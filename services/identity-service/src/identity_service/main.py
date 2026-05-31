from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.observability.metrics import metrics_payload
from healuxa_py_common.observability.tracing import TraceMiddleware, configure_logging, get_trace_id
from identity_service.api.auth import router as auth_router
from identity_service.api.deps import get_db
from identity_service.api.iam import router as iam_router
from identity_service.api.sessions import router as sessions_router
from identity_service.api.well_known import router as well_known_router
from identity_service.config import settings
from identity_service.domain.jwt_service import jwt_service
from identity_service.domain.security import hash_client_secret
from identity_service.infra.db import SessionLocal, engine
from identity_service.infra.models import ServiceClient
from identity_service.infra.redis_client import close_redis, get_redis
from sqlalchemy import text


async def _seed_service_client() -> None:
    async with SessionLocal() as db:
        existing = await db.get(ServiceClient, settings.service_auth_client_id)
        if existing:
            return
        db.add(
            ServiceClient(
                client_id=settings.service_auth_client_id,
                client_secret_hash=hash_client_secret(settings.service_auth_client_secret),
                name="Healuxa internal mesh",
                scopes=["service"],
            )
        )
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    async with SessionLocal() as db:
        await jwt_service.ensure_active_key(db)
    await _seed_service_client()
    yield
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Healuxa Identity Service",
        version="3.3.0",
        description="Enterprise IAM — Open Host Service per identity.openapi.yaml",
        lifespan=lifespan,
    )
    app.add_middleware(TraceMiddleware)

    app.include_router(auth_router)
    app.include_router(well_known_router)
    app.include_router(sessions_router)
    app.include_router(iam_router)

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
            redis = await get_redis()
            await redis.ping()
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "detail": str(exc)},
            )
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
