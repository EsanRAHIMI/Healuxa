from __future__ import annotations

from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_mongo import OUTBOX_COLLECTION, enqueue
from pymongo.asynchronous.client_session import AsyncClientSession

from profile_service.config import settings
from profile_service.infra.mongo import get_database

PROFILE_EVENTS = {"profile.updated"}

SCHEMA_REFS = {
    "profile.updated": "https://contracts.healuxa.com/events/profile.schema.json#/$defs/ProfileUpdated",
}


class EventPublisher:
    """Stages events in the transactional outbox; the relay publishes them to JetStream."""

    async def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        session: AsyncClientSession | None,
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
        await enqueue(get_database()[OUTBOX_COLLECTION], envelope, session=session)


event_publisher = EventPublisher()
