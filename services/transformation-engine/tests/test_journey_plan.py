"""Goal-driven plan generation and step progression, including appointment-driven steps."""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from transformation_engine.config import settings
from transformation_engine.consumers.assessment_completed import process_assessment_completed
from transformation_engine.domain.appointment_event_handler import (
    DETAIL_NOT_OWNER,
    DETAIL_OTHER_APPOINTMENT,
    appointment_event_handler,
)
from transformation_engine.infra.db import SessionLocal
from transformation_engine.infra.event_models import OUTCOME_ACKED, OUTCOME_REJECTED, OUTCOME_SKIPPED
from transformation_engine.infra.models import OUTBOX


async def _create(client: AsyncClient, user_id: str, headers: dict, goals: list[str]) -> dict:
    response = await client.post("/v1/journeys", json={"user_id": user_id, "primary_goals": goals}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _roadmap(client: AsyncClient, journey_id: str, headers: dict) -> list[dict]:
    response = await client.get(f"/v1/journeys/{journey_id}/roadmap", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["phases"]


def _step(phases: list[dict], code: str, goal: str | None = None) -> dict:
    for phase in phases:
        for step in phase["milestones"]:
            if step["code"] == code and step["goal"] == goal:
                return step
    raise AssertionError(f"step {code}/{goal} not in roadmap")


def _appointment_event(event_type: str, *, user_id: str, milestone_id: str | None, appointment_id: str, **extra) -> dict:
    payload = {
        "appointment_id": appointment_id,
        "user_id": user_id,
        "provider_id": str(ULID()),
        "service_id": str(ULID()),
        "scheduled_at": "2026-12-01T09:00:00Z",
        **extra,
    }
    if milestone_id:
        payload["milestone_id"] = milestone_id
    return {
        "event_id": str(ULID()),
        "type": event_type,
        "version": 1,
        "schema_ref": "https://contracts.healuxa.com/events/appointment.schema.json#/$defs/X",
        "occurred_at": datetime.now(UTC).isoformat(),
        "tenant_id": settings.tenant_default,
        "producer": "appointment-service",
        "payload": payload,
    }


async def _deliver(envelope: dict):
    async with SessionLocal() as db:
        return await appointment_event_handler.handle(envelope, db=db)


async def _intake_completed(user_id: str) -> None:
    envelope = {
        "event_id": str(ULID()),
        "type": "assessment.completed",
        "version": 1,
        "schema_ref": "https://contracts.healuxa.com/events/assessment.schema.json#/$defs/AssessmentCompleted",
        "occurred_at": datetime.now(UTC).isoformat(),
        "tenant_id": settings.tenant_default,
        "producer": "assessment-service",
        "payload": {
            "assessment_id": str(ULID()),
            "user_id": user_id,
            "kind": "intake",
            "recommended_goals": [],
            "scores": {},
            "completed_at": datetime.now(UTC).isoformat(),
        },
    }
    async with SessionLocal() as db:
        result = await process_assessment_completed(envelope, db=db)
    assert result.linked


async def _event_types() -> list[str]:
    async with SessionLocal() as db:
        rows = await db.execute(select(OUTBOX.c.event_type))
        return [row[0] for row in rows]


async def test_create_journey_generates_plan(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    journey = await _create(client, user_id, auth_headers, ["skin_health", "dental_smile"])
    assert journey["status"] == "onboarding"

    phases = await _roadmap(client, journey["id"], auth_headers)
    assert [p["code"] for p in phases] == ["understand", "consult", "care", "follow_up"]
    assert [p["status"] for p in phases] == ["in_progress", "pending", "pending", "pending"]
    assert [(s["code"], s["goal"], s["service_category"]) for s in phases[1]["milestones"]] == [
        ("consultation", "skin_health", "dermatology"),
        ("consultation", "dental_smile", "dental"),
    ]
    sequences = [s["sequence"] for p in phases for s in p["milestones"]]
    assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences) == 8

    actions = (await client.get(f"/v1/journeys/{journey['id']}/next-actions", headers=auth_headers)).json()
    assert [(a["action_type"], a["milestone_code"], a["priority"]) for a in actions] == [
        ("assess", "intake_assessment", "high")
    ]
    assert "journey.roadmap_updated" in await _event_types()


async def test_unknown_duplicate_or_too_many_goals_rejected(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    for goals in (["cure_everything"], ["longevity", "longevity"], ["skin_health", "longevity", "dental_smile", "hair_restoration"]):
        response = await client.post(
            "/v1/journeys", json={"user_id": user_id, "primary_goals": goals}, headers=auth_headers
        )
        assert response.status_code == 422, goals


async def test_intake_assessment_activates_journey_and_opens_consult_phase(
    client: AsyncClient, user_id: str, auth_headers: dict
) -> None:
    journey = await _create(client, user_id, auth_headers, ["longevity"])
    await _intake_completed(user_id)

    phases = await _roadmap(client, journey["id"], auth_headers)
    assert _step(phases, "intake_assessment")["status"] == "completed"
    assert [p["status"] for p in phases] == ["completed", "in_progress", "pending", "pending"]
    current = (await client.get(f"/v1/journeys/{user_id}", headers=auth_headers)).json()
    assert current["status"] == "active"

    actions = (await client.get(f"/v1/journeys/{journey['id']}/next-actions", headers=auth_headers)).json()
    assert [(a["action_type"], a["service_category"]) for a in actions] == [("book", "longevity")]
    types = await _event_types()
    assert "journey.milestone_completed" in types and "journey.phase_completed" in types


async def test_appointment_lifecycle_drives_step(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    journey = await _create(client, user_id, auth_headers, ["skin_health"])
    await _intake_completed(user_id)
    step = _step(await _roadmap(client, journey["id"], auth_headers), "consultation", "skin_health")
    appointment_id = str(ULID())

    requested = _appointment_event(
        "appointment.requested", user_id=user_id, milestone_id=step["id"], appointment_id=appointment_id
    )
    assert (await _deliver(requested)).outcome == OUTCOME_ACKED
    assert (await _deliver(requested)).detail == "already_processed"
    step = _step(await _roadmap(client, journey["id"], auth_headers), "consultation", "skin_health")
    assert (step["status"], step["appointment_id"]) == ("scheduled", appointment_id)
    assert step["scheduled_at"].startswith("2026-12-01T09:00:00")
    # A scheduled step is waiting on the visit, so it is no longer something the customer must do.
    assert (await client.get(f"/v1/journeys/{journey['id']}/next-actions", headers=auth_headers)).json() == []

    await _deliver(
        _appointment_event("appointment.cancelled", user_id=user_id, milestone_id=step["id"], appointment_id=appointment_id)
    )
    step = _step(await _roadmap(client, journey["id"], auth_headers), "consultation", "skin_health")
    assert (step["status"], step["appointment_id"]) == ("pending", None)

    second = str(ULID())
    await _deliver(_appointment_event("appointment.accepted", user_id=user_id, milestone_id=step["id"], appointment_id=second))
    stale = await _deliver(
        _appointment_event("appointment.expired", user_id=user_id, milestone_id=step["id"], appointment_id=appointment_id)
    )
    assert (stale.outcome, stale.detail) == (OUTCOME_SKIPPED, DETAIL_OTHER_APPOINTMENT)

    await _deliver(
        _appointment_event(
            "appointment.completed",
            user_id=user_id,
            milestone_id=step["id"],
            appointment_id=second,
            completed_at="2026-12-01T09:45:00Z",
        )
    )
    phases = await _roadmap(client, journey["id"], auth_headers)
    step = _step(phases, "consultation", "skin_health")
    assert (step["status"], step["appointment_id"]) == ("completed", second)
    assert [p["status"] for p in phases] == ["completed", "completed", "in_progress", "pending"]

    late = await _deliver(
        _appointment_event("appointment.cancelled", user_id=user_id, milestone_id=step["id"], appointment_id=second)
    )
    assert late.outcome == OUTCOME_SKIPPED
    assert _step(await _roadmap(client, journey["id"], auth_headers), "consultation", "skin_health")["status"] == "completed"


async def test_appointment_event_cannot_touch_another_users_step(
    client: AsyncClient, user_id: str, auth_headers: dict
) -> None:
    journey = await _create(client, user_id, auth_headers, ["dental_smile"])
    step = _step(await _roadmap(client, journey["id"], auth_headers), "consultation", "dental_smile")

    result = await _deliver(
        _appointment_event("appointment.completed", user_id=str(ULID()), milestone_id=step["id"], appointment_id=str(ULID()))
    )
    assert (result.outcome, result.detail) == (OUTCOME_SKIPPED, DETAIL_NOT_OWNER)
    assert _step(await _roadmap(client, journey["id"], auth_headers), "consultation", "dental_smile")["status"] == "pending"

    forged = _appointment_event("appointment.completed", user_id=user_id, milestone_id=step["id"], appointment_id=str(ULID()))
    forged["producer"] = "some-other-service"
    assert (await _deliver(forged)).outcome == OUTCOME_REJECTED
    no_step = _appointment_event("appointment.completed", user_id=user_id, milestone_id=None, appointment_id=str(ULID()))
    assert (await _deliver(no_step)).outcome == OUTCOME_SKIPPED


async def test_close_journey_allows_a_new_one(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    journey = await _create(client, user_id, auth_headers, ["skin_health"])
    other = {**auth_headers, "X-Healuxa-User": str(ULID())}
    assert (await client.post(f"/v1/journeys/{journey['id']}/close", headers=other)).status_code == 403

    closed = await client.post(f"/v1/journeys/{journey['id']}/close", headers=auth_headers)
    assert closed.status_code == 200 and closed.json()["status"] == "churned"
    assert (await client.post(f"/v1/journeys/{journey['id']}/close", headers=auth_headers)).json()["status"] == "churned"
    assert (await client.get(f"/v1/journeys/{user_id}", headers=auth_headers)).status_code == 404
    await _create(client, user_id, auth_headers, ["longevity"])
