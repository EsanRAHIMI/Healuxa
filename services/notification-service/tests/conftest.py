from __future__ import annotations

import os

# Simulated edge secret so test identity headers are trusted; forged headers without it are not.
os.environ.setdefault("HEALUXA_EDGE_SECRET", "test-edge-secret")
# Tests drive the delivery worker explicitly (run_once) for determinism.
os.environ["DELIVERY_WORKER_ENABLED"] = "false"
# Never send anything real from tests, whatever the developer's .env says.
for _channel in ("EMAIL", "SMS", "WHATSAPP", "PUSH"):
    os.environ[f"{_channel}_DRIVER"] = "log"
os.environ["ALLOW_REAL_DELIVERY"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from notification_service.infra.db import SessionLocal
from notification_service.main import app, lifespan

_TRUNCATE_SQL = text(
    """
    TRUNCATE TABLE
        deliveries,
        notifications,
        preferences,
        device_tokens,
        recipient_links,
        processed_events
    RESTART IDENTITY CASCADE
    """
)


@pytest.fixture(autouse=True)
async def _reset_notification_tables() -> None:
    async with SessionLocal() as db:
        await db.execute(_TRUNCATE_SQL)
        await db.commit()


@pytest.fixture
async def client():
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client


@pytest.fixture
def worker(client):
    """The app's delivery worker (log drivers), available once the lifespan has started."""
    return app.state.worker
