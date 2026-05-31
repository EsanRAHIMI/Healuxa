from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from identity_service.domain.jwt_service import jwt_service
from identity_service.infra.db import SessionLocal, engine
from identity_service.infra.redis_client import close_redis, get_redis
from identity_service.main import app, lifespan


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


@pytest.fixture
def requires_integration():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL required for integration tests")
