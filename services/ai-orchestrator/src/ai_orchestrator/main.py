from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.events.runtime import EventRuntime
from healuxa_py_common.observability.metrics import metrics_payload
from healuxa_py_common.observability.tracing import TraceMiddleware, configure_logging, get_trace_id
from sqlalchemy import text

from ai_orchestrator.api.sessions import router as sessions_router
from ai_orchestrator.config import settings
from ai_orchestrator.consumers.user_deleted import build_consumer as build_user_deleted_consumer
from ai_orchestrator.infra.db import SessionLocal, engine
from ai_orchestrator.llm import get_llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    runtime: EventRuntime | None = None
    if settings.nats_enabled:
        runtime = EventRuntime(nats_url=settings.nats_url, service_name=settings.service_name)
        runtime.add_consumer(build_user_deleted_consumer(runtime.connection))
        await runtime.start()
    try:
        yield
    finally:
        if runtime is not None:
            await runtime.stop()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Healuxa AI Orchestrator",
        version="3.4.0",
        description="Customer assistant grounded in verified platform data, per ai.openapi.yaml",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)
    app.include_router(sessions_router)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        headers = {}
        retry_after = getattr(exc, "retry_after", None)
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        return JSONResponse(
            status_code=exc.status,
            headers=headers,
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

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo the request body back (FastAPI's default includes `input`): messages are private.
        errors = [{"field": ".".join(str(p) for p in e.get("loc", ())[1:]) or "body", "code": str(e.get("type", "invalid"))} for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=error_response(
                status=422,
                code="validation_error",
                title="Validation failed",
                instance=str(request.url.path),
                trace_id=get_trace_id(),
                errors=errors,  # type: ignore[arg-type]
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
        except Exception:  # noqa: BLE001
            return JSONResponse(status_code=503, content={"status": "not_ready", "detail": "database unavailable"})
        # A missing model key is a degraded mode (messages answer 503), not unreadiness.
        return {"status": "ready", "assistant": "available" if get_llm().available else "unavailable"}

    @app.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
