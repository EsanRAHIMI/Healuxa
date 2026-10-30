"""Shared lifecycle mechanics: audit trail, expiry, reminders, presentation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timedelta

from healuxa_py_common.events.envelope import EventActor
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from appointment_service.config import settings
from appointment_service.domain import schemas
from appointment_service.domain.slots import local_iso
from appointment_service.events.publisher import event_publisher, ts
from appointment_service.infra.models import Appointment, AppointmentReminder, AppointmentTransition

SYSTEM_ACTOR = EventActor(type="system", id="appointment-service")


def record(
    db: AsyncSession,
    appointment: Appointment,
    *,
    action: str,
    from_status: str | None,
    to_status: str,
    actor_type: str,
    actor_id: str | None,
    at: datetime,
    reason_code: str | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    db.add(
        AppointmentTransition(
            id=str(ULID()),
            tenant_id=appointment.tenant_id,
            appointment_id=appointment.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_type=actor_type,
            actor_id=actor_id,
            reason_code=reason_code,
            reason=reason,
            idempotency_key=idempotency_key,
            occurred_at=at,
        )
    )


def change_status(appointment: Appointment, status: str, at: datetime) -> str:
    previous = appointment.status
    appointment.status = status
    appointment.version += 1
    appointment.updated_at = at
    return previous


async def expire_stale_holds(db: AsyncSession, now: datetime, *, tenant_id: str | None = None, provider_id: str | None = None, user_id: str | None = None) -> int:
    """Lazy expiry: holds past ``expires_at`` become ``expired`` (freeing their slot) and are audited.

    Holds are never announced, so no events. Caller commits.
    """
    stmt = update(Appointment).where(Appointment.status == "held", Appointment.expires_at <= now)
    if tenant_id is not None:
        stmt = stmt.where(Appointment.tenant_id == tenant_id)
    scope = []
    if provider_id is not None:
        scope.append(Appointment.provider_id == provider_id)
    if user_id is not None:
        scope.append(Appointment.user_id == user_id)
    if scope:
        stmt = stmt.where(or_(*scope))
    stmt = (
        stmt.values(status="expired", version=Appointment.version + 1, updated_at=now)
        .returning(Appointment.id, Appointment.tenant_id)
        .execution_options(synchronize_session=False)
    )
    rows = (await db.execute(stmt)).all()
    for appointment_id, tenant in rows:
        db.add(
            AppointmentTransition(
                id=str(ULID()),
                tenant_id=tenant,
                appointment_id=appointment_id,
                action="expire",
                from_status="held",
                to_status="expired",
                actor_type="system",
                actor_id=None,
                reason_code="hold_expired",
                occurred_at=now,
            )
        )
    return len(rows)


async def expire_if_due(db: AsyncSession, appointment: Appointment, now: datetime) -> bool:
    """Expire one locked appointment whose hold or answer deadline has passed. Caller commits."""
    if appointment.expires_at is None or appointment.expires_at > now:
        return False
    if appointment.status == "held":
        previous = change_status(appointment, "expired", now)
        record(db, appointment, action="expire", from_status=previous, to_status="expired", actor_type="system", actor_id=None, at=now, reason_code="hold_expired")
        return True
    if appointment.status == "requested":
        previous = change_status(appointment, "expired", now)
        record(db, appointment, action="expire", from_status=previous, to_status="expired", actor_type="system", actor_id=None, at=now, reason_code="request_unanswered")
        await event_publisher.publish(
            db=db, event_type="appointment.expired", appointment=appointment, extra={"expired_at": ts(now)}, actor=SYSTEM_ACTOR
        )
        return True
    return False


def schedule_reminders(db: AsyncSession, appointment: Appointment, now: datetime) -> None:
    for offset in sorted(set(settings.reminder_offsets_minutes), reverse=True):
        due = appointment.starts_at - timedelta(minutes=offset)
        db.add(
            AppointmentReminder(
                id=str(ULID()),
                tenant_id=appointment.tenant_id,
                appointment_id=appointment.id,
                offset_minutes=offset,
                due_at=due,
                # A reminder whose moment already passed (late booking) is recorded as skipped.
                status="scheduled" if due > now else "skipped",
                created_at=now,
            )
        )


async def cancel_reminders(db: AsyncSession, appointment_id: str) -> None:
    await db.execute(
        update(AppointmentReminder)
        .where(AppointmentReminder.appointment_id == appointment_id, AppointmentReminder.status == "scheduled")
        .values(status="cancelled")
        .execution_options(synchronize_session=False)
    )


def _schema(appointment: Appointment, reminders: Sequence[AppointmentReminder]) -> schemas.Appointment:
    price = None
    if appointment.price_minor is not None and appointment.currency:
        price = schemas.Money(amount_minor=appointment.price_minor, currency=appointment.currency)
    return schemas.Appointment(
        id=appointment.id,
        user_id=appointment.user_id,
        provider_id=appointment.provider_id,
        facility_id=appointment.facility_id,
        branch_id=appointment.branch_id,
        service_id=appointment.service_id,
        milestone_id=appointment.milestone_id,
        status=appointment.status,
        scheduled_at=appointment.starts_at,
        ends_at=appointment.ends_at,
        local_start=local_iso(appointment.starts_at, appointment.timezone),
        timezone=appointment.timezone,
        duration_minutes=appointment.duration_minutes,
        buffer_minutes=appointment.buffer_minutes,
        service_name=appointment.service_name,
        price=price,
        payment_status=appointment.payment_status,
        channel=appointment.channel,
        hold_expires_at=appointment.expires_at if appointment.status == "held" else None,
        requested_at=appointment.requested_at,
        confirmed_at=appointment.confirmed_at,
        checked_in_at=appointment.checked_in_at,
        completed_at=appointment.completed_at,
        cancelled_at=appointment.cancelled_at,
        cancelled_by=appointment.cancelled_by,
        decline_reason=appointment.decline_reason,
        no_show_party=appointment.no_show_party,
        rescheduled_from_id=appointment.rescheduled_from_id,
        rescheduled_to_id=appointment.rescheduled_to_id,
        reminders=[
            schemas.Reminder(id=r.id, offset_minutes=r.offset_minutes, due_at=r.due_at, status=r.status)
            for r in sorted(reminders, key=lambda r: r.due_at)
        ],
        version=appointment.version,
        created_at=appointment.created_at,
    )


async def present(db: AsyncSession, appointments: Sequence[Appointment]) -> list[schemas.Appointment]:
    ids = [a.id for a in appointments]
    by_appointment: dict[str, list[AppointmentReminder]] = defaultdict(list)
    if ids:
        for reminder in await db.scalars(select(AppointmentReminder).where(AppointmentReminder.appointment_id.in_(ids))):
            by_appointment[reminder.appointment_id].append(reminder)
    return [_schema(a, by_appointment[a.id]) for a in appointments]


async def present_one(db: AsyncSession, appointment: Appointment) -> schemas.Appointment:
    return (await present(db, [appointment]))[0]
