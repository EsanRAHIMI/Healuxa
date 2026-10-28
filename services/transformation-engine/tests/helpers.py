from __future__ import annotations

from ulid import ULID

from transformation_engine.infra.db import SessionLocal
from transformation_engine.infra.models import Milestone as MilestoneModel


async def create_test_milestone(
    journey_id: str,
    *,
    title: str = "Test milestone",
    status: str = "pending",
) -> str:
    milestone_id = str(ULID())
    async with SessionLocal() as db:
        db.add(
            MilestoneModel(
                id=milestone_id,
                journey_id=journey_id,
                title=title,
                status=status,
            )
        )
        await db.commit()
    return milestone_id


async def create_test_journey(client, user_id: str, auth_headers: dict) -> str:
    response = await client.post(
        "/v1/journeys",
        json={"user_id": user_id, "primary_goals": ["wellness"]},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]
