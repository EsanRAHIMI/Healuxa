"""assessment.completed delivered through JetStream reaches the idempotent handler exactly once."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from helpers import create_test_journey

from transformation_engine.infra.db import SessionLocal
from transformation_engine.infra.event_models import OUTCOME_ACKED, JourneyAssessmentLink, ProcessedEvent

needs_nats = pytest.mark.skipif(not os.environ.get("NATS_URL"), reason="NATS_URL not set")

FIXTURE = Path(__file__).parent / "fixtures" / "assessment_completed_envelope.json"


@needs_nats
async def test_consumer_links_assessment_once_despite_redelivery(
    client: AsyncClient, user_id: str, auth_headers: dict
) -> None:
    from healuxa_py_common.events.consumer import DurableConsumer
    from healuxa_py_common.events.jetstream import EVENTS_STREAM, JetStreamConnection

    from transformation_engine.consumers.assessment_completed import SUBJECT, handle_message

    await create_test_journey(client, user_id, auth_headers)

    envelope = json.loads(FIXTURE.read_text())
    envelope["event_id"] = str(uuid.uuid4())
    envelope["payload"]["user_id"] = user_id
    envelope["payload"]["assessment_id"] = str(ULID())
    data = json.dumps(envelope).encode()

    connection = JetStreamConnection(os.environ["NATS_URL"], name="transformation-tests")
    try:
        js = await connection.jetstream()
        # Two distinct deliveries of the same event (no Nats-Msg-Id) simulate at-least-once redelivery.
        await js.publish(SUBJECT, data, stream=EVENTS_STREAM)
        await js.publish(SUBJECT, data, stream=EVENTS_STREAM)

        seen: list[str] = []

        async def handler(body: dict) -> None:
            if body.get("event_id") == envelope["event_id"]:
                seen.append(body["event_id"])
                await handle_message(body)

        consumer = DurableConsumer(
            connection, subject=SUBJECT, durable=f"te-test-{uuid.uuid4().hex[:8]}", handler=handler, batch_size=200
        )
        for _ in range(5):
            await consumer.run_once(timeout=0.5)
    finally:
        await connection.close()

    assert len(seen) == 2
    async with SessionLocal() as db:
        processed = await db.get(ProcessedEvent, envelope["event_id"])
        links = (
            await db.scalars(
                select(JourneyAssessmentLink).where(
                    JourneyAssessmentLink.assessment_id == envelope["payload"]["assessment_id"]
                )
            )
        ).all()
    assert processed is not None and processed.outcome == OUTCOME_ACKED
    assert len(links) == 1


async def test_envelope_from_assessment_producer_is_accepted(
    client: AsyncClient, user_id: str, auth_headers: dict
) -> None:
    """Guards the producer/consumer contract: shared envelope builder output must be consumable."""
    from healuxa_py_common.events.envelope import EventActor, build_envelope

    from transformation_engine.consumers.assessment_completed import handle_message

    await create_test_journey(client, user_id, auth_headers)
    envelope = build_envelope(
        event_type="assessment.completed",
        version=1,
        schema_ref="https://contracts.healuxa.com/events/assessment.schema.json#/$defs/AssessmentCompleted",
        tenant_id="healuxa-dubai",
        producer="assessment-service",
        payload={
            "assessment_id": str(ULID()),
            "user_id": user_id,
            "kind": "beauty",
            "recommended_goals": [],
            "scores": {},
            "completed_at": "2026-10-28T10:00:00+00:00",
        },
        allowed_producers={"assessment-service"},
        actor=EventActor(type="user", id=user_id),
    )
    await handle_message(envelope.model_dump(mode="json"))

    async with SessionLocal() as db:
        processed = await db.get(ProcessedEvent, envelope.event_id)
    assert processed is not None and processed.outcome == OUTCOME_ACKED
