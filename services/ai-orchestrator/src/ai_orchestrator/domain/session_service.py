"""AiSession persistence, ownership, idempotency and the per-user rate limit (all in Postgres)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_orchestrator.config import settings
from ai_orchestrator.domain import schemas
from ai_orchestrator.domain.engine import TurnResult
from ai_orchestrator.infra.models import AiSession, AiTurn


def _not_found() -> ApiError:
    # Same answer for "does not exist" and "belongs to someone else": never confirm another user's session id.
    return ApiError(status=404, code="not_found", title="Not found", detail="Session not found")


def turn_view(turn: AiTurn) -> schemas.Turn:
    return schemas.Turn(id=turn.id, role=turn.role, content=turn.content, cards=list(turn.cards or []), guardrail=turn.guardrail, created_at=turn.created_at)


def session_view(session: AiSession, turns: list[AiTurn], *, available: bool) -> schemas.Session:
    return schemas.Session(
        id=session.id,
        locale=session.locale if session.locale in ("en", "ar", "fa") else "en",
        turn_count=session.turn_count,
        handoff_case_id=session.handoff_case_id,
        assistant_available=available,
        max_message_chars=settings.max_message_chars,
        created_at=session.created_at,
        updated_at=session.updated_at,
        turns=[turn_view(t) for t in turns],
    )


async def create_session(db: AsyncSession, principal: Principal, locale: str) -> AiSession:
    session = AiSession(id=str(ULID()), tenant_id=principal.tenant_id, user_id=principal.user_id, locale=locale, turn_count=0)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_owned_session(db: AsyncSession, session_id: str, principal: Principal, *, lock: bool = False) -> AiSession:
    if len(session_id) != 26:
        raise _not_found()
    query = select(AiSession).where(AiSession.id == session_id, AiSession.tenant_id == principal.tenant_id, AiSession.user_id == principal.user_id)
    if lock:
        query = query.with_for_update()
    session = await db.scalar(query)
    if session is None:
        raise _not_found()
    return session


async def list_turns(db: AsyncSession, session_id: str) -> list[AiTurn]:
    return list((await db.scalars(select(AiTurn).where(AiTurn.session_id == session_id).order_by(AiTurn.seq))).all())


async def delete_session(db: AsyncSession, session: AiSession) -> None:
    await db.delete(session)
    await db.commit()


async def erase_user(db: AsyncSession, *, tenant_id: str, user_id: str) -> int:
    """Right to erasure: remove every session (turns cascade) of a deleted account."""
    result = await db.execute(delete(AiSession).where(AiSession.tenant_id == tenant_id, AiSession.user_id == user_id))
    await db.commit()
    return result.rowcount or 0


async def enforce_rate_limit(db: AsyncSession, principal: Principal) -> None:
    now = datetime.now(UTC)
    for window, limit in ((timedelta(minutes=1), settings.rate_limit_per_minute), (timedelta(days=1), settings.rate_limit_per_day)):
        since = now - window
        count, oldest = (
            await db.execute(
                select(func.count(AiTurn.id), func.min(AiTurn.created_at)).where(
                    AiTurn.tenant_id == principal.tenant_id,
                    AiTurn.user_id == principal.user_id,
                    AiTurn.role == "user",
                    AiTurn.created_at > since,
                )
            )
        ).one()
        if count >= limit:
            retry_after = max(1, int((oldest + window - now).total_seconds()) + 1) if oldest else int(window.total_seconds())
            error = ApiError(status=429, code="rate_limited", title="Too many requests", detail="Message limit reached. Please try again shortly.")
            error.retry_after = retry_after  # type: ignore[attr-defined]
            raise error


async def find_replay(db: AsyncSession, session_id: str, idempotency_key: str) -> AiTurn | None:
    """The assistant turn that already answered this Idempotency-Key, if any; 409 while it is still running."""
    turns = list((await db.scalars(select(AiTurn).where(AiTurn.session_id == session_id, AiTurn.idempotency_key == idempotency_key))).all())
    if not turns:
        return None
    answer = next((t for t in turns if t.role == "assistant"), None)
    if answer is None:
        raise ApiError(status=409, code="conflict", title="Conflict", detail="This message is still being answered")
    return answer


async def add_user_turn(db: AsyncSession, session: AiSession, content: str, idempotency_key: str | None) -> AiTurn:
    if session.turn_count >= settings.max_turns_per_session * 2:
        raise ApiError(status=409, code="conflict", title="Conflict", detail="This conversation is full. Please start a new one.")
    turn = AiTurn(
        id=str(ULID()),
        session_id=session.id,
        tenant_id=session.tenant_id,
        user_id=session.user_id,
        seq=session.turn_count + 1,
        role="user",
        content=content,
        cards=[],
        tool_calls=[],
        idempotency_key=idempotency_key,
    )
    session.turn_count += 1
    session.updated_at = datetime.now(UTC)
    db.add(turn)
    await db.commit()
    return turn


async def add_assistant_turn(db: AsyncSession, session_id: str, result: TurnResult, idempotency_key: str | None) -> AiTurn:
    session = await db.scalar(select(AiSession).where(AiSession.id == session_id).with_for_update())
    if session is None:  # deleted (or the account erased) while the turn was running
        raise _not_found()
    turn = AiTurn(
        id=str(ULID()),
        session_id=session.id,
        tenant_id=session.tenant_id,
        user_id=session.user_id,
        seq=session.turn_count + 1,
        role="assistant",
        content=result.text,
        cards=result.cards,
        guardrail=result.guardrail,
        tool_calls=result.tool_calls,
        model=result.model,
        stop_reason=result.stop_reason,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        idempotency_key=idempotency_key,
    )
    session.turn_count += 1
    session.updated_at = datetime.now(UTC)
    if result.handoff_case_id:
        session.handoff_case_id = result.handoff_case_id
    db.add(turn)
    await db.commit()
    await db.refresh(turn)
    return turn


async def discard_user_turn(db: AsyncSession, turn: AiTurn) -> None:
    """A turn that got no answer (provider failure, client went away) is removed so history stays paired."""
    session = await db.scalar(select(AiSession).where(AiSession.id == turn.session_id).with_for_update())
    if session is None:
        return
    await db.execute(delete(AiTurn).where(AiTurn.id == turn.id))
    if session.turn_count == turn.seq:
        session.turn_count -= 1
    await db.commit()


def _cards_note(cards: list[dict[str, Any]]) -> str:
    refs = [f"{c['kind']} {c['id']}" for c in cards if c.get("id")]
    return f"\n[cards shown: {'; '.join(refs)}]" if refs else ""


async def history_messages(db: AsyncSession, session_id: str, *, before_seq: int) -> list[dict[str, Any]]:
    """The last few turns as plain text. Tool results are not replayed: facts must be re-fetched each turn."""
    rows = list(
        (
            await db.scalars(
                select(AiTurn).where(AiTurn.session_id == session_id, AiTurn.seq < before_seq).order_by(AiTurn.seq.desc()).limit(settings.history_turns)
            )
        ).all()
    )
    rows.reverse()
    while rows and rows[0].role != "user":
        rows.pop(0)
    return [{"role": t.role, "content": t.content + (_cards_note(t.cards or []) if t.role == "assistant" else "")} for t in rows]
