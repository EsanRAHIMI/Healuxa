from __future__ import annotations

from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_sql import enqueue
from sqlalchemy.ext.asyncio import AsyncSession
from identity_service.config import settings
from identity_service.infra.models import OUTBOX

IDENTITY_EVENTS = {
    "auth.user_registered": {"identity-service"},
    "auth.session_revoked": {"identity-service"},
    "auth.security_event": {"identity-service"},
    "auth.user_deleted": {"identity-service"},
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
        await enqueue(db, OUTBOX, envelope)

event_publisher = EventPublisher()
