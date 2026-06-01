"""Happy-path journey API flow."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from helpers import create_test_milestone


@pytest.mark.asyncio
async def test_journey_create_get_complete_flow(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    create = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["wellness"]},
        headers=auth_headers,
    )
    assert create.status_code == 201, create.text
    assert create.headers["location"] == f"/v1/journeys/{create.json()['id']}"

    journey_id = create.json()["id"]

    by_user = await client.get(f"/v1/journeys/{user_id}", headers=auth_headers)
    assert by_user.status_code == 200
    assert by_user.json()["id"] == journey_id

    roadmap = await client.get(f"/v1/journeys/{journey_id}/roadmap", headers=auth_headers)
    assert roadmap.status_code == 200
    assert roadmap.json()["journey_id"] == journey_id
    assert roadmap.json()["phases"] == []

    milestone_id = await create_test_milestone(journey_id, title="Initial assessment")

    listed = await client.get(f"/v1/journeys/{journey_id}/milestones", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1

    complete = await client.post(
        f"/v1/journeys/{journey_id}/milestones/{milestone_id}/complete",
        headers=auth_headers,
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"

    health = await client.get(f"/v1/journeys/{journey_id}/health", headers=auth_headers)
    assert health.status_code == 200
    assert health.json()["status"] == "onboarding"

    reassess = await client.post(f"/v1/journeys/{journey_id}/reassess", headers=auth_headers)
    assert reassess.status_code == 202

    actions = await client.get(f"/v1/journeys/{journey_id}/next-actions", headers=auth_headers)
    assert actions.status_code == 200
    assert actions.json() == []
