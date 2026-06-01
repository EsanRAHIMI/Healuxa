from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi.responses import JSONResponse
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.api.deps import get_db, require_journey_permission
from transformation_engine.domain.idempotency import validate_idempotency_key
from transformation_engine.domain.journey_service import journey_service
from transformation_engine.domain.schemas import (
    CreateJourney,
    Journey,
    JourneyHealth,
    Milestone,
    MilestoneListResponse,
    NextAction,
    Roadmap,
)

router = APIRouter(prefix="/v1/journeys", tags=["journeys"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Journey,
    operation_id="createJourney",
)
async def create_journey(
    body: CreateJourney,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:create")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    validate_idempotency_key(idempotency_key)
    journey, location = await journey_service.create_journey(
        db,
        body,
        principal=principal,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=journey.model_dump(mode="json"),
        headers={"Location": location},
    )


@router.get(
    "/{user_id}",
    response_model=Journey,
    operation_id="getJourneyByUser",
)
async def get_journey_by_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:read")),
) -> Journey:
    return await journey_service.get_journey_by_user(db, user_id, principal=principal)


@router.get(
    "/{journey_id}/roadmap",
    response_model=Roadmap,
    operation_id="getRoadmap",
)
async def get_roadmap(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:read")),
) -> Roadmap:
    return await journey_service.get_roadmap(db, journey_id, principal=principal)


@router.get(
    "/{journey_id}/milestones",
    response_model=MilestoneListResponse,
    operation_id="listMilestones",
)
async def list_milestones(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:read")),
    limit: int = 20,
    cursor: str | None = None,
) -> MilestoneListResponse:
    return await journey_service.list_milestones(
        db,
        journey_id,
        principal=principal,
        limit=limit,
        cursor=cursor,
    )


@router.post(
    "/{journey_id}/milestones/{milestone_id}/complete",
    response_model=Milestone,
    operation_id="completeMilestone",
)
async def complete_milestone(
    journey_id: str,
    milestone_id: str,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:write")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Milestone:
    validate_idempotency_key(idempotency_key)
    return await journey_service.complete_milestone(
        db,
        journey_id,
        milestone_id,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{journey_id}/next-actions",
    response_model=list[NextAction],
    operation_id="getNextActions",
)
async def get_next_actions(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:read")),
) -> list[NextAction]:
    return await journey_service.list_next_actions(db, journey_id, principal=principal)


@router.post(
    "/{journey_id}/reassess",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="reassessJourney",
)
async def reassess_journey(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:write")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    validate_idempotency_key(idempotency_key)
    await journey_service.reassess_journey(
        db,
        journey_id,
        principal=principal,
        idempotency_key=idempotency_key,
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get(
    "/{journey_id}/health",
    response_model=JourneyHealth,
    operation_id="getJourneyHealth",
)
async def get_journey_health(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_journey_permission("journeys:read")),
) -> JourneyHealth:
    return await journey_service.get_health(db, journey_id, principal=principal)
