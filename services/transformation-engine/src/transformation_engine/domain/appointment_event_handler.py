"""Keeps journey steps in step with the appointments booked for them.

The appointment service is the only booking engine; this handler is a downstream projection of its
events onto the Journey aggregate. A booking names its step through ``milestone_id``; events
without one concern appointments outside any journey and are ignored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from healuxa_py_common.events.envelope import EventActor
from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.domain.progress import complete_milestone
from transformation_engine.domain.security import utcnow
from transformation_engine.infra.event_models import CONSUMER_NAME, OUTCOME_ACKED, OUTCOME_REJECTED, OUTCOME_SKIPPED
from transformation_engine.infra.event_repository import is_event_processed, record_processed_event
from transformation_engine.infra.models import Journey, Milestone

logger = logging.getLogger(__name__)

APPOINTMENT_PRODUCER = "appointment-service"

SCHEDULING_EVENTS = frozenset(
    {"appointment.requested", "appointment.created", "appointment.accepted", "appointment.rescheduled"}
)
RELEASING_EVENTS = frozenset(
    {"appointment.cancelled", "appointment.declined", "appointment.expired", "appointment.no_show"}
)
COMPLETING_EVENT = "appointment.completed"
HANDLED_EVENTS = SCHEDULING_EVENTS | RELEASING_EVENTS | {COMPLETING_EVENT}

DETAIL_INVALID_ENVELOPE = "invalid_envelope"
DETAIL_UNKNOWN_MILESTONE = "unknown_milestone"
DETAIL_NOT_OWNER = "milestone_not_owned_by_user"
DETAIL_ALREADY_COMPLETED = "milestone_already_completed"
DETAIL_OTHER_APPOINTMENT = "milestone_linked_to_other_appointment"


@dataclass(frozen=True)
class AppointmentEventResult:
    outcome: str
    detail: str | None = None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class AppointmentEventHandler:
    async def handle(self, envelope: dict[str, Any], *, db: AsyncSession) -> AppointmentEventResult:
        event_type = envelope.get("type")
        if event_type not in HANDLED_EVENTS:
            return AppointmentEventResult(OUTCOME_SKIPPED, "unhandled_type")

        payload = envelope.get("payload")
        event_id = envelope.get("event_id")
        tenant_id = envelope.get("tenant_id")
        valid = (
            isinstance(payload, dict)
            and isinstance(event_id, str)
            and 16 <= len(event_id) <= 36
            and isinstance(tenant_id, str)
            and envelope.get("producer") == APPOINTMENT_PRODUCER
            and isinstance(payload.get("appointment_id"), str)
            and isinstance(payload.get("user_id"), str)
        )
        if not valid:
            # Log nothing taken from the envelope: it carries user identifiers.
            logger.warning("appointment event rejected: invalid envelope")
            return AppointmentEventResult(OUTCOME_REJECTED, DETAIL_INVALID_ENVELOPE)

        milestone_id = payload.get("milestone_id")
        if not isinstance(milestone_id, str) or not milestone_id:
            return AppointmentEventResult(OUTCOME_SKIPPED, "no_milestone")

        if await is_event_processed(db, event_id):
            return AppointmentEventResult(OUTCOME_ACKED, "already_processed")

        outcome, detail = await self._apply(db, event_type, tenant_id, payload, milestone_id)
        await record_processed_event(
            db, event_id=event_id, event_type=event_type, tenant_id=tenant_id, outcome=outcome, detail=detail
        )
        await db.commit()
        return AppointmentEventResult(outcome, detail)

    async def _apply(
        self,
        db: AsyncSession,
        event_type: str,
        tenant_id: str,
        payload: dict[str, Any],
        milestone_id: str,
    ) -> tuple[str, str | None]:
        # Row lock: events for one step may be processed concurrently by several instances.
        milestone = await db.get(Milestone, milestone_id, with_for_update=True) if len(milestone_id) <= 26 else None
        if milestone is None:
            return OUTCOME_SKIPPED, DETAIL_UNKNOWN_MILESTONE
        journey = await db.get(Journey, milestone.journey_id)
        # milestone_id is supplied by the booking client, so ownership is verified here.
        if journey is None or journey.tenant_id != tenant_id or journey.user_id != payload["user_id"]:
            return OUTCOME_SKIPPED, DETAIL_NOT_OWNER
        if milestone.status == "completed":
            return OUTCOME_SKIPPED, DETAIL_ALREADY_COMPLETED

        appointment_id: str = payload["appointment_id"]

        if event_type in SCHEDULING_EVENTS:
            milestone.status = "scheduled"
            milestone.appointment_id = appointment_id
            milestone.scheduled_at = _parse_ts(payload.get("scheduled_at"))
            return OUTCOME_ACKED, None

        if event_type in RELEASING_EVENTS:
            # A late cancellation of a superseded appointment must not release its replacement.
            if milestone.appointment_id not in (None, appointment_id):
                return OUTCOME_SKIPPED, DETAIL_OTHER_APPOINTMENT
            milestone.status = "pending"
            milestone.appointment_id = None
            milestone.scheduled_at = None
            return OUTCOME_ACKED, None

        milestone.scheduled_at = _parse_ts(payload.get("scheduled_at")) or milestone.scheduled_at
        await complete_milestone(
            db,
            journey,
            milestone,
            now=_parse_ts(payload.get("completed_at")) or utcnow(),
            actor=EventActor(type="system", id=CONSUMER_NAME),
            appointment_id=appointment_id,
            provider_id=payload.get("provider_id"),
        )
        return OUTCOME_ACKED, None


appointment_event_handler = AppointmentEventHandler()
