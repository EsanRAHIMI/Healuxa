from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.domain.assessment_completed_handler import (
    AssessmentCompletedResult,
    assessment_completed_handler,
)


async def process_assessment_completed(
    envelope_data: dict[str, Any],
    *,
    db: AsyncSession,
) -> AssessmentCompletedResult:
    """Entry point for assessment.completed (invoked by tests; NATS subscriber in PR-2)."""
    return await assessment_completed_handler.handle(envelope_data, db=db)
