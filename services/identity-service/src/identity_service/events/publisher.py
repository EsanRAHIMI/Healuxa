from __future__ import annotations

import json
import logging
from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from identity_service.config import settings

logger = logging.getLogger(__name__)

IDENTITY_EVENTS = {
    "auth.user_registered": {"identity-service"},
    "auth.session_revoked": {"identity-service"},
    "auth.security_event": {"identity-service"},
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
        envelope = build_envelope(
            event_type=event_type,
            version=1,
            schema_ref=f"https://contracts.healuxa.com/events/{event_type.replace('.', '/')}/v1",
            tenant_id=tenant_id or settings.tenant_default,
            producer=settings.service_name,
            payload=payload,
            allowed_producers=IDENTITY_EVENTS[event_type],
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
