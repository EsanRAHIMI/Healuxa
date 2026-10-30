from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.events.runtime import EventRuntime
from healuxa_py_common.observability.metrics import metrics_payload
from healuxa_py_common.observability.tracing import TraceMiddleware, configure_logging, get_trace_id
from sqlalchemy import text

from notification_service.api.notifications import router as notifications_router
from notification_service.channels.drivers import DriverRegistry
from notification_service.config import settings
from notification_service.consumers.handlers import build_consumers
from notification_service.domain.worker import DeliveryWorker
from notification_service.infra.db import SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    # Fails fast on a misconfigured or not-allowed real driver.
    app.state.worker = DeliveryWorker(SessionLocal, DriverRegistry.from_settings(settings), settings)
    runtime: EventRuntime | None = None
    stop = asyncio.Event()
    worker_task: asyncio.Task[None] | None = None
    if settings.nats_enabled:
        # notification-service publishes no events, so the runtime only hosts consumers.
        runtime = EventRuntime(nats_url=settings.nats_url, service_name=settings.service_name)
        for consumer in build_consumers(runtime.connection):
            runtime.add_consumer(consumer)
        await runtime.start()
    if settings.delivery_worker_enabled:
        worker_task = asyncio.create_task(app.state.worker.run_forever(stop))
    try:
        yield
    finally:
        stop.set()
        if worker_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(worker_task, timeout=10)
        if runtime is not None:
            await runtime.stop()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Healuxa Notification Service",
        version="3.4.0",
        description="In-app inbox, multi-channel delivery, preferences and device tokens per notification.openapi.yaml",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)
    app.include_router(notifications_router)

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
