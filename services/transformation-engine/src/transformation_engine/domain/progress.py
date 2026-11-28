"""Journey progression shared by the API and the event consumers.

Every function stages its changes and events in the caller's transaction and never commits.
"""

from __future__ import annotations

from datetime import datetime

from healuxa_py_common.events.envelope import EventActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.domain.plan_templates import STEP_INTAKE
from transformation_engine.events.publisher import event_publisher
from transformation_engine.infra.models import Journey, Milestone, Phase


async def ordered_phases(db: AsyncSession, journey_id: str) -> list[Phase]:
    result = await db.execute(
        select(Phase).where(Phase.journey_id == journey_id).order_by(Phase.sequence.asc(), Phase.id.asc())
    )
    return list(result.scalars())


async def ordered_milestones(db: AsyncSession, journey_id: str) -> list[Milestone]:
    result = await db.execute(
        select(Milestone)
        .where(Milestone.journey_id == journey_id)
        .order_by(Milestone.sequence.asc(), Milestone.created_at.asc(), Milestone.id.asc())
    )
    return list(result.scalars())


async def complete_milestone(
    db: AsyncSession,
    journey: Journey,
    milestone: Milestone,
    *,
    now: datetime,
    actor: EventActor,
    appointment_id: str | None = None,
    provider_id: str | None = None,
) -> bool:
    """Complete a step once. Returns False (and stages nothing) when it was already completed."""
    if milestone.status == "completed":
        return False

    milestone.status = "completed"
    milestone.completed_at = now
    if appointment_id:
        milestone.appointment_id = appointment_id

    payload = {
        "journey_id": journey.id,
        "user_id": journey.user_id,
        "milestone_id": milestone.id,
        "completed_at": now.isoformat(),
    }
    if milestone.phase_id:
        payload["phase_id"] = milestone.phase_id
    if appointment_id:
        payload["appointment_id"] = appointment_id
    if provider_id:
        payload["provider_id"] = provider_id
    await event_publisher.publish(
        db=db,
        event_type="journey.milestone_completed",
        tenant_id=journey.tenant_id,
        payload=payload,
        actor=actor,
    )

    if milestone.code == STEP_INTAKE and journey.status == "onboarding":
        journey.status = "active"

    await db.flush()
    await advance_phases(db, journey, now=now, actor=actor)
    return True


async def advance_phases(db: AsyncSession, journey: Journey, *, now: datetime, actor: EventActor) -> None:
    """A phase is complete when all its steps are; the first incomplete phase is the current one."""
    phases = await ordered_phases(db, journey.id)
    if not phases:
        return
    by_phase: dict[str, list[Milestone]] = {phase.id: [] for phase in phases}
    for milestone in await ordered_milestones(db, journey.id):
        if milestone.phase_id in by_phase:
            by_phase[milestone.phase_id].append(milestone)

    current_assigned = False
    for phase in phases:
        steps = by_phase[phase.id]
        done = bool(steps) and all(step.status == "completed" for step in steps)
        if done and not current_assigned:
            if phase.status != "completed":
                phase.status = "completed"
                phase.started_at = phase.started_at or now
                phase.completed_at = now
                await event_publisher.publish(
                    db=db,
                    event_type="journey.phase_completed",
                    tenant_id=journey.tenant_id,
                    payload={
                        "journey_id": journey.id,
                        "user_id": journey.user_id,
                        "phase_id": phase.id,
                        "completed_at": now.isoformat(),
                    },
                    actor=actor,
                )
        elif not current_assigned:
            current_assigned = True
            if phase.status != "in_progress":
                phase.status = "in_progress"
                phase.started_at = phase.started_at or now
    await db.flush()
