"""Periodic housekeeping: expire holds and unanswered requests, hand due reminders to notification.

Safe with several replicas: rows are claimed with ``FOR UPDATE SKIP LOCKED`` and every step is a short
transaction. Reminder delivery itself belongs to notification-service, which consumes
``appointment.reminder_due``; this service only owns the schedule (as data) and the hand-off.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from appointment_service.config import settings
from appointment_service.domain.clock import clock
from appointment_service.domain.lifecycle import SYSTEM_ACTOR, expire_if_due, expire_stale_holds
from appointment_service.events.publisher import event_publisher, ts
from appointment_service.infra.models import Appointment, AppointmentReminder

logger = logging.getLogger(__name__)
BATCH = 200


@dataclass
class SweepResult:
    holds_expired: int = 0
    requests_expired: int = 0
    reminders_dispatched: int = 0
    reminders_skipped: int = 0


async def _expire_requests(db: AsyncSession, now: datetime) -> int:
    rows = (
        await db.scalars(
            select(Appointment)
            .where(Appointment.status == "requested", Appointment.expires_at <= now)
            .order_by(Appointment.expires_at)
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for appointment in rows:
        await expire_if_due(db, appointment, now)
    return len(rows)


async def _dispatch_reminders(db: AsyncSession, now: datetime) -> tuple[int, int]:
    rows = (
        await db.execute(
            select(AppointmentReminder, Appointment)
            .join(Appointment, Appointment.id == AppointmentReminder.appointment_id)
            .where(AppointmentReminder.status == "scheduled", AppointmentReminder.due_at <= now)
            .order_by(AppointmentReminder.due_at)
            .limit(BATCH)
            .with_for_update(of=AppointmentReminder, skip_locked=True)
        )
    ).all()
    dispatched = skipped = 0
    for reminder, appointment in rows:
        if appointment.status != "confirmed" or appointment.starts_at <= now:
            # Never send a reminder for a cancelled/finished visit or one that already started.
            reminder.status = "skipped"
            skipped += 1
            continue
        await event_publisher.publish(
            db=db,
            event_type="appointment.reminder_due",
            appointment=appointment,
            extra={
                "reminder_id": reminder.id,
                "offset_minutes": reminder.offset_minutes,
                "due_at": ts(reminder.due_at),
                "timezone": appointment.timezone,
            },
            actor=SYSTEM_ACTOR,
        )
        reminder.status = "dispatched"
        reminder.dispatched_at = now
        dispatched += 1
    return dispatched, skipped


async def sweep_once(session_factory: async_sessionmaker[AsyncSession], now: datetime | None = None) -> SweepResult:
    now = now or clock.now()
    result = SweepResult()
    async with session_factory() as db, db.begin():
        result.holds_expired = await expire_stale_holds(db, now)
    async with session_factory() as db, db.begin():
        result.requests_expired = await _expire_requests(db, now)
    async with session_factory() as db, db.begin():
        result.reminders_dispatched, result.reminders_skipped = await _dispatch_reminders(db, now)
    return result


async def run_forever(session_factory: async_sessionmaker[AsyncSession], stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            result = await sweep_once(session_factory)
            if result.holds_expired or result.requests_expired or result.reminders_dispatched:
                logger.info("sweep: %s", result)
        except Exception:  # keep sweeping; the next tick retries
            logger.exception("appointment sweep failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.sweeper_interval_seconds)
