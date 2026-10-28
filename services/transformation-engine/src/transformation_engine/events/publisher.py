from __future__ import annotations

from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_sql import enqueue
from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.config import settings
from transformation_engine.infra.models import OUTBOX

TRANSFORMATION_EVENTS = {
    "journey.created",
    "journey.milestone_completed",
    "journey.reassessment_due",
}

SCHEMA_REFS = {
    "journey.created": "https://contracts.healuxa.com/events/journey.schema.json#/$defs/JourneyCreated",
    "journey.milestone_completed": "https://contracts.healuxa.com/events/journey.schema.json#/$defs/JourneyMilestoneCompleted",
    "journey.reassessment_due": "https://contracts.healuxa.com/events/journey.schema.json#/$defs/JourneyReassessmentDue",
}


class EventPublisher:
    """Stages events in the caller's transaction (outbox); the relay publishes them to JetStream."""

    async def publish(
        self,
        *,
        db: AsyncSession,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        actor: EventActor | None = None,
    ) -> None:
        if event_type not in TRANSFORMATION_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")

        envelope = build_envelope(
            event_type=event_type,
            version=1,
            schema_ref=SCHEMA_REFS[event_type],
            tenant_id=tenant_id or settings.tenant_default,
            producer=settings.service_name,
            payload=payload,
            allowed_producers={settings.service_name},
            correlation_id=correlation_id,
            actor=actor,
        )
        await enqueue(db, OUTBOX, envelope)

event_publisher = EventPublisher()
