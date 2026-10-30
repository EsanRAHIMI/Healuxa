from __future__ import annotations

from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_sql import enqueue
from sqlalchemy.ext.asyncio import AsyncSession

from subscription_service.config import settings
from subscription_service.infra.models import OUTBOX

SCHEMA_BASE = "https://contracts.healuxa.com/events/subscription.schema.json#/$defs/"
SUBSCRIPTION_EVENTS = {
    "subscription.created": "SubscriptionCreated",
    "subscription.renewed": "SubscriptionRenewed",
    "subscription.upgraded": "SubscriptionUpgraded",
    "subscription.downgraded": "SubscriptionDowngraded",
    "subscription.churned": "SubscriptionChurned",
    "subscription.cancellation_scheduled": "SubscriptionCancellationScheduled",
    "subscription.status_changed": "SubscriptionStatusChanged",
}


async def publish(db: AsyncSession, event_type: str, tenant_id: str, payload: dict[str, Any], actor: EventActor | None = None) -> None:
    if event_type not in SUBSCRIPTION_EVENTS:
        raise ValueError(f"Unsupported event type: {event_type}")
    envelope = build_envelope(
        event_type=event_type,
        version=1,
        schema_ref=SCHEMA_BASE + SUBSCRIPTION_EVENTS[event_type],
        tenant_id=tenant_id,
        producer=settings.service_name,
        payload={k: v for k, v in payload.items() if v is not None},
        allowed_producers={settings.service_name},
        actor=actor,
    )
    await enqueue(db, OUTBOX, envelope)


def money(amount_minor: int, currency: str) -> dict[str, Any]:
    return {"amount_minor": int(amount_minor), "currency": currency}
