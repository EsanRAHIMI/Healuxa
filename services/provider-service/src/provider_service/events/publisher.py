from __future__ import annotations

from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_sql import enqueue
from sqlalchemy.ext.asyncio import AsyncSession

from provider_service.config import settings
from provider_service.infra.models import OUTBOX

SCHEMA_BASE = "https://contracts.healuxa.com/events/catalog.schema.json#/$defs/"
CATALOG_EVENTS = {
    "catalog.provider_status_changed": "CatalogProviderStatusChanged",
    "catalog.facility_status_changed": "CatalogFacilityStatusChanged",
    "catalog.affiliation_changed": "CatalogAffiliationChanged",
    "catalog.availability_changed": "CatalogAvailabilityChanged",
    "catalog.facility_staff_changed": "CatalogFacilityStaffChanged",
}


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
        if event_type not in CATALOG_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")
        envelope = build_envelope(
            event_type=event_type,
            version=1,
            schema_ref=SCHEMA_BASE + CATALOG_EVENTS[event_type],
            tenant_id=tenant_id,
            producer=settings.service_name,
            payload=payload,
            allowed_producers={settings.service_name},
            actor=actor,
        )
        await enqueue(db, OUTBOX, envelope)


event_publisher = EventPublisher()
