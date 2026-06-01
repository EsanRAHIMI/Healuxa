from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    trace_id = _trace_id.get()
    if trace_id:
        return trace_id
    return str(uuid.uuid4())


class TraceIdFilter(logging.Filter):
    """Ensure format strings using %(trace_id)s never fail for third-party loggers."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            current = _trace_id.get()
            record.trace_id = current if current else "-"
        return True


def _attach_trace_id_filter(handler: logging.Handler) -> None:
    if not any(isinstance(item, TraceIdFilter) for item in handler.filters):
        handler.addFilter(TraceIdFilter())


class TraceMiddleware(BaseHTTPMiddleware):
    """Attach trace_id to every request/response per shared X-Trace-Id header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("traceparent") or request.headers.get("X-Trace-Id")
        trace_id = incoming.split("-")[1] if incoming and incoming.startswith("00-") else (
            incoming or str(uuid.uuid4())
        )
        token = _trace_id.set(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            _trace_id.reset(token)


def configure_logging(service_name: str, level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=f"%(asctime)s [{service_name}] %(levelname)s trace_id=%(trace_id)s %(message)s",
    )
    root = logging.getLogger()
    for handler in root.handlers:
        _attach_trace_id_filter(handler)
