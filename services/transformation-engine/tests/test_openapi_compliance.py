"""Contract compliance tests for transformation.openapi.yaml."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from ulid import ULID

from helpers import create_test_milestone
from transformation_engine.api.deps import principal_headers


async def _create_journey(client: AsyncClient, user_id: str, headers: dict) -> dict:
    response = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["goal-a"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_journey_requires_permission(client: AsyncClient, user_id: str) -> None:
    response = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["x"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_journey_forbidden_other_user(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    other = str(ULID())
    response = await client.post(
        "/v1/journeys",
        json={"user_id": other, "primary_goals": ["x"]},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_duplicate_journey_returns_409(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    await _create_journey(client, user_id, auth_headers)
    second = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["goal-b"]},
        headers=auth_headers,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "conflict"


@pytest.mark.asyncio
async def test_create_journey_idempotency_replay(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    headers = {**auth_headers, "Idempotency-Key": "journey-create-replay-01"}
    first = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["goal-a"]},
        headers=headers,
    )
    second = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["goal-a"]},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.headers["location"] == second.headers["location"]


@pytest.mark.asyncio
async def test_create_journey_idempotency_conflict(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    headers = {**auth_headers, "Idempotency-Key": "journey-create-conflict-01"}
    first = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["goal-a"]},
        headers=headers,
    )
    assert first.status_code == 201
    second = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["goal-b"]},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_list_milestones_cursor_pagination(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    journey = await _create_journey(client, user_id, auth_headers)
    journey_id = journey["id"]
    for idx in range(3):
        await create_test_milestone(journey_id, title=f"Milestone {idx}")

    page1 = await client.get(
        f"/v1/journeys/{journey_id}/milestones",
        params={"limit": 2},
        headers=auth_headers,
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["data"]) == 2
    assert body1["page"]["has_more"] is True
    assert body1["page"]["next_cursor"]

    page2 = await client.get(
        f"/v1/journeys/{journey_id}/milestones",
        params={"limit": 2, "cursor": body1["page"]["next_cursor"]},
        headers=auth_headers,
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["data"]) == 1
    assert body2["page"]["has_more"] is False

    ids1 = {item["id"] for item in body1["data"]}
    ids2 = {item["id"] for item in body2["data"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_complete_milestone_not_found(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    journey = await _create_journey(client, user_id, auth_headers)
    response = await client.post(
        f"/v1/journeys/{journey['id']}/milestones/{ULID()}/complete",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_milestone_idempotency_replay(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    journey = await _create_journey(client, user_id, auth_headers)
    milestone_id = await create_test_milestone(journey["id"])
    headers = {**auth_headers, "Idempotency-Key": "milestone-complete-replay-01"}
    first = await client.post(
        f"/v1/journeys/{journey['id']}/milestones/{milestone_id}/complete",
        headers=headers,
    )
    second = await client.post(
        f"/v1/journeys/{journey['id']}/milestones/{milestone_id}/complete",
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


@pytest.mark.asyncio
async def test_complete_milestone_already_completed_conflict(
    client: AsyncClient, user_id: str, auth_headers: dict
) -> None:
    journey = await _create_journey(client, user_id, auth_headers)
    milestone_id = await create_test_milestone(journey["id"])
    first = await client.post(
        f"/v1/journeys/{journey['id']}/milestones/{milestone_id}/complete",
        headers=auth_headers,
    )
    assert first.status_code == 200
    second = await client.post(
        f"/v1/journeys/{journey['id']}/milestones/{milestone_id}/complete",
        headers=auth_headers,
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_get_journey_by_user_not_found(client: AsyncClient) -> None:
    missing_user = str(ULID())
    headers = principal_headers(missing_user)
    response = await client.get(f"/v1/journeys/{missing_user}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reassess_returns_202(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    journey = await _create_journey(client, user_id, auth_headers)
    response = await client.post(f"/v1/journeys/{journey['id']}/reassess", headers=auth_headers)
    assert response.status_code == 202
