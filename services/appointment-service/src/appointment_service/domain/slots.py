"""Slot derivation — a pure function of provider-service facts and existing bookings.

Model:
- Availability rules and branch opening hours are branch-local wall-clock windows (minutes since
  midnight, ISO weekday 0 = Monday). A rule applies on local date D when its weekday matches and
  ``effective_from <= D <= effective_until`` (open-ended when ``effective_until`` is null).
- Bookable windows for D are the intersection of the day's rules with the day's opening hours.
- Window bounds are converted to UTC instants with the branch's IANA zone; candidates then step in
  absolute time (``interval``) from the window start. On a DST change day this yields the real number of
  hours: a spring-forward gap has no slots, a fall-back hour is offered twice (it exists twice). A bound
  that falls into a gap resolves with the pre-transition offset (i.e. it shifts forward).
- A slot is offered when the visit fits the window (``start + duration <= window end``) and its
  occupancy ``[start, start + duration + buffer)`` overlaps no blocked interval (availability
  exceptions, existing holds/appointments, whose occupancy also includes their buffer).
- Slots before ``not_before`` (minimum lead time) or after ``not_after`` (booking horizon) are dropped.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class HoursWindow:
    weekday: int
    start_minute: int
    end_minute: int


@dataclass(frozen=True)
class Rule:
    weekday: int
    start_minute: int
    end_minute: int
    effective_from: date
    effective_until: date | None = None

    def applies_on(self, day: date) -> bool:
        return (
            self.weekday == day.weekday()
            and self.effective_from <= day
            and (self.effective_until is None or day <= self.effective_until)
        )


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def overlaps(self, other: Interval) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    occupied_until: datetime


def local_instant(day: date, minute: int, zone: ZoneInfo) -> datetime:
    """Branch-local wall time (``minute`` since midnight of ``day``; 1440 = next midnight) as UTC."""
    naive = datetime.combine(day, time.min) + timedelta(minutes=minute)
    return naive.replace(tzinfo=zone).astimezone(UTC)


def _intersect(a: Sequence[tuple[int, int]], b: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    out = [(max(s1, s2), min(e1, e2)) for s1, e1 in a for s2, e2 in b if max(s1, s2) < min(e1, e2)]
    out.sort()
    merged: list[tuple[int, int]] = []
    for start, end in out:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def day_windows(day: date, rules: Iterable[Rule], hours: Iterable[HoursWindow]) -> list[tuple[int, int]]:
    weekday = day.weekday()
    rule_windows = [(r.start_minute, r.end_minute) for r in rules if r.applies_on(day)]
    hour_windows = [(h.start_minute, h.end_minute) for h in hours if h.weekday == weekday]
    return _intersect(rule_windows, hour_windows)


def derive_slots(
    *,
    timezone: str,
    from_date: date,
    to_date: date,
    duration_minutes: int,
    buffer_minutes: int,
    interval_minutes: int,
    hours: Sequence[HoursWindow],
    rules: Sequence[Rule],
    blocked: Sequence[Interval],
    not_before: datetime,
    not_after: datetime,
) -> list[Slot]:
    if duration_minutes <= 0 or interval_minutes <= 0 or buffer_minutes < 0:
        raise ValueError("duration and interval must be positive, buffer non-negative")
    zone = ZoneInfo(timezone)
    duration = timedelta(minutes=duration_minutes)
    occupancy = timedelta(minutes=duration_minutes + buffer_minutes)
    step = timedelta(minutes=interval_minutes)
    blocked_sorted = sorted(blocked, key=lambda i: i.start)

    slots: dict[datetime, Slot] = {}
    day = from_date
    while day <= to_date:
        for start_minute, end_minute in day_windows(day, rules, hours):
            window_start = local_instant(day, start_minute, zone)
            window_end = local_instant(day, end_minute, zone)
            start = window_start
            while start + duration <= window_end:
                if not_before <= start <= not_after:
                    candidate = Interval(start, start + occupancy)
                    if not any(candidate.overlaps(b) for b in blocked_sorted):
                        slots[start] = Slot(start=start, end=start + duration, occupied_until=start + occupancy)
                start += step
        day += timedelta(days=1)
    return [slots[k] for k in sorted(slots)]


def local_iso(instant: datetime, timezone: str) -> str:
    return instant.astimezone(ZoneInfo(timezone)).isoformat()
