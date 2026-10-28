from __future__ import annotations

import os

# Simulated edge secret so test identity headers are trusted; forged headers without it are not.
os.environ.setdefault("HEALUXA_EDGE_SECRET", "test-edge-secret")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from provider_service.infra.db import SessionLocal
from provider_service.main import app, lifespan

_TRUNCATE_SQL = text(
    """
    TRUNCATE TABLE
        outbox_events,
        availability_exceptions,
        availability_rules,
        operating_hours,
        service_offerings,
        affiliations,
        facility_staff,
        branches,
        credentials,
        facilities,
        providers
    RESTART IDENTITY CASCADE
    """
)


@pytest.fixture(autouse=True)
async def _reset_provider_tables() -> None:
    async with SessionLocal() as db:
        await db.execute(_TRUNCATE_SQL)
        await db.commit()


@pytest.fixture
async def client():
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
