"""Authorization rules (ABAC) layered on RBAC permissions from identity-service."""

from __future__ import annotations

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal

MANAGE = "payments:manage"
REFUND = "payments:refund"
RECONCILE = "finance:reconcile"


def forbidden(detail: str) -> ApiError:
    return ApiError(status=403, code="forbidden", title="Forbidden", detail=detail)


def not_found(what: str) -> ApiError:
    return ApiError(status=404, code="not_found", title="Not found", detail=f"{what} not found")


def unprocessable(detail: str, field: str | None = None) -> ApiError:
    errors = [{"field": field, "code": "invalid", "message": detail}] if field else None
    return ApiError(status=422, code="unprocessable", title="Unprocessable", detail=detail, errors=errors)


def conflict(detail: str, code: str = "conflict") -> ApiError:
    return ApiError(status=409, code=code, title="Conflict", detail=detail)  # type: ignore[arg-type]


def bad_request(detail: str, field: str | None = None) -> ApiError:
    errors = [{"field": field, "code": "required", "message": detail}] if field else None
    return ApiError(status=400, code="validation_error", title="Bad request", detail=detail, errors=errors)


def processor_unavailable() -> ApiError:
    return ApiError(
        status=503,
        code="service_unavailable",
        title="Service unavailable",
        detail="Payment processor unavailable; retry with the same Idempotency-Key",
    )


def actor_of(principal: Principal) -> EventActor:
    return EventActor(type="user", id=principal.user_id)


def is_manager(principal: Principal) -> bool:
    return MANAGE in principal.permissions


def is_finance(principal: Principal) -> bool:
    return RECONCILE in principal.permissions


def can_see_payment(principal: Principal, *, tenant_id: str, user_id: str) -> bool:
    """Owner, or payments/finance staff of the same tenant. Callers turn False into 404 (no existence leak)."""
    if principal.tenant_id != tenant_id:
        return False
    return principal.user_id == user_id or is_manager(principal) or is_finance(principal) or REFUND in principal.permissions
