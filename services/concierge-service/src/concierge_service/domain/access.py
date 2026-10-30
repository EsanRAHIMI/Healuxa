"""Authorization rules (ABAC) layered on top of RBAC permissions from identity-service.

Roles on a case are derived, never claimed:
- ``customer``: the case owner (same tenant, ``customer_id == principal.user_id``).
- ``coordinator``: holds ``concierge:coordinate`` in the case's tenant.
- ``supervisor``: holds ``concierge:supervise`` in the case's tenant.
Anyone else gets 404 so case existence never leaks.
"""

from __future__ import annotations

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal

from concierge_service.infra.models import ConciergeCase

REQUEST_PERMISSION = "concierge:request"
COORDINATE_PERMISSION = "concierge:coordinate"
SUPERVISE_PERMISSION = "concierge:supervise"


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


def is_supervisor(principal: Principal) -> bool:
    return SUPERVISE_PERMISSION in principal.permissions


def is_coordinator(principal: Principal) -> bool:
    return COORDINATE_PERMISSION in principal.permissions or is_supervisor(principal)


def case_role(principal: Principal, case: ConciergeCase) -> str | None:
    """The strongest role the principal holds on this case, or None (→ 404)."""
    if case.tenant_id != principal.tenant_id:
        return None
    if is_supervisor(principal):
        return "supervisor"
    if COORDINATE_PERMISSION in principal.permissions:
        return "coordinator"
    if case.customer_id == principal.user_id and REQUEST_PERMISSION in principal.permissions:
        return "customer"
    return None


def require_case_role(principal: Principal, case: ConciergeCase | None, *roles: str) -> str:
    role = case_role(principal, case) if case is not None else None
    if role is None:
        raise not_found("Case")
    if roles and role not in roles:
        # The caller can see the case but may not perform this action on it.
        raise forbidden("Requires one of: " + ", ".join(roles))
    return role


def messaging_role(principal: Principal, case: ConciergeCase | None) -> str:
    """Secure messaging is strictly between the case customer and its assigned coordinator."""
    if case is None or case.tenant_id != principal.tenant_id:
        raise not_found("Case")
    if case.customer_id == principal.user_id and REQUEST_PERMISSION in principal.permissions:
        return "customer"
    if case.coordinator_id == principal.user_id and is_coordinator(principal):
        return "coordinator"
    raise not_found("Case")
