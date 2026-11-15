"""Service-authenticated read endpoints for appointment-service (booking engine) and profile-service
(records access checks).

Mesh-internal only (``serviceAuth``): the caller presents a service token issued by identity-service
(``POST /v1/auth/service-token``); introspection yields the ``service`` permission. Responses are raw
scheduling facts — appointment-service derives slots from them and never invents availability.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from healuxa_py_common.middleware.auth import Principal
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from provider_service.api.deps import get_db, resolve_principal
from provider_service.domain.access import forbidden, not_found, unprocessable
from provider_service.infra.models import (
    Affiliation,
    AvailabilityException,
    AvailabilityRule,
    Branch,
    Facility,
    FacilityStaff,
    OperatingHoursWindow,
    Provider,
    ServiceOffering,
)

SERVICE_PERMISSION = "service"
MAX_WINDOW = timedelta(days=62)

router = APIRouter(prefix="/v1/internal/scheduling", tags=["internal"])


def require_service(principal: Principal = Depends(resolve_principal)) -> Principal:
    if SERVICE_PERMISSION not in principal.permissions:
        raise forbidden("Service credentials required")
    return principal


Db = Annotated[AsyncSession, Depends(get_db)]
Service = Annotated[Principal, Depends(require_service)]


class SchedulingOffering(BaseModel):
    id: str
    provider_id: str
    facility_id: str
    branch_id: str
    name: str
    category: str
    duration_minutes: int
    buffer_minutes: int
    mode: str
    status: str
    price_type: str
    professional_fee_minor: int | None
    facility_fee_minor: int | None
    currency: str


class SchedulingProvider(BaseModel):
    id: str
    user_id: str
    status: str
    verification_status: str


class SchedulingFacility(BaseModel):
    id: str
    status: str
    verification_status: str


class SchedulingBranch(BaseModel):
    id: str
    facility_id: str
    timezone: str
    status: str


class HoursWindow(BaseModel):
    weekday: int
    start_minute: int
    end_minute: int


class SchedulingRule(BaseModel):
    id: str
    weekday: int
    start_minute: int
    end_minute: int
    effective_from: date
    effective_until: date | None


class SchedulingException(BaseModel):
    id: str
    branch_id: str | None
    starts_at: datetime
    ends_at: datetime
    reason: str


class SchedulingContext(BaseModel):
    offering: SchedulingOffering
    provider: SchedulingProvider
    facility: SchedulingFacility
    branch: SchedulingBranch
    affiliation_active: bool
    bookable: bool
    operating_hours: list[HoursWindow]
    availability_rules: list[SchedulingRule]
    exceptions: list[SchedulingException]


class FacilityRole(BaseModel):
    facility_id: str
    role: str


class SchedulingActor(BaseModel):
    user_id: str
    provider_ids: list[str]
    facility_roles: list[FacilityRole]


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None:
        raise unprocessable(f"{field} must include a UTC offset", field)
    return value.astimezone(UTC)


@router.get("/services/{service_id}")
async def get_scheduling_context(
    db: Db,
    _: Service,
    service_id: str,
    tenant_id: str = Query(min_length=2, max_length=64),
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
) -> SchedulingContext:
    window_start, window_end = _aware(from_, "from"), _aware(to, "to")
    if window_end <= window_start or window_end - window_start > MAX_WINDOW:
        raise unprocessable("Window must be positive and at most 62 days", "to")

    offering = await db.scalar(
        select(ServiceOffering).where(ServiceOffering.id == service_id, ServiceOffering.tenant_id == tenant_id)
    )
    if offering is None:
        raise not_found("Service offering")
    provider = await db.get(Provider, offering.provider_id)
    facility = await db.get(Facility, offering.facility_id)
    branch = await db.get(Branch, offering.branch_id)
    if provider is None or facility is None or branch is None:
        raise not_found("Service offering")

    affiliation_active = (
        await db.scalar(
            select(Affiliation.id).where(
                Affiliation.provider_id == provider.id,
                Affiliation.branch_id == branch.id,
                Affiliation.status == "active",
            )
        )
    ) is not None
    hours = (
        await db.scalars(
            select(OperatingHoursWindow)
            .where(OperatingHoursWindow.branch_id == branch.id)
            .order_by(OperatingHoursWindow.weekday, OperatingHoursWindow.start_minute)
        )
    ).all()
    rules = (
        await db.scalars(
            select(AvailabilityRule)
            .where(AvailabilityRule.provider_id == provider.id, AvailabilityRule.branch_id == branch.id)
            .order_by(AvailabilityRule.weekday, AvailabilityRule.start_minute)
        )
    ).all()
    exceptions = (
        await db.scalars(
            select(AvailabilityException)
            .where(
                AvailabilityException.provider_id == provider.id,
                or_(AvailabilityException.branch_id.is_(None), AvailabilityException.branch_id == branch.id),
                and_(AvailabilityException.starts_at < window_end, AvailabilityException.ends_at > window_start),
            )
            .order_by(AvailabilityException.starts_at)
        )
    ).all()

    bookable = (
        offering.status == "active"
        and provider.status == "active"
        and provider.verification_status == "verified"
        and provider.content_license_accepted_at is not None
        and facility.status == "active"
        and facility.verification_status == "verified"
        and facility.content_license_accepted_at is not None
        and branch.status == "active"
        and affiliation_active
    )
    return SchedulingContext(
        offering=SchedulingOffering.model_validate(offering, from_attributes=True),
        provider=SchedulingProvider.model_validate(provider, from_attributes=True),
        facility=SchedulingFacility.model_validate(facility, from_attributes=True),
        branch=SchedulingBranch.model_validate(branch, from_attributes=True),
        affiliation_active=affiliation_active,
        bookable=bookable,
        operating_hours=[HoursWindow.model_validate(h, from_attributes=True) for h in hours],
        availability_rules=[SchedulingRule.model_validate(r, from_attributes=True) for r in rules],
        exceptions=[SchedulingException.model_validate(e, from_attributes=True) for e in exceptions],
    )


@router.get("/actors/{user_id}")
async def get_scheduling_actor(
    db: Db, _: Service, user_id: str, tenant_id: str = Query(min_length=2, max_length=64)
) -> SchedulingActor:
    """What a user may do in scheduling: the providers they own and their facility staff roles."""
    provider_ids = (
        await db.scalars(
            select(Provider.id).where(Provider.tenant_id == tenant_id, Provider.user_id == user_id).order_by(Provider.id)
        )
    ).all()
    roles = (
        await db.execute(
            select(FacilityStaff.facility_id, FacilityStaff.role)
            .join(Facility, Facility.id == FacilityStaff.facility_id)
            .where(FacilityStaff.user_id == user_id, Facility.tenant_id == tenant_id)
            .order_by(FacilityStaff.facility_id)
        )
    ).all()
    return SchedulingActor(
        user_id=user_id,
        provider_ids=list(provider_ids),
        facility_roles=[FacilityRole(facility_id=f, role=r) for f, r in roles],
    )


# ── Records access (consumed by profile-service) ─────────────────────────────────────────────
# profile-service decides whether a caller may read a customer's shared medical record. It must not
# trust the caller's claim to belong to an organisation, so it asks here, with a service token.

records_router = APIRouter(prefix="/v1/internal/records-access", tags=["internal"])


class RecordsActorProvider(BaseModel):
    id: str
    status: str
    verification_status: str


class RecordsActorFacility(BaseModel):
    id: str
    role: str
    status: str
    verification_status: str


class RecordsActor(BaseModel):
    user_id: str
    providers: list[RecordsActorProvider]
    facilities: list[RecordsActorFacility]


class RecordsGrantee(BaseModel):
    type: Literal["provider", "facility"]
    id: str
    name: str
    status: str
    verification_status: str


@records_router.get("/actors/{user_id}")
async def get_records_actor(
    db: Db, _: Service, user_id: str, tenant_id: str = Query(min_length=2, max_length=64)
) -> RecordsActor:
    """The practitioner profiles a user owns and the facilities they are currently staff of."""
    providers = (
        await db.execute(
            select(Provider.id, Provider.status, Provider.verification_status)
            .where(Provider.tenant_id == tenant_id, Provider.user_id == user_id)
            .order_by(Provider.id)
        )
    ).all()
    facilities = (
        await db.execute(
            select(FacilityStaff.facility_id, FacilityStaff.role, Facility.status, Facility.verification_status)
            .join(Facility, Facility.id == FacilityStaff.facility_id)
            .where(FacilityStaff.user_id == user_id, Facility.tenant_id == tenant_id)
            .order_by(FacilityStaff.facility_id)
        )
    ).all()
    return RecordsActor(
        user_id=user_id,
        providers=[RecordsActorProvider(id=i, status=s, verification_status=v) for i, s, v in providers],
        facilities=[RecordsActorFacility(id=i, role=r, status=s, verification_status=v) for i, r, s, v in facilities],
    )


@records_router.get("/grantees/{grantee_type}/{grantee_id}")
async def get_records_grantee(
    db: Db,
    _: Service,
    grantee_type: Literal["provider", "facility"],
    grantee_id: str,
    tenant_id: str = Query(min_length=2, max_length=64),
) -> RecordsGrantee:
    """Whether an organisation exists in the tenant (and its public name), before a customer shares with it."""
    if grantee_type == "provider":
        row = (
            await db.execute(
                select(Provider.display_name, Provider.status, Provider.verification_status).where(
                    Provider.id == grantee_id, Provider.tenant_id == tenant_id
                )
            )
        ).first()
    else:
        row = (
            await db.execute(
                select(Facility.name, Facility.status, Facility.verification_status).where(
                    Facility.id == grantee_id, Facility.tenant_id == tenant_id
                )
            )
        ).first()
    if row is None:
        raise not_found("Grantee")
    name, status, verification_status = row
    return RecordsGrantee(
        type=grantee_type, id=grantee_id, name=name, status=status, verification_status=verification_status
    )
