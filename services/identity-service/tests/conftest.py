from __future__ import annotations

import os

# Isolate tests from development Postgres (`identity`) and Redis (DB 0). See README.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://healuxa:dev@localhost:5432/identity_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from identity_service.domain.jwt_service import jwt_service
from identity_service.infra.db import SessionLocal, engine
from identity_service.infra.redis_client import close_redis, get_redis
from identity_service.main import app, lifespan

_TRUNCATE_SQL = text(
    """
    TRUNCATE TABLE
        idempotency_records,
        login_history,
        user_roles,
        sessions,
        credentials,
        users,
        jwks_keys
    RESTART IDENTITY CASCADE
    """
)


@pytest.fixture(autouse=True)
async def _reset_identity_tables() -> None:
    """Keep tests independent of dev data and of each other."""
    jwt_service._active_kid = None
    jwt_service._private_pem = None
    try:
        async with SessionLocal() as db:
            await db.execute(_TRUNCATE_SQL)
            await db.commit()
    except Exception as exc:
        pytest.skip(f"identity_test database not ready (run alembic upgrade head): {exc}")
    try:
        redis = await get_redis()
        await redis.flushdb()
    except Exception:
        pass


@pytest.fixture
async def client():
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    jwt_service._active_kid = None
    jwt_service._private_pem = None
    await close_redis()
    await engine.dispose()


@pytest.fixture
def service_headers():
    from identity_service.api.deps import service_auth_headers

    return service_auth_headers()
