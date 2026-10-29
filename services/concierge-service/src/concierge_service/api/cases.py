from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy.ext.asyncio import AsyncSession

from concierge_service.api.deps import get_db, require_permission, resolve_principal
from concierge_service.domain import cases, collaboration
from concierge_service.domain.access import COORDINATE_PERMISSION, REQUEST_PERMISSION
from concierge_service.domain.schemas import (
    AssignRequest,
    AuditOut,
    AuditPage,
    CaseCategory,
    CaseCreate,
    CaseOut,
    CasePage,
    CaseStatus,
    EscalateRequest,
    MessageCreate,
    MessageOut,
    MessagePage,
    NoteCreate,
    NoteOut,
    NotePage,
    OptionCreate,
    OptionList,
    OptionOut,
    ReadRequest,
    ReadResult,
    TransitionRequest,
)

router = APIRouter(prefix="/v1/concierge", tags=["concierge"])

Db = Annotated[AsyncSession, Depends(get_db)]
AnyPrincipal = Annotated[Principal, Depends(resolve_principal)]
Customer = Annotated[Principal, Depends(require_permission(REQUEST_PERMISSION))]
Coordinator = Annotated[Principal, Depends(require_permission(COORDINATE_PERMISSION))]
Limit = Annotated[int, Query(ge=1, le=100)]


def _coordinator_or_supervisor(principal: AnyPrincipal) -> Principal:
    from concierge_service.domain.access import forbidden, is_coordinator

    if not is_coordinator(principal):
        raise forbidden(f"Missing permission: {COORDINATE_PERMISSION}")
    return principal


Staff = Annotated[Principal, Depends(_coordinator_or_supervisor)]


@router.post("/cases", status_code=201, response_model=CaseOut, operation_id="createConciergeCase")
async def create_case(
    body: CaseCreate,
    response: Response,
    principal: Customer,
    db: Db,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaseOut:
    case, _ = await cases.create_case(db, principal, body, idempotency_key=idempotency_key)
    response.headers["Location"] = f"/v1/concierge/cases/{case.id}"
    return cases.to_out(case)


@router.get("/cases", response_model=CasePage, operation_id="listMyConciergeCases")
async def list_my_cases(
    principal: Customer,
    db: Db,
    status: CaseStatus | None = None,
    limit: Limit = 20,
    cursor: str | None = None,
) -> CasePage:
    rows, page = await cases.list_own_cases(db, principal, status=status, limit=limit, cursor=cursor)
    return CasePage(data=[cases.to_out(c) for c in rows], page=page)


@router.get("/queue", response_model=CasePage, operation_id="listConciergeQueue")
async def list_queue(
    principal: Staff,
    db: Db,
    status: CaseStatus | None = None,
    category: CaseCategory | None = None,
    assignee: Literal["me", "unassigned", "any"] = "any",
    breached: bool | None = None,
    open_only: bool = True,
    limit: Limit = 20,
    cursor: str | None = None,
) -> CasePage:
    rows, page = await cases.list_queue(
        db,
        principal,
        status=status,
        category=category,
        assignee=assignee,
        breached=breached,
        open_only=open_only,
        limit=limit,
        cursor=cursor,
    )
    return CasePage(data=[cases.to_out(c) for c in rows], page=page)


@router.get("/cases/{id}", response_model=CaseOut, operation_id="getConciergeCase")
async def get_case(id: str, principal: AnyPrincipal, db: Db) -> CaseOut:
    return cases.to_out(await cases.get_case(db, principal, id))


@router.post("/cases/{id}/transitions", response_model=CaseOut, operation_id="transitionConciergeCase")
async def transition_case(id: str, body: TransitionRequest, principal: AnyPrincipal, db: Db) -> CaseOut:
    case = await cases.transition(db, principal, id, to_status=body.to_status, reason=body.reason)
    return cases.to_out(case)


@router.post("/cases/{id}/assignment", response_model=CaseOut, operation_id="assignConciergeCase")
async def assign_case(id: str, principal: Staff, db: Db, body: AssignRequest | None = None) -> CaseOut:
    coordinator_id = body.coordinator_id if body else None
    return cases.to_out(await cases.assign(db, principal, id, coordinator_id=coordinator_id))


@router.post("/cases/{id}/escalation", response_model=CaseOut, operation_id="escalateConciergeCase")
async def escalate_case(id: str, body: EscalateRequest, principal: AnyPrincipal, db: Db) -> CaseOut:
    return cases.to_out(await cases.escalate(db, principal, id, reason=body.reason))


@router.get("/cases/{id}/audit", response_model=AuditPage, operation_id="listConciergeCaseAudit")
async def list_audit(id: str, principal: Staff, db: Db, limit: Limit = 50, cursor: str | None = None) -> AuditPage:
    rows, page = await cases.list_audit(db, principal, id, limit=limit, cursor=cursor)
    return AuditPage(data=[AuditOut.model_validate(r, from_attributes=True) for r in rows], page=page)


@router.get("/cases/{id}/notes", response_model=NotePage, operation_id="listConciergeCaseNotes")
async def list_notes(id: str, principal: Staff, db: Db, limit: Limit = 50, cursor: str | None = None) -> NotePage:
    rows, page = await collaboration.list_notes(db, principal, id, limit=limit, cursor=cursor)
    return NotePage(data=[NoteOut.model_validate(r, from_attributes=True) for r in rows], page=page)


@router.post("/cases/{id}/notes", status_code=201, response_model=NoteOut, operation_id="addConciergeCaseNote")
async def add_note(id: str, body: NoteCreate, principal: Staff, db: Db) -> NoteOut:
    return NoteOut.model_validate(await collaboration.add_note(db, principal, id, body), from_attributes=True)


@router.get("/cases/{id}/options", response_model=OptionList, operation_id="listConciergeCaseOptions")
async def list_options(id: str, principal: AnyPrincipal, db: Db) -> OptionList:
    rows = await collaboration.list_options(db, principal, id)
    return OptionList(data=[OptionOut.model_validate(r, from_attributes=True) for r in rows])


@router.post("/cases/{id}/options", status_code=201, response_model=OptionOut, operation_id="proposeConciergeCaseOption")
async def propose_option(id: str, body: OptionCreate, principal: Staff, db: Db) -> OptionOut:
    return OptionOut.model_validate(await collaboration.propose_option(db, principal, id, body), from_attributes=True)


@router.post("/cases/{id}/options/{option_id}/select", response_model=OptionOut, operation_id="selectConciergeCaseOption")
async def select_option(id: str, option_id: str, principal: Customer, db: Db) -> OptionOut:
    return OptionOut.model_validate(await collaboration.select_option(db, principal, id, option_id), from_attributes=True)


@router.get("/cases/{id}/messages", response_model=MessagePage, operation_id="listConciergeCaseMessages")
async def list_messages(id: str, principal: AnyPrincipal, db: Db, limit: Limit = 50, cursor: str | None = None) -> MessagePage:
    rows, page = await collaboration.list_messages(db, principal, id, limit=limit, cursor=cursor)
    return MessagePage(data=[MessageOut.model_validate(r, from_attributes=True) for r in rows], page=page)


@router.post("/cases/{id}/messages", status_code=201, response_model=MessageOut, operation_id="postConciergeCaseMessage")
async def post_message(id: str, body: MessageCreate, principal: AnyPrincipal, db: Db) -> MessageOut:
    return MessageOut.model_validate(await collaboration.post_message(db, principal, id, body), from_attributes=True)


@router.post("/cases/{id}/messages/read", response_model=ReadResult, operation_id="markConciergeCaseMessagesRead")
async def mark_read(id: str, principal: AnyPrincipal, db: Db, body: ReadRequest | None = None) -> ReadResult:
    up_to = body.up_to_message_id if body else None
    marked = await collaboration.mark_read(db, principal, id, up_to_message_id=up_to)
    return ReadResult(marked=marked)
