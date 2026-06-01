from __future__ import annotations

import json
import logging
from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope

from transformation_engine.config import settings

logger = logging.getLogger(__name__)

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
    async def publish(
        self,
        *,
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
        if not settings.nats_enabled:
            logger.info("event published (log-only): %s", envelope.type)
            return
        try:
            import nats

            nc = await nats.connect(settings.nats_url, connect_timeout=1)
            subject = f"healuxa.{event_type}.v1"
            await nc.publish(subject, json.dumps(envelope.model_dump(mode="json")).encode())
            await nc.drain()
        except Exception:
            logger.info("event published (log-only fallback): %s", envelope.type)


event_publisher = EventPublisher()
