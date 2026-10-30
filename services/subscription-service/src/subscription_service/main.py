from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.jetstream import subject_for
from healuxa_py_common.events.outbox_sql import SqlOutboxStore
from healuxa_py_common.events.runtime import EventRuntime
from healuxa_py_common.observability.metrics import metrics_payload
from healuxa_py_common.observability.tracing import TraceMiddleware, configure_logging, get_trace_id
from sqlalchemy import text

from subscription_service.api.routes import router
from subscription_service.config import settings
from subscription_service.domain.memberships import handle_payment_event
from subscription_service.infra.db import SessionLocal, engine
from subscription_service.infra.models import OUTBOX

CONSUMED = ("payment.succeeded", "payment.failed", "payment.billing_agreement_updated")


async def consume(envelope: dict[str, Any]) -> None:
    async with SessionLocal() as db, db.begin():
        await handle_payment_event(db, envelope)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    runtime: EventRuntime | None = None
    if settings.nats_enabled:
        runtime = EventRuntime(nats_url=settings.nats_url, service_name=settings.service_name)
        runtime.add_outbox(SqlOutboxStore(SessionLocal, OUTBOX))
        for event_type in CONSUMED:
            runtime.add_consumer(
                DurableConsumer(
                    runtime.connection,
                    subject=subject_for(event_type),
                    durable=f"subscription-service-{event_type.replace('.', '-')}",
                    handler=consume,
                )
            )
        await runtime.start()
    try:
        yield
    finally:
        if runtime is not None:
            await runtime.stop()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Healuxa Subscription Service",
        version="3.4.0",
        description="Plans, memberships and entitlements per subscription.openapi.yaml (disabled until MEMBERSHIPS_ENABLED=true)",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)
    app.include_router(router)

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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        try:
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))
        except Exception as exc:
            return JSONResponse(status_code=503, content={"status": "not_ready", "detail": type(exc).__name__})
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
