from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from healuxa_py_common.events.envelope import EventActor, build_envelope
from healuxa_py_common.events.outbox_sql import enqueue
from sqlalchemy.ext.asyncio import AsyncSession

from appointment_service.config import settings
from appointment_service.infra.models import OUTBOX, Appointment

SCHEMA_BASE = "https://contracts.healuxa.com/events/appointment.schema.json#/$defs/"
APPOINTMENT_EVENTS = {
    "appointment.requested": "AppointmentRequested",
    "appointment.created": "AppointmentCreated",
    "appointment.accepted": "AppointmentAccepted",
    "appointment.declined": "AppointmentDeclined",
    "appointment.completed": "AppointmentCompleted",
    "appointment.no_show": "AppointmentNoShow",
    "appointment.cancelled": "AppointmentCancelled",
    "appointment.rescheduled": "AppointmentRescheduled",
    "appointment.expired": "AppointmentExpired",
    "appointment.reminder_due": "AppointmentReminderDue",
}


def ts(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def base_payload(appointment: Appointment) -> dict[str, Any]:
    """Identifiers and times only — never health data, free text, or price details beyond Money."""
    payload: dict[str, Any] = {
        "appointment_id": appointment.id,
        "user_id": appointment.user_id,
        "provider_id": appointment.provider_id,
        "service_id": appointment.service_id,
        "facility_id": appointment.facility_id,
        "branch_id": appointment.branch_id,
        "scheduled_at": ts(appointment.starts_at),
        "ends_at": ts(appointment.ends_at),
    }
    if appointment.milestone_id:
        payload["milestone_id"] = appointment.milestone_id
    return payload


class EventPublisher:
    """Stages events in the caller's transaction (outbox); the relay publishes them to JetStream."""

    async def publish(
        self,
        *,
        db: AsyncSession,
        event_type: str,
        appointment: Appointment,
        extra: dict[str, Any] | None = None,
        actor: EventActor | None = None,
    ) -> None:
        if event_type not in APPOINTMENT_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")
        envelope = build_envelope(
            event_type=event_type,
            version=1,
            schema_ref=SCHEMA_BASE + APPOINTMENT_EVENTS[event_type],
            tenant_id=appointment.tenant_id,
            producer=settings.service_name,
            payload={**base_payload(appointment), **(extra or {})},
            allowed_producers={settings.service_name},
            actor=actor,
        )
        await enqueue(db, OUTBOX, envelope)


event_publisher = EventPublisher()
