"""Phase 1 handler for assessment.completed — link/audit only."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from ulid import ULID

from transformation_engine.consumers.assessment_completed import process_assessment_completed
from transformation_engine.infra.db import SessionLocal
from transformation_engine.infra.event_models import (
    LINK_STATUS_PENDING_ROADMAP_SEED,
    OUTCOME_ACKED,
    OUTCOME_REJECTED,
    OUTCOME_SKIPPED,
    JourneyAssessmentLink,
    ProcessedEvent,
)
from transformation_engine.infra.event_repository import assessment_link_exists

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "assessment_completed_envelope.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def _envelope(
    *,
    event_id: str | None = None,
    user_id: str | None = None,
    assessment_id: str | None = None,
    kind: str = "beauty",
    producer: str = "assessment-service",
    recommended_goals: list | None = None,
    scores: dict | None = None,
) -> dict:
    data = _load_fixture()
    if event_id is not None:
        data["event_id"] = event_id
    if producer is not None:
        data["producer"] = producer
    if user_id is not None:
        data["payload"]["user_id"] = user_id
    if assessment_id is not None:
        data["payload"]["assessment_id"] = assessment_id
    data["payload"]["kind"] = kind
    if recommended_goals is not None:
        data["payload"]["recommended_goals"] = recommended_goals
    if scores is not None:
        data["payload"]["scores"] = scores
    return data


async def _create_journey(client: AsyncClient, user_id: str, auth_headers: dict) -> str:
    response = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["wellness"]},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_valid_event_creates_link_and_acked(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    await _create_journey(client, user_id, auth_headers)
    event_id = str(ULID())
    assessment_id = str(ULID())
    envelope = _envelope(event_id=event_id, user_id=user_id, assessment_id=assessment_id)

    with patch(
        "transformation_engine.events.publisher.event_publisher.publish",
        new_callable=AsyncMock,
    ) as publish_mock:
        async with SessionLocal() as db:
            result = await process_assessment_completed(envelope, db=db)

    assert result.outcome == OUTCOME_ACKED
    assert result.linked is True
    assert result.already_processed is False
    publish_mock.assert_not_called()

    async with SessionLocal() as db:
        processed = await db.get(ProcessedEvent, event_id)
        assert processed is not None
        assert processed.outcome == OUTCOME_ACKED
        link = await db.scalar(
            select(JourneyAssessmentLink).where(JourneyAssessmentLink.event_id == event_id)
        )
        assert link is not None
        assert link.link_status == LINK_STATUS_PENDING_ROADMAP_SEED
        assert link.assessment_id == assessment_id
        link_count = await db.scalar(select(func.count()).select_from(JourneyAssessmentLink))
        assert link_count == 1


@pytest.mark.asyncio
async def test_duplicate_event_id_is_idempotent(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    await _create_journey(client, user_id, auth_headers)
    event_id = str(ULID())
    assessment_id = str(ULID())
    envelope = _envelope(event_id=event_id, user_id=user_id, assessment_id=assessment_id)

    async with SessionLocal() as db:
        first = await process_assessment_completed(envelope, db=db)
        second = await process_assessment_completed(envelope, db=db)

    assert first.linked is True
    assert second.already_processed is True
    assert second.linked is False

    async with SessionLocal() as db:
        processed_count = await db.scalar(select(func.count()).select_from(ProcessedEvent))
        assert processed_count == 1
        link_count = await db.scalar(select(func.count()).select_from(JourneyAssessmentLink))
        assert link_count == 1


@pytest.mark.asyncio
async def test_no_active_journey_skipped_without_link(user_id: str) -> None:
    envelope = _envelope(event_id=str(ULID()), user_id=user_id, assessment_id=str(ULID()))

    async with SessionLocal() as db:
        result = await process_assessment_completed(envelope, db=db)

    assert result.outcome == OUTCOME_SKIPPED
    assert result.detail == "no_active_journey"
    assert result.linked is False

    async with SessionLocal() as db:
        link_count = await db.scalar(select(func.count()).select_from(JourneyAssessmentLink))
        assert link_count == 0
        processed = await db.get(ProcessedEvent, envelope["event_id"])
        assert processed is not None
        assert processed.outcome == OUTCOME_SKIPPED


@pytest.mark.asyncio
async def test_invalid_producer_rejected_without_link(user_id: str) -> None:
    envelope = _envelope(
        event_id=str(ULID()),
        user_id=user_id,
        assessment_id=str(ULID()),
        producer="transformation-engine",
    )

    async with SessionLocal() as db:
        result = await process_assessment_completed(envelope, db=db)

    assert result.outcome == OUTCOME_REJECTED
    assert result.linked is False

    async with SessionLocal() as db:
        processed = await db.get(ProcessedEvent, envelope["event_id"])
        assert processed is not None
        assert processed.outcome == OUTCOME_REJECTED
        link_count = await db.scalar(select(func.count()).select_from(JourneyAssessmentLink))
        assert link_count == 0


@pytest.mark.asyncio
async def test_duplicate_assessment_id_with_new_event_id_skipped(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    await _create_journey(client, user_id, auth_headers)
    assessment_id = str(ULID())
    first = _envelope(event_id=str(ULID()), user_id=user_id, assessment_id=assessment_id)
    second = _envelope(event_id=str(ULID()), user_id=user_id, assessment_id=assessment_id)

    async with SessionLocal() as db:
        first_result = await process_assessment_completed(first, db=db)
        second_result = await process_assessment_completed(second, db=db)

    assert first_result.outcome == OUTCOME_ACKED
    assert second_result.outcome == OUTCOME_SKIPPED
    assert second_result.detail == "duplicate_assessment_link"

    async with SessionLocal() as db:
        link_count = await db.scalar(select(func.count()).select_from(JourneyAssessmentLink))
        assert link_count == 1
        processed_count = await db.scalar(select(func.count()).select_from(ProcessedEvent))
        assert processed_count == 2


@pytest.mark.asyncio
async def test_reassessment_kind_links_only_no_trigger_resolution(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    journey_id = await _create_journey(client, user_id, auth_headers)
    envelope = _envelope(
        event_id=str(ULID()),
        user_id=user_id,
        assessment_id=str(ULID()),
        kind="reassessment",
    )

    with patch(
        "transformation_engine.events.publisher.event_publisher.publish",
        new_callable=AsyncMock,
    ) as publish_mock:
        async with SessionLocal() as db:
            result = await process_assessment_completed(envelope, db=db)

    assert result.outcome == OUTCOME_ACKED
    assert result.linked is True
    publish_mock.assert_not_called()

    async with SessionLocal() as db:
        assert await assessment_link_exists(
            db,
            tenant_id=envelope["tenant_id"],
            assessment_id=envelope["payload"]["assessment_id"],
        )
        from transformation_engine.infra.models import ReassessmentTrigger

        trigger_count = await db.scalar(
            select(func.count())
            .select_from(ReassessmentTrigger)
            .where(ReassessmentTrigger.journey_id == journey_id)
        )
        assert trigger_count == 0


@pytest.mark.asyncio
async def test_no_external_http_calls(user_id: str) -> None:
    envelope = _envelope(event_id=str(ULID()), user_id=user_id, assessment_id=str(ULID()))

    with patch("httpx.AsyncClient", autospec=True) as http_mock:
        async with SessionLocal() as db:
            await process_assessment_completed(envelope, db=db)
        http_mock.assert_not_called()
