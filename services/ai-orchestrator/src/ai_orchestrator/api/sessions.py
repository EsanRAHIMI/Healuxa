from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from healuxa_py_common.errors import ApiError
from healuxa_py_common.observability.tracing import get_trace_id

from ai_orchestrator.api.deps import Caller, require_chat
from ai_orchestrator.config import settings
from ai_orchestrator.domain import guardrails, schemas
from ai_orchestrator.domain import session_service as svc
from ai_orchestrator.domain.engine import TurnResult, run_turn
from ai_orchestrator.domain.tools import TurnContext
from ai_orchestrator.infra.db import SessionLocal
from ai_orchestrator.infra.models import AiTurn
from ai_orchestrator.infra.platform import PlatformClient
from ai_orchestrator.llm import get_llm
from ai_orchestrator.llm.base import LLMError, LLMUnavailable

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/ai", tags=["assistant"])

# Tests swap this to route tool calls to an in-process stand-in for the platform services.
platform_transport: Any = None


def _unavailable() -> ApiError:
    return ApiError(status=503, code="service_unavailable", title="Service unavailable", detail="The assistant is temporarily unavailable.")


def _validate_key(key: str | None) -> None:
    if key is not None and not 8 <= len(key) <= 128:
        raise ApiError(status=422, code="validation_error", title="Validation failed", detail="Idempotency-Key must be between 8 and 128 characters")


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()


@router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=schemas.Session, operation_id="createAiSession")
async def create_session(body: schemas.CreateSession, caller: Caller = Depends(require_chat)) -> JSONResponse:
    async with SessionLocal() as db:
        session = await svc.create_session(db, caller.principal, body.locale)
    view = svc.session_view(session, [], available=get_llm().available)
    return JSONResponse(status_code=201, content=view.model_dump(mode="json"), headers={"Location": f"/v1/ai/sessions/{session.id}"})


@router.get("/sessions/{session_id}", response_model=schemas.Session, operation_id="getAiSession")
async def get_session(session_id: str, caller: Caller = Depends(require_chat)) -> schemas.Session:
    async with SessionLocal() as db:
        session = await svc.get_owned_session(db, session_id, caller.principal)
        turns = await svc.list_turns(db, session.id)
    return svc.session_view(session, turns, available=get_llm().available)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="deleteAiSession")
async def delete_session(session_id: str, caller: Caller = Depends(require_chat)) -> Response:
    async with SessionLocal() as db:
        session = await svc.get_owned_session(db, session_id, caller.principal)
        await svc.delete_session(db, session)
    return Response(status_code=204)


@router.post(
    "/sessions/{session_id}/messages",
    operation_id="postAiMessage",
    response_model=schemas.Turn,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def post_message(
    session_id: str,
    body: schemas.PostMessage,
    request: Request,
    caller: Caller = Depends(require_chat),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    _validate_key(idempotency_key)
    content = body.content.strip()
    if not content or len(content) > settings.max_message_chars:
        raise ApiError(
            status=422,
            code="validation_error",
            title="Validation failed",
            detail=f"Message must be between 1 and {settings.max_message_chars} characters",
            errors=[{"field": "content", "code": "invalid_length", "message": f"1 to {settings.max_message_chars} characters"}],  # type: ignore[list-item]
        )
    wants_stream = "text/event-stream" in request.headers.get("accept", "")
    llm = get_llm()

    async with SessionLocal() as db:
        session = await svc.get_owned_session(db, session_id, caller.principal, lock=True)
        if idempotency_key:
            replay = await svc.find_replay(db, session.id, idempotency_key)
            if replay is not None:
                view = svc.turn_view(replay)
                if not wants_stream:
                    return JSONResponse(content=view.model_dump(mode="json"))
                return StreamingResponse(_replay_stream(view), media_type="text/event-stream", headers=_SSE_HEADERS)
        # Refuse before writing anything when no model is configured and no code guardrail will answer.
        if guardrails.classify_input(content) is None and not llm.available:
            raise _unavailable()
        await svc.enforce_rate_limit(db, caller.principal)
        user_turn = await svc.add_user_turn(db, session, content, idempotency_key)
        history = await svc.history_messages(db, session.id, before_seq=user_turn.seq)
        ctx = TurnContext(
            user_id=caller.principal.user_id,
            locale=session.locale,
            session_id=session.id,
            handoff_case_id=session.handoff_case_id,
            platform=PlatformClient(token=caller.token, trace_id=get_trace_id(), transport=platform_transport),
        )

    events = _run(llm=llm, ctx=ctx, history=history, user_turn=user_turn, idempotency_key=idempotency_key)
    if wants_stream:
        return StreamingResponse(_stream(events, user_turn), media_type="text/event-stream", headers=_SSE_HEADERS)

    final: schemas.Turn | None = None
    async for kind, payload in events:
        if kind == "done":
            final = payload
        elif kind == "error":
            raise _unavailable()
    if final is None:
        raise _unavailable()
    return JSONResponse(content=final.model_dump(mode="json"))


_SSE_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


async def _replay_stream(view: schemas.Turn) -> AsyncIterator[bytes]:
    yield _sse("delta", {"text": view.content})
    yield _sse("done", {"turn": view.model_dump(mode="json")})


async def _run(*, llm: Any, ctx: TurnContext, history: list[dict], user_turn: AiTurn, idempotency_key: str | None) -> AsyncIterator[tuple[str, Any]]:
    """Drive the engine and persist the outcome. Yields engine events, then ("done", Turn) or ("error", code)."""
    result: TurnResult | None = None
    saved = False
    try:
        try:
            async for kind, payload in run_turn(llm=llm, ctx=ctx, history=history, user_text=user_turn.content):
                if kind == "result":
                    result = payload
                else:
                    yield kind, payload
        except (LLMUnavailable, LLMError):
            yield "error", "service_unavailable"
            return
        except Exception:  # noqa: BLE001 — never leak internals to the stream; details stay out of logs too
            logger.exception("assistant turn failed")
            yield "error", "internal_error"
            return
        if result is None:
            yield "error", "internal_error"
            return
        async with SessionLocal() as db:
            turn = await svc.add_assistant_turn(db, user_turn.session_id, result, idempotency_key)
        saved = True
        yield "done", svc.turn_view(turn)
    finally:
        await ctx.platform.aclose()
        if not saved:
            # Unanswered (provider failure or the client went away): drop the question so history stays paired.
            await asyncio.shield(_discard(user_turn))


async def _discard(user_turn: AiTurn) -> None:
    try:
        async with SessionLocal() as db:
            await svc.discard_user_turn(db, user_turn)
    except Exception:  # noqa: BLE001
        logger.warning("could not discard an unanswered turn")


async def _stream(events: AsyncIterator[tuple[str, Any]], user_turn: AiTurn) -> AsyncIterator[bytes]:
    yield _sse("turn", {"user_turn_id": user_turn.id})
    async for kind, payload in events:
        if kind == "done":
            yield _sse("done", {"turn": payload.model_dump(mode="json")})
        elif kind == "error":
            yield _sse("error", {"code": payload})
        else:
            yield _sse(kind, payload)
