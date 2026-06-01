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
