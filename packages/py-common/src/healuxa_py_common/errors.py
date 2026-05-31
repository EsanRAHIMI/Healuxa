from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ErrorCode = Literal[
    "validation_error",
    "unauthorized",
    "forbidden",
    "not_found",
    "conflict",
    "idempotency_conflict",
    "rate_limited",
    "unprocessable",
    "internal_error",
    "service_unavailable",
]


class FieldError(BaseModel):
    field: str
    code: str
    message: str | None = None


class ErrorBody(BaseModel):
    """RFC 9457-compatible error per packages/api-contracts/openapi/_shared/components.yaml."""

    code: ErrorCode
    title: str
    status: int
    trace_id: str
    type: str | None = None
    detail: str | None = None
    instance: str | None = None
    errors: list[FieldError] | None = None


class ApiError(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: ErrorCode,
        title: str,
        detail: str | None = None,
        instance: str | None = None,
        errors: list[FieldError] | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.instance = instance
        self.errors = errors
        super().__init__(title)


def error_response(
    *,
    status: int,
    code: ErrorCode,
    title: str,
    trace_id: str,
    detail: str | None = None,
    instance: str | None = None,
    errors: list[FieldError] | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    body = ErrorBody(
        type=error_type or f"https://errors.healuxa.com/{code}",
        title=title,
        status=status,
        code=code,
        detail=detail,
        instance=instance,
        trace_id=trace_id,
        errors=errors,
    )
    return body.model_dump(exclude_none=True)
