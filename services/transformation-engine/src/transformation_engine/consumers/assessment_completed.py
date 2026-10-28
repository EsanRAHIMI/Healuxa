from __future__ import annotations

from typing import Any

from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.jetstream import JetStreamConnection, subject_for
from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.domain.assessment_completed_handler import (
    AssessmentCompletedResult,
    assessment_completed_handler,
)
from transformation_engine.infra.db import SessionLocal
from transformation_engine.infra.event_models import CONSUMER_NAME

SUBJECT = subject_for("assessment.completed")
DURABLE_NAME = f"{CONSUMER_NAME}-assessment-completed"


async def process_assessment_completed(
    envelope_data: dict[str, Any],
    *,
    db: AsyncSession,
) -> AssessmentCompletedResult:
    return await assessment_completed_handler.handle(envelope_data, db=db)


async def handle_message(envelope_data: dict[str, Any]) -> None:
    """JetStream entry point. Raising leads to redelivery; the handler is idempotent on event_id."""
    async with SessionLocal() as db:
        await process_assessment_completed(envelope_data, db=db)


def build_consumer(connection: JetStreamConnection) -> DurableConsumer:
    return DurableConsumer(connection, subject=SUBJECT, durable=DURABLE_NAME, handler=handle_message)
