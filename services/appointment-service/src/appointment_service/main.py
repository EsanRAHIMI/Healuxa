from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.events.outbox_sql import SqlOutboxStore
from healuxa_py_common.events.runtime import EventRuntime
from healuxa_py_common.observability.metrics import metrics_payload
from healuxa_py_common.observability.tracing import TraceMiddleware, configure_logging, get_trace_id
from sqlalchemy import text

from appointment_service.api.appointments import router as appointments_router
from appointment_service.clients.provider_directory import HttpProviderDirectory, ServiceTokenSource
from appointment_service.config import settings
from appointment_service.consumers.payments import build_consumers as build_payment_consumers
from appointment_service.domain.sweeper import run_forever
from appointment_service.infra.db import SessionLocal, engine
from appointment_service.infra.models import OUTBOX


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    http = httpx.AsyncClient(timeout=httpx.Timeout(settings.provider_timeout_seconds))
    tokens = ServiceTokenSource(
        client=http,
        token_url=settings.identity_service_token_url,
        client_id=settings.service_auth_client_id,
        client_secret=settings.service_auth_client_secret,
    )
    app.state.directory = HttpProviderDirectory(client=http, base_url=settings.provider_service_url, tokens=tokens)

    runtime: EventRuntime | None = None
    if settings.nats_enabled:
        runtime = EventRuntime(nats_url=settings.nats_url, service_name=settings.service_name)
        runtime.add_outbox(SqlOutboxStore(SessionLocal, OUTBOX))
        for consumer in build_payment_consumers(runtime.connection):
            runtime.add_consumer(consumer)
        await runtime.start()
    stop = asyncio.Event()
    sweeper: asyncio.Task[None] | None = None
    if settings.sweeper_enabled:
        sweeper = asyncio.create_task(run_forever(SessionLocal, stop))
    try:
        yield
    finally:
        stop.set()
        if sweeper is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(sweeper, timeout=10)
        if runtime is not None:
            await runtime.stop()
        await http.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Healuxa Appointment Service",
        version="3.4.0",
        description="Booking engine: slots, holds, confirmation, lifecycle and reminders per appointment.openapi.yaml",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)
    app.include_router(appointments_router)

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
            return JSONResponse(status_code=503, content={"status": "not_ready", "detail": str(exc)})
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
