"""Internal notes, provider options and secure messaging on a case."""

from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from concierge_service.domain import state_machine as sm
from concierge_service.domain.access import (
    actor_of,
    conflict,
    forbidden,
    messaging_role,
    not_found,
    require_case_role,
)
from concierge_service.domain.cases import audit, change_status, load_case, mark_first_response, new_id, now
from concierge_service.domain.pagination import decode_cursor, encode_cursor
from concierge_service.domain.schemas import MessageCreate, NoteCreate, OptionCreate, PageMeta
from concierge_service.events.publisher import event_publisher
from concierge_service.infra.models import CaseMessage, InternalNote, ProviderOption

T = TypeVar("T", InternalNote, CaseMessage)

OPTION_STATES = frozenset({"assigned", "in_progress", "awaiting_customer"})
SELECTION_STATES = frozenset({"in_progress", "awaiting_customer"})


async def _ascending_page(
    db: AsyncSession, model: type[T], case_id: str, *, limit: int, cursor: str | None
) -> tuple[list[T], PageMeta]:
    stmt = select(model).where(model.case_id == case_id)
    if cursor:
        t, i = decode_cursor(cursor)
        stmt = stmt.where(or_(model.created_at > t, and_(model.created_at == t, model.id > i)))
    rows = list(await db.scalars(stmt.order_by(model.created_at.asc(), model.id.asc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more and rows else None
    return rows, PageMeta(next_cursor=next_cursor, limit=limit, has_more=has_more)


# ── internal notes (staff only) ──────────────────────────────────────────────


async def add_note(db: AsyncSession, principal: Principal, case_id: str, body: NoteCreate) -> InternalNote:
    case = await load_case(db, case_id)
    require_case_role(principal, case, "coordinator", "supervisor")
    note = InternalNote(id=new_id(), tenant_id=principal.tenant_id, case_id=case_id, author_id=principal.user_id, body=body.body, created_at=now())
    db.add(note)
    await db.commit()
    return note


async def list_notes(
    db: AsyncSession, principal: Principal, case_id: str, *, limit: int, cursor: str | None
) -> tuple[list[InternalNote], PageMeta]:
    case = await load_case(db, case_id)
    require_case_role(principal, case, "coordinator", "supervisor")
    return await _ascending_page(db, InternalNote, case_id, limit=limit, cursor=cursor)


# ── provider options ─────────────────────────────────────────────────────────


async def propose_option(db: AsyncSession, principal: Principal, case_id: str, body: OptionCreate) -> ProviderOption:
    case = await load_case(db, case_id, lock=True)
    role = require_case_role(principal, case, "coordinator", "supervisor")
    assert case is not None
    if role == "coordinator" and case.coordinator_id != principal.user_id:
        raise forbidden("Only the assigned coordinator may propose options")
    if case.status not in OPTION_STATES:
        raise conflict(f"Options cannot be proposed while the case is {case.status}")
    duplicate = await db.scalar(
        select(ProviderOption.id).where(
            ProviderOption.case_id == case_id,
            ProviderOption.provider_id == body.provider_id,
            ProviderOption.branch_id.is_not_distinct_from(body.branch_id),
            ProviderOption.service_id.is_not_distinct_from(body.service_id),
        )
    )
    if duplicate:
        raise conflict("This provider option was already proposed")
    at = now()
    option = ProviderOption(
        id=new_id(),
        tenant_id=case.tenant_id,
        case_id=case_id,
        provider_id=body.provider_id,
        facility_id=body.facility_id,
        branch_id=body.branch_id,
        service_id=body.service_id,
        label=body.label,
        status="proposed",
        proposed_by=principal.user_id,
        created_at=at,
    )
    db.add(option)
    case.updated_at = at
    audit(db, case, action="option_proposed", actor=principal, role=role, from_status=case.status, to_status=case.status, subject_id=option.id, at=at)
    await db.commit()
    return option


async def list_options(db: AsyncSession, principal: Principal, case_id: str) -> list[ProviderOption]:
    case = await load_case(db, case_id)
    require_case_role(principal, case)
    rows = await db.scalars(
        select(ProviderOption).where(ProviderOption.case_id == case_id).order_by(ProviderOption.created_at, ProviderOption.id)
    )
    return list(rows)


async def select_option(db: AsyncSession, principal: Principal, case_id: str, option_id: str) -> ProviderOption:
    case = await load_case(db, case_id, lock=True)
    role = require_case_role(principal, case, "customer")
    assert case is not None
    option = await db.scalar(
        select(ProviderOption).where(ProviderOption.id == option_id, ProviderOption.case_id == case_id)
    )
    if option is None:
        raise not_found("Option")
    if case.status not in SELECTION_STATES:
        raise conflict(f"An option cannot be selected while the case is {case.status}")
    if case.selected_option_id is not None:
        if case.selected_option_id == option_id:
            return option
        raise conflict("An option was already selected for this case")
    await db.execute(
        update(ProviderOption)
        .where(ProviderOption.case_id == case_id, ProviderOption.id != option_id)
        .values(status="not_selected")
    )
    option.status = "selected"
    case.selected_option_id = option_id
    case.updated_at = now()
    audit(db, case, action="option_selected", actor=principal, role=role, from_status=case.status, to_status=case.status, subject_id=option_id)
    if case.status == "awaiting_customer":
        await change_status(db, case, to_status="in_progress", actor=principal, role=role, reason="option selected")
    await db.commit()
    await db.refresh(option)
    return option


# ── secure messaging (customer ⇄ assigned coordinator only) ──────────────────


async def post_message(db: AsyncSession, principal: Principal, case_id: str, body: MessageCreate) -> CaseMessage:
    case = await load_case(db, case_id, lock=True)
    role = messaging_role(principal, case)
    assert case is not None
    if case.status in sm.TERMINAL:
        raise conflict(f"Messaging is closed: the case is {case.status}")
    at = now()
    message = CaseMessage(
        id=new_id(), tenant_id=case.tenant_id, case_id=case_id, sender_id=principal.user_id, sender_role=role, body=body.body, created_at=at
    )
    db.add(message)
    mark_first_response(case, role)
    case.updated_at = at
    await event_publisher.publish(
        db=db,
        event_type="concierge.message_posted",
        tenant_id=case.tenant_id,
        payload={
            "case_id": case.id,
            "message_id": message.id,
            "customer_id": case.customer_id,
            "coordinator_id": case.coordinator_id,
            "sender_id": principal.user_id,
            "sender_role": role,
            "posted_at": at.isoformat(),
        },
        actor=actor_of(principal),
    )
    await db.commit()
    return message


async def list_messages(
    db: AsyncSession, principal: Principal, case_id: str, *, limit: int, cursor: str | None
) -> tuple[list[CaseMessage], PageMeta]:
    case = await load_case(db, case_id)
    messaging_role(principal, case)
    return await _ascending_page(db, CaseMessage, case_id, limit=limit, cursor=cursor)


async def mark_read(db: AsyncSession, principal: Principal, case_id: str, *, up_to_message_id: str | None) -> int:
    case = await load_case(db, case_id)
    role = messaging_role(principal, case)
    counterpart = "coordinator" if role == "customer" else "customer"
    stmt = (
        update(CaseMessage)
        .where(CaseMessage.case_id == case_id, CaseMessage.sender_role == counterpart, CaseMessage.read_at.is_(None))
        .values(read_at=now())
    )
    if up_to_message_id is not None:
        anchor: datetime | None = await db.scalar(
            select(CaseMessage.created_at).where(CaseMessage.id == up_to_message_id, CaseMessage.case_id == case_id)
        )
        if anchor is None:
            raise not_found("Message")
        stmt = stmt.where(
            or_(CaseMessage.created_at < anchor, and_(CaseMessage.created_at == anchor, CaseMessage.id <= up_to_message_id))
        )
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)
