"""Authorization rules (ABAC) layered on top of RBAC permissions from identity-service."""

from __future__ import annotations

from collections.abc import Iterable

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from provider_service.infra.models import FacilityStaff, Provider

PROVIDER_STAFF_PERMISSION = "providers:verify"
FACILITY_STAFF_PERMISSION = "facilities:verify"


def forbidden(detail: str) -> ApiError:
    return ApiError(status=403, code="forbidden", title="Forbidden", detail=detail)


def not_found(what: str) -> ApiError:
    return ApiError(status=404, code="not_found", title="Not found", detail=f"{what} not found")


def unprocessable(detail: str, field: str | None = None) -> ApiError:
    errors = [{"field": field, "code": "invalid", "message": detail}] if field else None
    return ApiError(status=422, code="unprocessable", title="Unprocessable", detail=detail, errors=errors)


def conflict(detail: str) -> ApiError:
    return ApiError(status=409, code="conflict", title="Conflict", detail=detail)


def actor_of(principal: Principal) -> EventActor:
    return EventActor(type="user", id=principal.user_id)


def is_provider_staff(principal: Principal | None) -> bool:
    return principal is not None and PROVIDER_STAFF_PERMISSION in principal.permissions


def is_facility_staff(principal: Principal | None) -> bool:
    return principal is not None and FACILITY_STAFF_PERMISSION in principal.permissions


def owns_provider(principal: Principal | None, provider: Provider) -> bool:
    return principal is not None and provider.user_id == principal.user_id


async def facility_role(db: AsyncSession, principal: Principal | None, facility_id: str) -> str | None:
    if principal is None:
        return None
    return await db.scalar(
        select(FacilityStaff.role).where(
            FacilityStaff.facility_id == facility_id, FacilityStaff.user_id == principal.user_id
        )
    )


async def require_facility_role(
    db: AsyncSession, principal: Principal, facility_id: str, roles: Iterable[str]
) -> str:
    """Facility membership with one of ``roles``; platform facility staff always pass."""
    if is_facility_staff(principal):
        return "platform_staff"
    role = await facility_role(db, principal, facility_id)
    if role not in set(roles):
        raise forbidden("Requires a facility role: " + ", ".join(sorted(roles)))
    return role
