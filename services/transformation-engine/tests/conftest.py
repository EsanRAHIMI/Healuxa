from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://healuxa:dev@localhost:5432/transformation_test",
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from ulid import ULID

from transformation_engine.api.deps import principal_headers
from transformation_engine.infra.db import SessionLocal, engine
from transformation_engine.main import app, lifespan

_TRUNCATE_SQL = text(
    """
    TRUNCATE TABLE
        idempotency_records,
        reassessment_triggers,
        outcome_records,
        next_actions,
        milestones,
        phases,
        goals,
        journeys
    RESTART IDENTITY CASCADE
    """
)


@pytest.fixture(autouse=True)
async def _reset_transformation_tables() -> None:
    try:
        async with SessionLocal() as db:
            await db.execute(_TRUNCATE_SQL)
            await db.commit()
    except Exception as exc:
        pytest.skip(f"transformation_test database not ready (run alembic upgrade head): {exc}")


@pytest.fixture
async def client():
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    await engine.dispose()


@pytest.fixture
def user_id() -> str:
    return str(ULID())


@pytest.fixture
def auth_headers(user_id: str) -> dict[str, str]:
    return principal_headers(user_id)
