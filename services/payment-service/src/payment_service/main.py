from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial

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

from payment_service.api.finance import router as finance_router
from payment_service.api.invoices import router as invoices_router
from payment_service.api.payments import router as payments_router
from payment_service.config import settings
from payment_service.domain.consumers import APPOINTMENT_STATUS, SUBSCRIPTION_EVENTS, dispatch
from payment_service.infra.db import SessionLocal, engine
from payment_service.infra.gateways import get_gateway
from payment_service.infra.models import OUTBOX

CONSUMED = sorted(APPOINTMENT_STATUS) + sorted(SUBSCRIPTION_EVENTS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    get_gateway()  # fail fast on an unsafe/invalid processor configuration
    runtime: EventRuntime | None = None
    if settings.nats_enabled:
        runtime = EventRuntime(nats_url=settings.nats_url, service_name=settings.service_name)
        runtime.add_outbox(SqlOutboxStore(SessionLocal, OUTBOX))
        handler = partial(dispatch, SessionLocal)
        for event_type in CONSUMED:
            runtime.add_consumer(
                DurableConsumer(
                    runtime.connection,
                    subject=subject_for(event_type),
                    durable=f"payment-service-{event_type.replace('.', '-')}",
                    handler=handler,
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
        title="Healuxa Payment Service",
        version="3.4.0",
        description="Quotes, payments, refunds, disputes, ledger, reconciliation and invoices per payment.openapi.yaml",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)
    # Static /payments/* routes (finance, webhooks) must be registered before /payments/{payment_id}.
    app.include_router(finance_router)
    app.include_router(payments_router)
    app.include_router(invoices_router)

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
