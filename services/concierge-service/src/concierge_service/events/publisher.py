from __future__ import annotations

from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_sql import enqueue
from sqlalchemy.ext.asyncio import AsyncSession

from concierge_service.config import settings
from concierge_service.infra.models import OUTBOX

SCHEMA_BASE = "https://contracts.healuxa.com/events/concierge.schema.json#/$defs/"
CONCIERGE_EVENTS = {
    "concierge.case_submitted": "ConciergeCaseSubmitted",
    "concierge.case_status_changed": "ConciergeCaseStatusChanged",
    "concierge.message_posted": "ConciergeMessagePosted",
}
# Defence in depth: these keys must never reach an event (free text / message bodies / notes).
FORBIDDEN_PAYLOAD_KEYS = frozenset({"body", "needs_note", "reason", "note", "text", "label"})


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
        if event_type not in CONCIERGE_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")
        leaked = FORBIDDEN_PAYLOAD_KEYS & payload.keys()
        if leaked:
            raise ValueError(f"Free-text fields must not be published: {sorted(leaked)}")
        envelope = build_envelope(
            event_type=event_type,
            version=1,
            schema_ref=SCHEMA_BASE + CONCIERGE_EVENTS[event_type],
            tenant_id=tenant_id,
            producer=settings.service_name,
            payload=payload,
            allowed_producers={settings.service_name},
            actor=actor,
        )
        await enqueue(db, OUTBOX, envelope)


event_publisher = EventPublisher()
