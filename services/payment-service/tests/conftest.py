from __future__ import annotations

import os

# Simulated edge secret so test identity headers are trusted; forged headers without it are not.
os.environ.setdefault("HEALUXA_EDGE_SECRET", "test-edge-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/payment_test")
os.environ.setdefault("APP_ENV", "test")
os.environ["PAYMENT_GATEWAY"] = "fake"
os.environ["PAYMENTS_LIVE_MODE"] = "false"
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["STRIPE_PUBLISHABLE_KEY"] = "pk_test_sandbox_placeholder"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_signing_secret_for_unit_tests"
os.environ["MEMBERSHIP_PAYMENTS_ENABLED"] = "true"
os.environ["NATS_ENABLED"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from payment_service.infra.catalog import set_catalog
from payment_service.infra.db import SessionLocal
from payment_service.infra.gateways import set_gateway
from payment_service.infra.gateways.fake import FakeGateway
from payment_service.main import app, lifespan

from helpers import FakeCatalog

_TRUNCATE_SQL = text(
    """
    TRUNCATE TABLE
        outbox_events, ledger_entries, ledger_journals, invoices, invoice_sequences, disputes, refunds,
        payments, quotes, processor_events, consumed_events, idempotency_records, balance_transactions,
        payee_members, processor_customers, appointment_views, membership_views
    RESTART IDENTITY CASCADE
    """
)


@pytest.fixture(autouse=True)
async def _reset_tables() -> None:
    async with SessionLocal() as db:
        await db.execute(_TRUNCATE_SQL)
        await db.commit()


@pytest.fixture
def gateway() -> FakeGateway:
    fake = FakeGateway()
    set_gateway(fake)
    yield fake
    set_gateway(None)


@pytest.fixture
def catalog() -> FakeCatalog:
    fake = FakeCatalog()
    set_catalog(fake)
    yield fake
    set_catalog(None)


@pytest.fixture
async def client(gateway: FakeGateway, catalog: FakeCatalog):
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
