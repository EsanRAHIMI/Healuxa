from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.domain.event_validation import (
    ASSESSMENT_COMPLETED_TYPE,
    EventValidationError,
    parse_assessment_completed_envelope,
    payload_is_empty_roadmap_seed,
)
from transformation_engine.infra.event_repository import (
    assessment_link_exists,
    find_active_journey,
    insert_journey_assessment_link,
    is_event_processed,
    record_processed_event,
)
from transformation_engine.infra.event_models import OUTCOME_ACKED, OUTCOME_REJECTED, OUTCOME_SKIPPED

logger = logging.getLogger(__name__)

DETAIL_NO_ACTIVE_JOURNEY = "no_active_journey"
DETAIL_DUPLICATE_ASSESSMENT_LINK = "duplicate_assessment_link"
DETAIL_NON_EMPTY_ROADMAP_INPUTS = "non_empty_roadmap_inputs_deferred"
DETAIL_INVALID_ENVELOPE = "invalid_envelope"


@dataclass(frozen=True)
class AssessmentCompletedResult:
    outcome: str
    detail: str | None
    linked: bool
    already_processed: bool


class AssessmentCompletedHandler:
    async def handle(self, envelope_data: dict[str, Any], *, db: AsyncSession) -> AssessmentCompletedResult:
        try:
            envelope = parse_assessment_completed_envelope(envelope_data)
        except EventValidationError as exc:
            logger.warning("assessment.completed rejected: %s", exc)
            tenant_id = str(envelope_data.get("tenant_id") or "unknown")
            event_id = str(envelope_data.get("event_id") or "")
            if event_id and not await is_event_processed(db, event_id):
                await record_processed_event(
                    db,
                    event_id=event_id,
                    event_type=str(envelope_data.get("type") or ASSESSMENT_COMPLETED_TYPE),
                    tenant_id=tenant_id,
                    outcome=OUTCOME_REJECTED,
                    detail=DETAIL_INVALID_ENVELOPE,
                )
                await db.commit()
            return AssessmentCompletedResult(
                outcome=OUTCOME_REJECTED,
                detail=DETAIL_INVALID_ENVELOPE,
                linked=False,
                already_processed=False,
            )

        event_id = envelope.event_id
        tenant_id = envelope.tenant_id
        payload = envelope.payload

        if await is_event_processed(db, event_id):
            return AssessmentCompletedResult(
                outcome=OUTCOME_ACKED,
                detail=None,
                linked=False,
                already_processed=True,
            )

        journey = await find_active_journey(
            db,
            tenant_id=tenant_id,
            user_id=payload["user_id"],
        )
        if journey is None:
            await record_processed_event(
                db,
                event_id=event_id,
                event_type=envelope.type,
                tenant_id=tenant_id,
                outcome=OUTCOME_SKIPPED,
                detail=DETAIL_NO_ACTIVE_JOURNEY,
            )
            await db.commit()
            return AssessmentCompletedResult(
                outcome=OUTCOME_SKIPPED,
                detail=DETAIL_NO_ACTIVE_JOURNEY,
                linked=False,
                already_processed=False,
            )

        if not payload_is_empty_roadmap_seed(payload):
            await record_processed_event(
                db,
                event_id=event_id,
                event_type=envelope.type,
                tenant_id=tenant_id,
                outcome=OUTCOME_SKIPPED,
                detail=DETAIL_NON_EMPTY_ROADMAP_INPUTS,
            )
            await db.commit()
            return AssessmentCompletedResult(
                outcome=OUTCOME_SKIPPED,
                detail=DETAIL_NON_EMPTY_ROADMAP_INPUTS,
                linked=False,
                already_processed=False,
            )

        if await assessment_link_exists(db, tenant_id=tenant_id, assessment_id=payload["assessment_id"]):
            await record_processed_event(
                db,
                event_id=event_id,
                event_type=envelope.type,
                tenant_id=tenant_id,
                outcome=OUTCOME_SKIPPED,
                detail=DETAIL_DUPLICATE_ASSESSMENT_LINK,
            )
            await db.commit()
            return AssessmentCompletedResult(
                outcome=OUTCOME_SKIPPED,
                detail=DETAIL_DUPLICATE_ASSESSMENT_LINK,
                linked=False,
                already_processed=False,
            )

        await insert_journey_assessment_link(
            db,
            tenant_id=tenant_id,
            journey_id=journey.id,
            assessment_id=payload["assessment_id"],
            event_id=event_id,
            assessment_kind=payload["kind"],
            completed_at=payload["completed_at"],
        )

        await record_processed_event(
            db,
            event_id=event_id,
            event_type=envelope.type,
            tenant_id=tenant_id,
            outcome=OUTCOME_ACKED,
            detail=None,
        )
        await db.commit()
        return AssessmentCompletedResult(
            outcome=OUTCOME_ACKED,
            detail=None,
            linked=True,
            already_processed=False,
        )


assessment_completed_handler = AssessmentCompletedHandler()
