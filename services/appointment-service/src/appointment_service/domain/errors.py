from __future__ import annotations

from healuxa_py_common.errors import ApiError


def forbidden(detail: str) -> ApiError:
    return ApiError(status=403, code="forbidden", title="Forbidden", detail=detail)


def not_found(what: str) -> ApiError:
    return ApiError(status=404, code="not_found", title="Not found", detail=f"{what} not found")


def unprocessable(detail: str, field: str | None = None) -> ApiError:
    errors = [{"field": field, "code": "invalid", "message": detail}] if field else None
    return ApiError(status=422, code="unprocessable", title="Unprocessable", detail=detail, errors=errors)


def conflict(detail: str) -> ApiError:
    return ApiError(status=409, code="conflict", title="Conflict", detail=detail)


def idempotency_conflict() -> ApiError:
    return ApiError(
        status=409,
        code="idempotency_conflict",
        title="Idempotency conflict",
        detail="Idempotency-Key was already used with a different request",
    )


def unavailable(detail: str = "Availability source (provider-service) is unavailable") -> ApiError:
    return ApiError(status=503, code="service_unavailable", title="Service unavailable", detail=detail)
