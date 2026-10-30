from __future__ import annotations

import os

# Isolate tests from development data; the edge secret makes test identity headers trusted (forged ones
# without it are not); the sweeper is exercised directly instead of on a timer.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/appointment_test")
os.environ.setdefault("HEALUXA_EDGE_SECRET", "test-edge-secret")
os.environ.setdefault("IDENTITY_INTROSPECT_URL", "http://127.0.0.1:1/v1/auth/introspect")
os.environ["SWEEPER_ENABLED"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from appointment_service.api.deps import get_directory
from appointment_service.config import settings
from appointment_service.domain.clock import clock
from appointment_service.infra.db import SessionLocal
from appointment_service.main import app, lifespan
from helpers import NOW, FakeDirectory

_TRUNCATE_SQL = text(
    """
    TRUNCATE TABLE
        outbox_events,
        appointment_reminders,
        appointment_transitions,
        appointments
    RESTART IDENTITY CASCADE
    """
)


@pytest.fixture(autouse=True)
async def _reset_tables() -> None:
    async with SessionLocal() as db:
        await db.execute(_TRUNCATE_SQL)
        await db.commit()


@pytest.fixture(autouse=True)
def _frozen_clock():
    clock.freeze(NOW)
    yield
    clock.reset()


@pytest.fixture(autouse=True)
def _default_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin booking policy so tests do not depend on a developer's .env.
    monkeypatch.setattr(settings, "hold_ttl_minutes", 10)
    monkeypatch.setattr(settings, "max_active_holds_per_customer", 3)
    monkeypatch.setattr(settings, "slot_interval_minutes", 15)
    monkeypatch.setattr(settings, "min_lead_minutes", 60)
    monkeypatch.setattr(settings, "max_horizon_days", 90)
    monkeypatch.setattr(settings, "customer_cancel_cutoff_minutes", 120)
    monkeypatch.setattr(settings, "check_in_opens_minutes", 60)
    monkeypatch.setattr(settings, "no_show_grace_minutes", 15)
    monkeypatch.setattr(settings, "reminder_offsets_minutes", [1440, 120])
    monkeypatch.setattr(settings, "payment_required", False)


@pytest.fixture
def directory() -> FakeDirectory:
    return FakeDirectory()


@pytest.fixture
async def client(directory: FakeDirectory):
    async with lifespan(app):
        app.dependency_overrides[get_directory] = lambda: directory
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as async_client:
                yield async_client
        finally:
            app.dependency_overrides.clear()
