from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy.ext.asyncio import AsyncSession

from appointment_service.api.deps import get_db, get_directory, optional_principal, require_permission
from appointment_service.clients.provider_directory import ProviderDirectory
from appointment_service.config import settings
from appointment_service.domain import schemas
from appointment_service.domain.availability import list_slots
from appointment_service.domain.booking import booking_service
from appointment_service.domain.schemas import AppointmentStatus

router = APIRouter(tags=["appointments"])

Db = Annotated[AsyncSession, Depends(get_db)]
Directory = Annotated[ProviderDirectory, Depends(get_directory)]
Creator = Annotated[Principal, Depends(require_permission("appointments:create"))]
Reader = Annotated[Principal, Depends(require_permission("appointments:read"))]
Writer = Annotated[Principal, Depends(require_permission("appointments:write"))]
MaybePrincipal = Annotated[Principal | None, Depends(optional_principal)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
IfMatch = Annotated[str | None, Header(alias="If-Match", max_length=64)]


def _etag(response: Response, appointment: schemas.Appointment) -> None:
    response.headers["ETag"] = f'"v{appointment.version}"'


@router.get("/v1/services/{service_id}/slots", tags=["slots"], response_model_by_alias=True)
async def list_available_slots(
    db: Db,
    directory: Directory,
    principal: MaybePrincipal,
    service_id: str,
    from_: date = Query(alias="from"),
    to: date = Query(),
) -> schemas.SlotList:
    tenant = principal.tenant_id if principal else settings.public_tenant
    return await list_slots(db, directory, tenant, service_id, from_, to)


@router.get("/v1/appointments")
async def list_appointments(
    db: Db,
    directory: Directory,
    principal: Reader,
    user_id: str | None = Query(default=None, max_length=36),
    provider_id: str | None = Query(default=None, max_length=36),
    branch_id: str | None = Query(default=None, max_length=36),
    facility_id: str | None = Query(default=None, max_length=36),
    status: AppointmentStatus | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    sort: Literal["scheduled_at", "-scheduled_at"] = "scheduled_at",
) -> dict:
    data, next_cursor, has_more = await booking_service.list(
        db,
        directory,
        principal,
        user_id=user_id,
        provider_id=provider_id,
        branch_id=branch_id,
        facility_id=facility_id,
        status=status,
        from_=from_,
        to=to,
        limit=limit,
        cursor=cursor,
        sort=sort,
    )
    return {
        "data": [a.model_dump(mode="json") for a in data],
        "page": {"next_cursor": next_cursor, "limit": limit, "has_more": has_more},
    }


@router.post("/v1/appointments", status_code=201)
async def create_appointment(
    db: Db,
    directory: Directory,
    principal: Creator,
    body: schemas.CreateAppointment,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> schemas.Appointment:
    # An Idempotency-Key replay returns the original appointment with the same 201 response.
    appointment = await booking_service.create_hold(db, directory, principal, body, idempotency_key=idempotency_key)
    response.headers["Location"] = f"/v1/appointments/{appointment.id}"
    _etag(response, appointment)
    return appointment


@router.get("/v1/appointments/{appointment_id}")
async def get_appointment(
    db: Db, directory: Directory, principal: Reader, appointment_id: str, response: Response
) -> schemas.Appointment:
    appointment = await booking_service.get(db, directory, principal, appointment_id)
    _etag(response, appointment)
    return appointment


@router.post("/v1/appointments/{appointment_id}/status")
async def transition_appointment(
    db: Db,
    directory: Directory,
    principal: Writer,
    appointment_id: str,
    body: schemas.TransitionRequest,
    response: Response,
    idempotency_key: IdempotencyKey = None,
    if_match: IfMatch = None,
) -> schemas.Appointment:
    appointment = await booking_service.transition(
        db, directory, principal, appointment_id, body, if_match=if_match, idempotency_key=idempotency_key
    )
    _etag(response, appointment)
    return appointment


@router.post("/v1/appointments/{appointment_id}/reschedule", status_code=201)
async def reschedule_appointment(
    db: Db,
    directory: Directory,
    principal: Writer,
    appointment_id: str,
    body: schemas.RescheduleRequest,
    response: Response,
    idempotency_key: IdempotencyKey = None,
    if_match: IfMatch = None,
) -> schemas.Appointment:
    appointment = await booking_service.reschedule(
        db, directory, principal, appointment_id, body, if_match=if_match, idempotency_key=idempotency_key
    )
    response.headers["Location"] = f"/v1/appointments/{appointment.id}"
    _etag(response, appointment)
    return appointment


@router.get("/v1/appointments/{appointment_id}/transitions")
async def list_appointment_transitions(
    db: Db, directory: Directory, principal: Reader, appointment_id: str
) -> dict:
    data = await booking_service.history(db, directory, principal, appointment_id)
    return {"data": [t.model_dump(mode="json") for t in data]}
