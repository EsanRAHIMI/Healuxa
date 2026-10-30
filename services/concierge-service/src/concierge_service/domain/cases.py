"""Concierge case use cases. Every mutation locks the case row, writes an audit entry and stages
its events in the same transaction (transactional outbox)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from concierge_service.config import settings
from concierge_service.domain import state_machine as sm
from concierge_service.domain.access import (
    actor_of,
    case_role,
    conflict,
    forbidden,
    is_coordinator,
    is_supervisor,
    not_found,
    require_case_role,
    unprocessable,
)
from concierge_service.domain.pagination import decode_cursor, encode_cursor
from concierge_service.domain.schemas import CaseCreate, CaseOut, PageMeta
from concierge_service.events.publisher import event_publisher
from concierge_service.infra.models import CaseAudit, ConciergeCase


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(ULID())


def sla_breached(case: ConciergeCase, at: datetime | None = None) -> bool:
    at = at or now()
    if case.first_responded_at is not None:
        return case.first_responded_at > case.first_response_due_at
    if case.status in sm.TERMINAL:
        return False if case.closed_at is None else case.closed_at > case.first_response_due_at
    return at > case.first_response_due_at


def to_out(case: ConciergeCase) -> CaseOut:
    return CaseOut(
        id=case.id,
        customer_id=case.customer_id,
        category=case.category,  # type: ignore[arg-type]
        status=case.status,  # type: ignore[arg-type]
        preferred_start_date=case.preferred_start_date,
        preferred_end_date=case.preferred_end_date,
        languages=list(case.languages or []),
        destination_city=case.destination_city,
        needs_note=case.needs_note,
        coordinator_id=case.coordinator_id,
        selected_option_id=case.selected_option_id,
        escalated_from=case.escalated_from,
        first_response_due_at=case.first_response_due_at,
        first_responded_at=case.first_responded_at,
        sla_breached=sla_breached(case),
        closed_at=case.closed_at,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _body_hash(body: CaseCreate) -> str:
    canonical = json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def audit(
    db: AsyncSession,
    case: ConciergeCase,
    *,
    action: str,
    actor: Principal,
    role: str,
    from_status: str | None = None,
    to_status: str | None = None,
    reason: str | None = None,
    subject_id: str | None = None,
    at: datetime | None = None,
) -> None:
    db.add(
        CaseAudit(
            id=new_id(),
            tenant_id=case.tenant_id,
            case_id=case.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor.user_id,
            actor_role=role,
            reason=reason,
            subject_id=subject_id,
            created_at=at or now(),
        )
    )


async def load_case(db: AsyncSession, case_id: str, *, lock: bool = False) -> ConciergeCase | None:
    stmt = select(ConciergeCase).where(ConciergeCase.id == case_id)
    if lock:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


async def change_status(
    db: AsyncSession,
    case: ConciergeCase,
    *,
    to_status: str,
    actor: Principal,
    role: str,
    reason: str | None = None,
) -> None:
    """Apply a validated transition: state, audit row and ``concierge.case_status_changed``."""
    from_status = case.status
    sm.ensure_transition(from_status, to_status)
    at = now()
    case.status = to_status
    case.updated_at = at
    case.version += 1
    if to_status == "escalated":
        case.escalated_from = from_status
    elif from_status == "escalated":
        case.escalated_from = None
    if to_status in sm.TERMINAL:
        case.closed_at = at
    audit(db, case, action="status_changed", actor=actor, role=role, from_status=from_status, to_status=to_status, reason=reason, at=at)
    await event_publisher.publish(
        db=db,
        event_type="concierge.case_status_changed",
        tenant_id=case.tenant_id,
        payload={
            "case_id": case.id,
            "customer_id": case.customer_id,
            "coordinator_id": case.coordinator_id,
            "previous_status": from_status,
            "status": to_status,
            "changed_by_role": role,
            "changed_at": at.isoformat(),
        },
        actor=actor_of(actor),
    )


def mark_first_response(case: ConciergeCase, role: str) -> None:
    if role in ("coordinator", "supervisor") and case.first_responded_at is None:
        case.first_responded_at = now()


async def create_case(
    db: AsyncSession, principal: Principal, body: CaseCreate, *, idempotency_key: str | None
) -> tuple[ConciergeCase, bool]:
    """Returns (case, created). A replay with the same key and body returns the original case."""
    body_hash = _body_hash(body)
    if idempotency_key is not None:
        if not 8 <= len(idempotency_key) <= 128:
            raise unprocessable("Idempotency-Key must be 8-128 characters", "Idempotency-Key")
        existing = await _by_creation_key(db, principal, idempotency_key)
        if existing is not None:
            return _replay(existing, body_hash), False

    at = now()
    case = ConciergeCase(
        id=new_id(),
        tenant_id=principal.tenant_id,
        customer_id=principal.user_id,
        category=body.category,
        status="submitted",
        preferred_start_date=body.preferred_start_date,
        preferred_end_date=body.preferred_end_date,
        languages=list(dict.fromkeys(body.languages)),
        destination_city=body.destination_city,
        needs_note=body.needs_note,
        first_response_due_at=at + timedelta(minutes=settings.first_response_sla_minutes),
        creation_key=idempotency_key,
        creation_hash=body_hash if idempotency_key else None,
        created_at=at,
        updated_at=at,
    )
    db.add(case)
    await db.flush()  # no ORM relationships: insert the case before rows referencing it
    audit(db, case, action="submitted", actor=principal, role="customer", to_status="submitted", at=at)
    await event_publisher.publish(
        db=db,
        event_type="concierge.case_submitted",
        tenant_id=case.tenant_id,
        payload={
            "case_id": case.id,
            "customer_id": case.customer_id,
            "category": case.category,
            "status": "submitted",
            "first_response_due_at": case.first_response_due_at.isoformat(),
            "submitted_at": at.isoformat(),
        },
        actor=actor_of(principal),
    )
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent request with the same key won the race: replay it.
        await db.rollback()
        if idempotency_key is None:
            raise
        existing = await _by_creation_key(db, principal, idempotency_key)
        if existing is None:
            raise
        return _replay(existing, body_hash), False
    return case, True


async def _by_creation_key(db: AsyncSession, principal: Principal, key: str) -> ConciergeCase | None:
    return await db.scalar(
        select(ConciergeCase).where(
            ConciergeCase.tenant_id == principal.tenant_id,
            ConciergeCase.customer_id == principal.user_id,
            ConciergeCase.creation_key == key,
        )
    )


def _replay(existing: ConciergeCase, body_hash: str) -> ConciergeCase:
    if existing.creation_hash != body_hash:
        raise ApiError(
            status=409,
            code="idempotency_conflict",
            title="Idempotency conflict",
            detail="Idempotency-Key was already used with a different request body",
        )
    return existing


def _page(rows: list[ConciergeCase], limit: int) -> tuple[list[ConciergeCase], PageMeta]:
    has_more = len(rows) > limit
    rows = rows[:limit]
    cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more and rows else None
    return rows, PageMeta(next_cursor=cursor, limit=limit, has_more=has_more)


async def list_own_cases(
    db: AsyncSession, principal: Principal, *, status: str | None, limit: int, cursor: str | None
) -> tuple[list[ConciergeCase], PageMeta]:
    stmt = select(ConciergeCase).where(
        ConciergeCase.tenant_id == principal.tenant_id, ConciergeCase.customer_id == principal.user_id
    )
    if status:
        stmt = stmt.where(ConciergeCase.status == status)
    if cursor:
        t, i = decode_cursor(cursor)
        stmt = stmt.where(
            or_(ConciergeCase.created_at < t, and_(ConciergeCase.created_at == t, ConciergeCase.id < i))
        )
    stmt = stmt.order_by(ConciergeCase.created_at.desc(), ConciergeCase.id.desc()).limit(limit + 1)
    return _page(list(await db.scalars(stmt)), limit)


async def list_queue(
    db: AsyncSession,
    principal: Principal,
    *,
    status: str | None,
    category: str | None,
    assignee: str,
    breached: bool | None,
    open_only: bool,
    limit: int,
    cursor: str | None,
) -> tuple[list[ConciergeCase], PageMeta]:
    c = ConciergeCase
    stmt = select(c).where(c.tenant_id == principal.tenant_id)
    if status:
        stmt = stmt.where(c.status == status)
    elif open_only:
        stmt = stmt.where(c.status.not_in(tuple(sm.TERMINAL)))
    if category:
        stmt = stmt.where(c.category == category)
    if assignee == "me":
        stmt = stmt.where(c.coordinator_id == principal.user_id)
    elif assignee == "unassigned":
        stmt = stmt.where(c.coordinator_id.is_(None))
    if breached is not None:
        at = now()
        is_breached = or_(
            and_(c.first_responded_at.is_not(None), c.first_responded_at > c.first_response_due_at),
            and_(c.first_responded_at.is_(None), c.closed_at.is_(None), c.first_response_due_at < at),
            and_(c.first_responded_at.is_(None), c.closed_at.is_not(None), c.closed_at > c.first_response_due_at),
        )
        stmt = stmt.where(is_breached if breached else ~is_breached)
    if cursor:
        t, i = decode_cursor(cursor)
        stmt = stmt.where(or_(c.created_at > t, and_(c.created_at == t, c.id > i)))
    stmt = stmt.order_by(c.created_at.asc(), c.id.asc()).limit(limit + 1)
    return _page(list(await db.scalars(stmt)), limit)


async def get_case(db: AsyncSession, principal: Principal, case_id: str) -> ConciergeCase:
    case = await load_case(db, case_id)
    require_case_role(principal, case)
    assert case is not None
    return case


async def transition(
    db: AsyncSession, principal: Principal, case_id: str, *, to_status: str, reason: str | None
) -> ConciergeCase:
    case = await load_case(db, case_id, lock=True)
    role = require_case_role(principal, case)
    assert case is not None
    if to_status not in sm.DIRECT_TARGETS and not (case.status == "escalated" and to_status == "assigned"):
        raise unprocessable(
            f"{to_status} is set through its own endpoint (assignment / escalation)", "to_status"
        )
    if to_status == "assigned" and case.coordinator_id is None:
        raise conflict("Assign a coordinator before returning the case to assigned")
    sm.ensure_transition(case.status, to_status)
    is_assignee = case.coordinator_id is not None and case.coordinator_id == principal.user_id
    if not sm.role_may_transition(role, from_status=case.status, to_status=to_status, is_assignee=is_assignee):
        raise forbidden(f"A {role} may not move this case from {case.status} to {to_status}")
    if to_status == "cancelled" and role != "customer" and not reason:
        raise unprocessable("A reason is required when staff cancel a case", "reason")
    if to_status == "arranged" and case.selected_option_id is None:
        raise conflict("The customer must select a provider option before the case is arranged")
    mark_first_response(case, role)
    await change_status(db, case, to_status=to_status, actor=principal, role=role, reason=reason)
    await db.commit()
    return case


async def assign(db: AsyncSession, principal: Principal, case_id: str, *, coordinator_id: str | None) -> ConciergeCase:
    case = await load_case(db, case_id, lock=True)
    role = require_case_role(principal, case, "coordinator", "supervisor")
    assert case is not None
    target = coordinator_id or principal.user_id
    if target != principal.user_id and not is_supervisor(principal):
        raise forbidden("Only a supervisor may assign a case to someone else")
    if case.status in sm.TERMINAL:
        raise sm.illegal(case.status, "assigned")
    if case.status == "escalated" and role != "supervisor":
        raise forbidden("Only a supervisor may reassign an escalated case")
    if case.coordinator_id is not None and role != "supervisor":
        if case.coordinator_id == principal.user_id:
            return case  # claiming your own case again is a no-op
        raise conflict("Case is already assigned to another coordinator")
    previous = case.coordinator_id
    case.coordinator_id = target
    case.updated_at = now()
    mark_first_response(case, role)
    audit(db, case, action="assigned", actor=principal, role=role, from_status=case.status, to_status=case.status, subject_id=target, reason=f"previous={previous}" if previous else None)
    if case.status in sm.ASSIGNABLE_INTO_ASSIGNED:
        await change_status(db, case, to_status="assigned", actor=principal, role=role)
    await db.commit()
    return case


async def escalate(db: AsyncSession, principal: Principal, case_id: str, *, reason: str) -> ConciergeCase:
    case = await load_case(db, case_id, lock=True)
    role = require_case_role(principal, case)
    assert case is not None
    if role == "coordinator" and case.coordinator_id != principal.user_id:
        raise forbidden("Only the assigned coordinator, the customer or a supervisor may escalate")
    sm.ensure_transition(case.status, "escalated")
    await change_status(db, case, to_status="escalated", actor=principal, role=role, reason=reason)
    await db.commit()
    return case


async def list_audit(
    db: AsyncSession, principal: Principal, case_id: str, *, limit: int, cursor: str | None
) -> tuple[list[CaseAudit], PageMeta]:
    case = await load_case(db, case_id)
    require_case_role(principal, case, "coordinator", "supervisor")
    stmt = select(CaseAudit).where(CaseAudit.case_id == case_id)
    if cursor:
        t, i = decode_cursor(cursor)
        stmt = stmt.where(or_(CaseAudit.created_at > t, and_(CaseAudit.created_at == t, CaseAudit.id > i)))
    rows = list(await db.scalars(stmt.order_by(CaseAudit.created_at.asc(), CaseAudit.id.asc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more and rows else None
    return rows, PageMeta(next_cursor=next_cursor, limit=limit, has_more=has_more)

