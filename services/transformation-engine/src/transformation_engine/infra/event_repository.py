from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from transformation_engine.infra.event_models import (
    CONSUMER_NAME,
    LINK_STATUS_PENDING_ROADMAP_SEED,
    OUTCOME_ACKED,
    OUTCOME_REJECTED,
    OUTCOME_SKIPPED,
    JourneyAssessmentLink,
    ProcessedEvent,
)
from transformation_engine.infra.models import TERMINAL_JOURNEY_STATUSES, Journey


async def is_event_processed(db: AsyncSession, event_id: str) -> bool:
    existing = await db.get(ProcessedEvent, event_id)
    return existing is not None


async def find_active_journey(db: AsyncSession, *, tenant_id: str, user_id: str) -> Journey | None:
    return await db.scalar(
        select(Journey).where(
            Journey.tenant_id == tenant_id,
            Journey.user_id == user_id,
            Journey.status.notin_(TERMINAL_JOURNEY_STATUSES),
        )
    )


async def assessment_link_exists(db: AsyncSession, *, tenant_id: str, assessment_id: str) -> bool:
    row = await db.scalar(
        select(JourneyAssessmentLink.id).where(
            JourneyAssessmentLink.tenant_id == tenant_id,
            JourneyAssessmentLink.assessment_id == assessment_id,
        )
    )
    return row is not None


async def record_processed_event(
    db: AsyncSession,
    *,
    event_id: str,
    event_type: str,
    tenant_id: str,
    outcome: str,
    detail: str | None = None,
) -> None:
    db.add(
        ProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            consumer=CONSUMER_NAME,
            tenant_id=tenant_id,
            outcome=outcome,
            detail=detail,
        )
    )


def _parse_completed_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def insert_journey_assessment_link(
    db: AsyncSession,
    *,
    tenant_id: str,
    journey_id: str,
    assessment_id: str,
    event_id: str,
    assessment_kind: str,
    completed_at: str,
) -> None:
    db.add(
        JourneyAssessmentLink(
            id=str(ULID()),
            tenant_id=tenant_id,
            journey_id=journey_id,
            assessment_id=assessment_id,
            event_id=event_id,
            assessment_kind=assessment_kind,
            completed_at=_parse_completed_at(completed_at),
            link_status=LINK_STATUS_PENDING_ROADMAP_SEED,
        )
    )
    await db.flush()
