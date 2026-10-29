from __future__ import annotations

from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_sql import enqueue
from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.config import settings
from payment_service.infra.models import OUTBOX

SCHEMA_BASE = "https://contracts.healuxa.com/events/payment.schema.json#/$defs/"
PAYMENT_EVENTS = {
    "payment.authorized": "PaymentAuthorized",
    "payment.succeeded": "PaymentSucceeded",
    "payment.failed": "PaymentFailed",
    "payment.canceled": "PaymentCanceled",
    "payment.refunded": "PaymentRefunded",
    "payment.dispute_opened": "PaymentDisputeOpened",
    "payment.dispute_closed": "PaymentDisputeClosed",
    "payment.invoice_issued": "PaymentInvoiceIssued",
    "payment.billing_agreement_updated": "PaymentBillingAgreementUpdated",
    "commission.computed": "CommissionComputed",
}

# Defence in depth: these keys must never appear in any payload (card data, processor secrets, health data).
FORBIDDEN_KEYS = {"card", "pan", "cvc", "cvv", "card_number", "exp_month", "exp_year", "last4", "client_secret", "description", "service_name"}


def _check(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden key in event payload: {key}")
            _check(value)
    elif isinstance(payload, list):
        for item in payload:
            _check(item)


class EventPublisher:
    """Stages events in the caller's transaction (outbox); the relay publishes them to JetStream."""

    async def publish(
        self,
        *,
        db: AsyncSession,
        event_type: str,
        tenant_id: str,
        payload: dict[str, Any],
        actor: EventActor | None = None,
    ) -> None:
        if event_type not in PAYMENT_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")
        clean = {k: v for k, v in payload.items() if v is not None}
        _check(clean)
        envelope = build_envelope(
            event_type=event_type,
            version=1,
            schema_ref=SCHEMA_BASE + PAYMENT_EVENTS[event_type],
            tenant_id=tenant_id,
            producer=settings.service_name,
            payload=clean,
            allowed_producers={settings.service_name},
            actor=actor,
        )
        await enqueue(db, OUTBOX, envelope)


event_publisher = EventPublisher()


def money(amount_minor: int, currency: str) -> dict[str, Any]:
    return {"amount_minor": int(amount_minor), "currency": currency}
