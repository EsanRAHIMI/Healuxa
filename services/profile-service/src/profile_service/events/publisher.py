from __future__ import annotations

import json
import logging
from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope

from profile_service.config import settings

logger = logging.getLogger(__name__)

PROFILE_EVENTS = {"profile.updated"}

SCHEMA_REFS = {
    "profile.updated": "https://contracts.healuxa.com/events/profile.schema.json#/$defs/ProfileUpdated",
}


class EventPublisher:
    async def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: str | None = None,
        actor: EventActor | None = None,
    ) -> None:
        if event_type not in PROFILE_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")

        envelope = build_envelope(
            event_type=event_type,
            version=1,
            schema_ref=SCHEMA_REFS[event_type],
            tenant_id=tenant_id or settings.tenant_default,
            producer=settings.service_name,
            payload=payload,
            allowed_producers={settings.service_name},
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
