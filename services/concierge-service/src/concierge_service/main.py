from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.events.outbox_sql import SqlOutboxStore
from healuxa_py_common.events.runtime import EventRuntime
from healuxa_py_common.observability.metrics import metrics_payload
from healuxa_py_common.observability.tracing import TraceMiddleware, configure_logging, get_trace_id
from sqlalchemy import text

from concierge_service.api.cases import router as cases_router
from concierge_service.config import settings
from concierge_service.infra.db import SessionLocal, engine
from concierge_service.infra.models import OUTBOX


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    runtime: EventRuntime | None = None
    if settings.nats_enabled:
        runtime = EventRuntime(nats_url=settings.nats_url, service_name=settings.service_name)
        runtime.add_outbox(SqlOutboxStore(SessionLocal, OUTBOX))
        await runtime.start()
    try:
        yield
    finally:
        if runtime is not None:
            await runtime.stop()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Healuxa Concierge Service",
        version="1.0.0",
        description="Concierge cases, coordinator queue, provider options and secure messaging per concierge.openapi.yaml",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)
    app.include_router(cases_router)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=error_response(
                status=exc.status,
                code=exc.code,
                title=exc.title,
                detail=exc.detail,
                instance=str(request.url.path),
                trace_id=get_trace_id(),
                errors=exc.errors,
            ),
        )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    async def ready():
        try:
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
