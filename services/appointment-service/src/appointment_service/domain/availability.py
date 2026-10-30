"""Bookable-slot queries: provider-service facts + this service's own holds and appointments."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from appointment_service.clients.provider_directory import ProviderDirectory, ProviderUnavailable, SchedulingContext
from appointment_service.config import settings
from appointment_service.domain import schemas
from appointment_service.domain.clock import clock
from appointment_service.domain.errors import conflict, not_found, unavailable, unprocessable
from appointment_service.domain.slots import HoursWindow, Interval, Rule, Slot, derive_slots, local_iso
from appointment_service.infra.models import BLOCKING_STATUSES, Appointment


def day_start_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


async def fetch_context(
    directory: ProviderDirectory, tenant_id: str, service_id: str, window_start: datetime, window_end: datetime
) -> SchedulingContext:
    """Bookable facts or an error — never a guess. Unbookable offerings look absent, like the public catalog."""
    try:
        context = await directory.scheduling_context(tenant_id, service_id, window_start, window_end)
    except ProviderUnavailable as exc:
        raise unavailable() from exc
    if context is None or not context.bookable or context.offering.id != service_id:
        raise not_found("Service offering")
    try:
        ZoneInfo(context.branch.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise unavailable("Branch time zone from provider-service is not a valid IANA zone") from exc
    return context


async def busy_intervals(
    db: AsyncSession,
    provider_id: str,
    window_start: datetime,
    window_end: datetime,
    *,
    exclude_id: str | None = None,
) -> list[Interval]:
    """Occupancy of the provider's holding/active appointments; holds past their expiry count as free."""
    now = clock.now()
    stmt = select(Appointment.starts_at, Appointment.blocked_until).where(
        Appointment.provider_id == provider_id,
        Appointment.status.in_(BLOCKING_STATUSES),
        Appointment.starts_at < window_end,
        Appointment.blocked_until > window_start,
        not_(and_(Appointment.status == "held", Appointment.expires_at <= now)),
    )
    if exclude_id is not None:
        stmt = stmt.where(Appointment.id != exclude_id)
    return [Interval(start, end) for start, end in (await db.execute(stmt)).all()]


def _facts(context: SchedulingContext) -> tuple[list[HoursWindow], list[Rule], list[Interval]]:
    hours = [HoursWindow(h.weekday, h.start_minute, h.end_minute) for h in context.operating_hours]
    rules = [
        Rule(r.weekday, r.start_minute, r.end_minute, r.effective_from, r.effective_until)
        for r in context.availability_rules
    ]
    exceptions = [
        Interval(e.starts_at.astimezone(UTC), e.ends_at.astimezone(UTC))
        for e in context.exceptions
        if e.branch_id in (None, context.branch.id)
    ]
    return hours, rules, exceptions


def _derive(context: SchedulingContext, from_date: date, to_date: date, blocked: list[Interval]) -> list[Slot]:
    hours, rules, exceptions = _facts(context)
    now = clock.now()
    return derive_slots(
        timezone=context.branch.timezone,
        from_date=from_date,
        to_date=to_date,
        duration_minutes=context.offering.duration_minutes,
        buffer_minutes=context.offering.buffer_minutes,
        interval_minutes=settings.slot_interval_minutes,
        hours=hours,
        rules=rules,
        blocked=[*exceptions, *blocked],
        not_before=now + timedelta(minutes=settings.min_lead_minutes),
        not_after=now + timedelta(days=settings.max_horizon_days),
    )


async def list_slots(
    db: AsyncSession, directory: ProviderDirectory, tenant_id: str, service_id: str, from_date: date, to_date: date
) -> schemas.SlotList:
    if to_date < from_date:
        raise unprocessable("to must not be before from", "to")
    if (to_date - from_date).days + 1 > settings.max_slot_range_days:
        raise unprocessable(f"At most {settings.max_slot_range_days} days per request", "to")
    window_start = day_start_utc(from_date - timedelta(days=1))
    window_end = day_start_utc(to_date + timedelta(days=2))
    context = await fetch_context(directory, tenant_id, service_id, window_start, window_end)
    busy = await busy_intervals(db, context.offering.provider_id, window_start, window_end)
    tz = context.branch.timezone
    slots = _derive(context, from_date, to_date, busy)
    return schemas.SlotList(
        service_id=service_id,
        provider_id=context.offering.provider_id,
        branch_id=context.branch.id,
        timezone=tz,
        duration_minutes=context.offering.duration_minutes,
        buffer_minutes=context.offering.buffer_minutes,
        from_=from_date,
        to=to_date,
        slots=[
            schemas.Slot(
                scheduled_at=s.start, ends_at=s.end, local_start=local_iso(s.start, tz), local_end=local_iso(s.end, tz)
            )
            for s in slots
        ],
    )


def check_timing(start: datetime) -> None:
    now = clock.now()
    if start < now + timedelta(minutes=settings.min_lead_minutes):
        raise unprocessable(f"Appointments must start at least {settings.min_lead_minutes} minutes from now", "scheduled_at")
    if start > now + timedelta(days=settings.max_horizon_days):
        raise unprocessable(f"Appointments can be booked at most {settings.max_horizon_days} days ahead", "scheduled_at")


async def context_for_start(
    directory: ProviderDirectory, tenant_id: str, service_id: str, start: datetime
) -> SchedulingContext:
    return await fetch_context(directory, tenant_id, service_id, start - timedelta(days=2), start + timedelta(days=2))


async def require_free_slot(
    db: AsyncSession, context: SchedulingContext, start: datetime, *, exclude_id: str | None = None
) -> Slot:
    """``start`` must be a derived slot (422 otherwise) and not taken by another booking (409).

    This is the friendly pre-check; the exclusion constraint remains the authority under concurrency.
    """
    check_timing(start)
    local_day = start.astimezone(ZoneInfo(context.branch.timezone)).date()
    candidates = _derive(context, local_day - timedelta(days=1), local_day + timedelta(days=1), [])
    slot = next((s for s in candidates if s.start == start), None)
    if slot is None:
        raise unprocessable("scheduled_at is not a bookable slot for this service", "scheduled_at")
    occupancy = Interval(slot.start, slot.occupied_until)
    busy = await busy_intervals(db, context.offering.provider_id, slot.start, slot.occupied_until, exclude_id=exclude_id)
    if any(occupancy.overlaps(b) for b in busy):
        raise conflict("This slot is no longer available")
    return slot
