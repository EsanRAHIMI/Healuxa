from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.observability.metrics import metrics_payload
from healuxa_py_common.observability.tracing import TraceMiddleware, configure_logging, get_trace_id

from profile_service.api.profiles import router as profiles_router
from profile_service.config import settings
from healuxa_py_common.events.outbox_mongo import OUTBOX_COLLECTION, MongoOutboxStore
from healuxa_py_common.events.runtime import EventRuntime

from profile_service.infra.mongo import close_client, ensure_indexes, get_database, ping_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    runtime: EventRuntime | None = None
    if settings.mongodb_uri:
        await ensure_indexes()
        if settings.nats_enabled:
            runtime = EventRuntime(nats_url=settings.nats_url, service_name=settings.service_name)
            runtime.add_outbox(MongoOutboxStore(get_database()[OUTBOX_COLLECTION]))
            await runtime.start()
    try:
        yield
    finally:
        if runtime is not None:
            await runtime.stop()
        await close_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Healuxa Profile Service",
        version="3.3.0",
        description="Customer profiles per profile.openapi.yaml (MongoDB Atlas)",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)
    app.include_router(profiles_router)

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
        if not settings.mongodb_uri:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "detail": "MONGODB_URI not configured"},
            )
        try:
            await ping_database()
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "detail": str(exc)},
            )
        pending = await MongoOutboxStore(get_database()[OUTBOX_COLLECTION]).pending_count()
        return {"status": "ready", "outbox_pending": pending}

    @app.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
