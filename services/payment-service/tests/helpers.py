from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from payment_service.api.deps import principal_headers
from payment_service.config import settings
from payment_service.domain.consumers import handle_appointment_event, handle_subscription_event
from payment_service.infra.catalog import Offering
from payment_service.infra.db import SessionLocal
from payment_service.infra.gateways.stripe import signature_header
from payment_service.infra.models import OUTBOX

CUSTOMER_PERMS = "payments:create,payments:read,invoices:read"
STAFF_PERMS = "payments:create,payments:read,invoices:read,payments:manage,payments:refund,finance:reconcile"
WEBHOOK_SECRET = settings.stripe_webhook_secret


def new_id() -> str:
    return str(ULID())


def customer(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=CUSTOMER_PERMS, tenant_id=tenant_id)


def staff(*, tenant_id: str | None = None, permissions: str = STAFF_PERMS) -> dict[str, str]:
    return principal_headers(new_id(), permissions=permissions, tenant_id=tenant_id)


class FakeCatalog:
    def __init__(self) -> None:
        self.offerings: dict[str, Offering] = {}

    def add(self, *, professional: int = 50_000, facility: int = 20_000, price_type: str = "fixed", status: str = "active",
            provider_id: str | None = None, facility_id: str | None = "auto") -> Offering:
        offering = Offering(
            id=new_id(),
            provider_id=provider_id or new_id(),
            facility_id=new_id() if facility_id == "auto" else facility_id,
            status=status,
            price_type=price_type,
            professional_fee_minor=professional,
            facility_fee_minor=facility,
            currency="AED",
        )
        self.offerings[offering.id] = offering
        return offering

    async def get_offering(self, service_id: str) -> Offering | None:
        return self.offerings.get(service_id)


def envelope(event_type: str, payload: dict[str, Any], *, tenant_id: str = "healuxa-dubai") -> dict[str, Any]:
    return {"event_id": new_id(), "type": event_type, "version": 1, "tenant_id": tenant_id, "producer": "test", "payload": payload,
            "occurred_at": datetime.now(UTC).isoformat()}


async def appointment_event(event_type: str, appointment: dict[str, Any], *, tenant_id: str = "healuxa-dubai") -> dict:
    env = envelope(event_type, appointment, tenant_id=tenant_id)
    await handle_appointment_event(SessionLocal, env)
    return env


async def subscription_event(event_type: str, payload: dict[str, Any], *, tenant_id: str = "healuxa-dubai") -> dict:
    env = envelope(event_type, payload, tenant_id=tenant_id)
    await handle_subscription_event(SessionLocal, env)
    return env


async def booked_appointment(catalog: FakeCatalog, user_id: str, *, hours_ahead: int = 72, **offering_kw) -> tuple[dict, Offering]:
    offering = catalog.add(**offering_kw)
    appointment = {
        "appointment_id": new_id(),
        "user_id": user_id,
        "provider_id": offering.provider_id,
        "service_id": offering.id,
        "scheduled_at": (datetime.now(UTC) + timedelta(hours=hours_ahead)).isoformat(),
        "requested_at": datetime.now(UTC).isoformat(),
    }
    await appointment_event("appointment.requested", appointment)
    return appointment, offering


async def ok(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


async def quote_for(client: AsyncClient, user_id: str, appointment: dict) -> dict:
    return await ok(
        await client.post(
            "/v1/payment-quotes",
            json={"subject_type": "appointment", "subject_id": appointment["appointment_id"]},
            headers=customer(user_id),
        ),
        201,
    )


async def create_payment(client: AsyncClient, user_id: str, quote_id: str, *, key: str | None = None, capture_method: str | None = None) -> dict:
    body: dict[str, Any] = {"quote_id": quote_id}
    if capture_method:
        body["capture_method"] = capture_method
    return await ok(
        await client.post("/v1/payments", json=body, headers={**customer(user_id), "Idempotency-Key": key or f"key-{new_id()}"}),
        201,
    )


def stripe_event(event_type: str, obj: dict[str, Any], *, event_id: str | None = None, created: int | None = None, livemode: bool = False) -> dict:
    return {
        "id": event_id or f"evt_{new_id()}",
        "object": "event",
        "type": event_type,
        "created": created if created is not None else int(time.time()),
        "livemode": livemode,
        "data": {"object": obj},
    }


async def send_webhook(client: AsyncClient, event: dict, *, secret: str = WEBHOOK_SECRET, timestamp: int | None = None,
                       raw: bytes | None = None, header: str | None = None):
    body = raw if raw is not None else json.dumps(event).encode()
    sig = header if header is not None else signature_header(secret, body, timestamp)
    return await client.post("/v1/payments/webhooks/stripe", content=body, headers={"Stripe-Signature": sig, "Content-Type": "application/json"})


async def pi_event(client: AsyncClient, gateway, pi_id: str, outcome: str, *, created: int | None = None, event_type: str | None = None):
    obj = gateway.confirm(pi_id, outcome)
    event_type = event_type or {
        "authorized": "payment_intent.amount_capturable_updated",
        "succeeded": "payment_intent.succeeded",
        "failed": "payment_intent.payment_failed",
        "processing": "payment_intent.processing",
    }[outcome]
    response = await send_webhook(client, stripe_event(event_type, obj, created=created))
    assert response.status_code == 204, response.text
    return obj


async def paid_appointment(client: AsyncClient, gateway, catalog: FakeCatalog, user_id: str, **kw) -> dict:
    """Customer books, pays (automatic capture) and Stripe confirms via webhook."""
    appointment, offering = await booked_appointment(catalog, user_id, **kw)
    quote = await quote_for(client, user_id, appointment)
    payment = await create_payment(client, user_id, quote["id"], capture_method="automatic")
    pi_id = gateway.calls[-1] and _last_pi(gateway)
    await pi_event(client, gateway, pi_id, "succeeded")
    fresh = await ok(await client.get(f"/v1/payments/{payment['id']}", headers=customer(user_id)))
    return {"appointment": appointment, "offering": offering, "quote": quote, "payment": fresh, "pi_id": pi_id}


def _last_pi(gateway) -> str:
    return list(gateway.payment_intents)[-1]


def last_pi(gateway) -> str:
    return _last_pi(gateway)


async def outbox(event_type: str | None = None) -> list[dict]:
    async with SessionLocal() as db:
        query = select(OUTBOX.c.body).order_by(OUTBOX.c.created_at)
        if event_type:
            query = query.where(OUTBOX.c.event_type == event_type)
        return [row.body for row in await db.execute(query)]
