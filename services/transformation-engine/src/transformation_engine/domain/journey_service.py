from __future__ import annotations

from decimal import Decimal

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from transformation_engine.config import settings
from transformation_engine.domain.idempotency import hash_request_body, read_idempotent_response, store_idempotent_response
from transformation_engine.domain.pagination import decode_cursor, encode_cursor
from transformation_engine.domain.schemas import (
    CreateJourney,
    Journey,
    JourneyHealth,
    Milestone,
    MilestoneListResponse,
    Money,
    NextAction,
    PageMeta,
    Roadmap,
)
from transformation_engine.domain.security import utcnow
from transformation_engine.events.publisher import event_publisher
from transformation_engine.infra.models import (
    TERMINAL_JOURNEY_STATUSES,
    Journey as JourneyModel,
    Milestone as MilestoneModel,
    NextAction as NextActionModel,
    Phase,
    ReassessmentTrigger,
)


def _money_from_json(data: dict | None) -> Money | None:
    if not data:
        return None
    return Money(amount_minor=int(data["amount_minor"]), currency=str(data["currency"]))


def _journey_to_schema(row: JourneyModel) -> Journey:
    return Journey(
        id=row.id,
        user_id=row.user_id,
        primary_goals=list(row.primary_goals),
        status=row.status,  # type: ignore[arg-type]
        health_index=float(row.health_index),
        started_at=row.started_at.isoformat(),
        ltv_projection=_money_from_json(row.ltv_projection),
    )


def _milestone_to_schema(row: MilestoneModel) -> Milestone:
    return Milestone(
        id=row.id,
        title=row.title,
        status=row.status,  # type: ignore[arg-type]
        due_at=row.due_at.isoformat() if row.due_at else None,
    )


def _ensure_access(journey: JourneyModel, principal: Principal) -> None:
    if journey.user_id != principal.user_id:
        raise ApiError(
            status=403,
            code="forbidden",
            title="Forbidden",
            detail="Cannot access another user's journey",
        )


class JourneyService:
    async def get_journey(self, db: AsyncSession, journey_id: str) -> JourneyModel:
        journey = await db.get(JourneyModel, journey_id)
        if not journey:
            raise ApiError(status=404, code="not_found", title="Not found", detail="Journey not found")
        return journey

    async def create_journey(
        self,
        db: AsyncSession,
        body: CreateJourney,
        *,
        principal: Principal,
        idempotency_key: str | None,
    ) -> tuple[Journey, str]:
        if body.user_id != principal.user_id:
            raise ApiError(
                status=403,
                code="forbidden",
                title="Forbidden",
                detail="Cannot create a journey for another user",
            )

        body_hash = hash_request_body(body.model_dump(mode="json"))
        if idempotency_key:
            cached = await read_idempotent_response(db, idempotency_key, request_hash=body_hash)
            if cached:
                location = cached.pop("_location", f"/v1/journeys/{cached.get('id', 'unknown')}")
                return Journey(**cached), location

        tenant_id = settings.tenant_default
        existing = await db.scalar(
            select(JourneyModel.id).where(
                JourneyModel.tenant_id == tenant_id,
                JourneyModel.user_id == body.user_id,
                JourneyModel.status.notin_(TERMINAL_JOURNEY_STATUSES),
            )
        )
        if existing:
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="User already has an active journey",
            )

        journey_id = str(ULID())
        now = utcnow()
        journey = JourneyModel(
            id=journey_id,
            tenant_id=tenant_id,
            user_id=body.user_id,
            primary_goals=body.primary_goals,
            status="onboarding",
            started_at=now,
            target_completion=body.target_completion,
            health_index=Decimal("1.000"),
        )
        db.add(journey)

        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="User already has an active journey",
            ) from exc

        await event_publisher.publish(
            event_type="journey.created",
            tenant_id=tenant_id,
            payload={
                "journey_id": journey_id,
                "user_id": body.user_id,
                "primary_goals": body.primary_goals,
                "status": "onboarding",
                "started_at": now.isoformat(),
                **(
                    {"target_completion": body.target_completion.isoformat()}
                    if body.target_completion
                    else {}
                ),
            },
            actor=EventActor(type="user", id=body.user_id),
        )

        response = _journey_to_schema(journey)
        location = f"/v1/journeys/{journey_id}"

        if idempotency_key:
            stored = dict(response.model_dump(mode="json"))
            stored["_location"] = location
            await store_idempotent_response(
                db,
                idempotency_key,
                request_hash=body_hash,
                status_code=201,
                response_body=stored,
            )
        else:
            await db.commit()

        return response, location

    async def get_journey_by_user(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        principal: Principal,
    ) -> Journey:
        if user_id != principal.user_id:
            raise ApiError(
                status=403,
                code="forbidden",
                title="Forbidden",
                detail="Cannot access another user's journey",
            )

        journey = await db.scalar(
            select(JourneyModel)
            .where(
                JourneyModel.tenant_id == settings.tenant_default,
                JourneyModel.user_id == user_id,
                JourneyModel.status.notin_(TERMINAL_JOURNEY_STATUSES),
            )
            .order_by(JourneyModel.started_at.desc())
            .limit(1)
        )
        if not journey:
            raise ApiError(status=404, code="not_found", title="Not found", detail="Journey not found")
        return _journey_to_schema(journey)

    async def get_roadmap(
        self,
        db: AsyncSession,
        journey_id: str,
        *,
        principal: Principal,
    ) -> Roadmap:
        journey = await self.get_journey(db, journey_id)
        _ensure_access(journey, principal)

        result = await db.execute(
            select(Phase).where(Phase.journey_id == journey_id).order_by(Phase.sequence.asc(), Phase.id.asc())
        )
        phases = [
            {
                "id": phase.id,
                "name": phase.name,
                "sequence": phase.sequence,
                "status": phase.status,
                "started_at": phase.started_at.isoformat() if phase.started_at else None,
                "completed_at": phase.completed_at.isoformat() if phase.completed_at else None,
            }
            for phase in result.scalars()
        ]
        return Roadmap(journey_id=journey_id, phases=phases)

    async def list_milestones(
        self,
        db: AsyncSession,
        journey_id: str,
        *,
        principal: Principal,
        limit: int = 20,
        cursor: str | None = None,
    ) -> MilestoneListResponse:
        journey = await self.get_journey(db, journey_id)
        _ensure_access(journey, principal)

        query = select(MilestoneModel).where(MilestoneModel.journey_id == journey_id)

        if cursor:
            cursor_created_at, cursor_id = decode_cursor(cursor)
            query = query.where(
                or_(
                    MilestoneModel.created_at < cursor_created_at,
                    and_(
                        MilestoneModel.created_at == cursor_created_at,
                        MilestoneModel.id < cursor_id,
                    ),
                )
            )

        query = query.order_by(MilestoneModel.created_at.desc(), MilestoneModel.id.desc()).limit(limit + 1)
        rows = list((await db.execute(query)).scalars())
        has_more = len(rows) > limit
        rows = rows[:limit]

        data = [_milestone_to_schema(row) for row in rows]
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(created_at=last.created_at, resource_id=last.id)

        return MilestoneListResponse(
            data=data,
            page=PageMeta(limit=limit, has_more=has_more, next_cursor=next_cursor),
        )

    async def complete_milestone(
        self,
        db: AsyncSession,
        journey_id: str,
        milestone_id: str,
        *,
        principal: Principal,
        idempotency_key: str | None,
    ) -> Milestone:
        request_hash = hash_request_body({"journey_id": journey_id, "milestone_id": milestone_id})
        if idempotency_key:
            cached = await read_idempotent_response(db, idempotency_key, request_hash=request_hash)
            if cached:
                return Milestone(**cached)

        journey = await self.get_journey(db, journey_id)
        _ensure_access(journey, principal)

        milestone = await db.get(MilestoneModel, milestone_id)
        if not milestone or milestone.journey_id != journey_id:
            raise ApiError(status=404, code="not_found", title="Not found", detail="Milestone not found")

        if milestone.status == "completed":
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="Milestone already completed",
            )

        now = utcnow()
        milestone.status = "completed"
        milestone.completed_at = now

        await event_publisher.publish(
            event_type="journey.milestone_completed",
            tenant_id=journey.tenant_id,
            payload={
                "journey_id": journey_id,
                "user_id": journey.user_id,
                "milestone_id": milestone_id,
                "phase_id": milestone.phase_id,
                "completed_at": now.isoformat(),
            },
            actor=EventActor(type="user", id=principal.user_id),
        )

        response = _milestone_to_schema(milestone)

        if idempotency_key:
            await store_idempotent_response(
                db,
                idempotency_key,
                request_hash=request_hash,
                status_code=200,
                response_body=response.model_dump(mode="json"),
            )
        else:
            await db.commit()

        return response

    async def list_next_actions(
        self,
        db: AsyncSession,
        journey_id: str,
        *,
        principal: Principal,
    ) -> list[NextAction]:
        journey = await self.get_journey(db, journey_id)
        _ensure_access(journey, principal)

        result = await db.execute(
            select(NextActionModel)
            .where(NextActionModel.journey_id == journey_id, NextActionModel.status == "pending")
            .order_by(NextActionModel.created_at.asc())
        )
        return [
            NextAction(
                action_type=row.action_type,  # type: ignore[arg-type]
                priority=row.priority,  # type: ignore[arg-type]
                due_at=row.due_at.isoformat() if row.due_at else None,
            )
            for row in result.scalars()
        ]

    async def reassess_journey(
        self,
        db: AsyncSession,
        journey_id: str,
        *,
        principal: Principal,
        idempotency_key: str | None,
    ) -> None:
        request_hash = hash_request_body({"journey_id": journey_id})
        if idempotency_key:
            cached = await read_idempotent_response(db, idempotency_key, request_hash=request_hash)
            if cached is not None:
                return

        journey = await self.get_journey(db, journey_id)
        _ensure_access(journey, principal)

        due_at = utcnow()
        trigger = ReassessmentTrigger(
            id=str(ULID()),
            journey_id=journey_id,
            due_at=due_at,
            reason="manual",
        )
        db.add(trigger)

        await event_publisher.publish(
            event_type="journey.reassessment_due",
            tenant_id=journey.tenant_id,
            payload={
                "journey_id": journey_id,
                "user_id": journey.user_id,
                "due_at": due_at.isoformat(),
            },
            actor=EventActor(type="user", id=principal.user_id),
        )

        if idempotency_key:
            await store_idempotent_response(
                db,
                idempotency_key,
                request_hash=request_hash,
                status_code=202,
                response_body={},
            )
        else:
            await db.commit()

    async def get_health(
        self,
        db: AsyncSession,
        journey_id: str,
        *,
        principal: Principal,
    ) -> JourneyHealth:
        journey = await self.get_journey(db, journey_id)
        _ensure_access(journey, principal)
        return JourneyHealth(
            health_index=float(journey.health_index),
            status=journey.status,  # type: ignore[arg-type]
        )


journey_service = JourneyService()
