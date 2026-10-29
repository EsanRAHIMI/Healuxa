"""Pure slot derivation: rules ∩ opening hours, buffers, exceptions, effective dates, time zones and DST."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from appointment_service.domain.slots import HoursWindow, Interval, Rule, derive_slots, local_iso

EPOCH = datetime(2020, 1, 1, tzinfo=UTC)
FAR = datetime(2100, 1, 1, tzinfo=UTC)
MON = date(2027, 3, 1)


def _hm(hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    return h * 60 + m


def rule(weekday: int, start: str, end: str, since: date = date(2027, 1, 1), until: date | None = None) -> Rule:
    return Rule(weekday, _hm(start), _hm(end), since, until)


def hours(weekday: int, start: str, end: str) -> HoursWindow:
    return HoursWindow(weekday, _hm(start), _hm(end))


def slots(*, tz="Asia/Dubai", day=MON, to=None, duration=30, buffer=0, interval=30, rules=(), hrs=(), blocked=(), not_before=EPOCH, not_after=FAR):
    return derive_slots(
        timezone=tz,
        from_date=day,
        to_date=to or day,
        duration_minutes=duration,
        buffer_minutes=buffer,
        interval_minutes=interval,
        hours=list(hrs),
        rules=list(rules),
        blocked=list(blocked),
        not_before=not_before,
        not_after=not_after,
    )


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


def starts(result) -> list[str]:
    return [s.start.strftime("%H:%M") for s in result]


def test_dubai_slots_are_returned_in_utc() -> None:
    result = slots(rules=[rule(0, "09:00", "12:00")], hrs=[hours(0, "08:00", "18:00")])
    # Asia/Dubai is UTC+4 all year: 09:00 local = 05:00 UTC.
    assert starts(result) == ["05:00", "05:30", "06:00", "06:30", "07:00", "07:30"]
    assert result[0].end == utc(2027, 3, 1, 5, 30)
    assert local_iso(result[0].start, "Asia/Dubai") == "2027-03-01T09:00:00+04:00"


def test_dubai_has_no_dst_offset_change() -> None:
    march = slots(day=date(2027, 3, 29), rules=[rule(0, "09:00", "10:00")], hrs=[hours(0, "00:00", "24:00")])
    october = slots(day=date(2027, 11, 1), rules=[rule(0, "09:00", "10:00")], hrs=[hours(0, "00:00", "24:00")])
    assert starts(march) == starts(october) == ["05:00", "05:30"]


def test_operating_hours_clip_rules() -> None:
    result = slots(rules=[rule(0, "07:00", "13:00")], hrs=[hours(0, "09:00", "18:00")], interval=60, duration=60)
    assert starts(result) == ["05:00", "06:00", "07:00", "08:00"]  # 09:00–13:00 local


def test_no_slots_without_matching_rule_or_hours() -> None:
    assert slots(rules=[rule(1, "09:00", "12:00")], hrs=[hours(0, "08:00", "18:00")]) == []  # rule is Tuesday
    assert slots(rules=[rule(0, "09:00", "12:00")], hrs=[hours(1, "08:00", "18:00")]) == []  # branch closed Monday
    assert slots(rules=[rule(0, "09:00", "12:00")], hrs=[]) == []


def test_rule_effective_dates_are_inclusive() -> None:
    windows = dict(hrs=[hours(0, "00:00", "24:00")], interval=60, duration=60)
    assert slots(rules=[rule(0, "09:00", "10:00", since=MON + timedelta(days=7))], **windows) == []
    assert len(slots(rules=[rule(0, "09:00", "10:00", since=MON)], **windows)) == 1
    assert len(slots(rules=[rule(0, "09:00", "10:00", since=date(2027, 1, 1), until=MON)], **windows)) == 1
    assert slots(rules=[rule(0, "09:00", "10:00", since=date(2027, 1, 1), until=MON - timedelta(days=1))], **windows) == []


def test_visit_must_fit_the_window() -> None:
    assert slots(rules=[rule(0, "09:00", "09:30")], hrs=[hours(0, "08:00", "18:00")], duration=45) == []
    assert starts(slots(rules=[rule(0, "09:00", "10:00")], hrs=[hours(0, "08:00", "18:00")], duration=45, interval=15)) == ["05:00", "05:15"]


def test_buffers_space_appointments() -> None:
    # Existing appointment 10:00–10:30 local with a 15 min buffer occupies until 10:45.
    busy = Interval(utc(2027, 3, 1, 6, 0), utc(2027, 3, 1, 6, 45))
    result = slots(rules=[rule(0, "09:00", "12:00")], hrs=[hours(0, "08:00", "18:00")], duration=30, buffer=15, interval=15, blocked=[busy])
    local_starts = [local_iso(s.start, "Asia/Dubai")[11:16] for s in result]
    # 09:30 would occupy 09:30–10:15 (its own buffer overlaps 10:00); 10:30 is inside the busy buffer.
    assert "09:15" in local_starts and "09:30" not in local_starts
    assert "10:30" not in local_starts and "10:45" in local_starts
    assert result[0].occupied_until - result[0].start == timedelta(minutes=45)


def test_exceptions_block_time() -> None:
    leave = Interval(utc(2027, 3, 1, 6, 0), utc(2027, 3, 1, 7, 0))  # 10:00–11:00 local
    result = slots(rules=[rule(0, "09:00", "12:00")], hrs=[hours(0, "08:00", "18:00")], blocked=[leave])
    assert starts(result) == ["05:00", "05:30", "07:00", "07:30"]


def test_lead_time_and_horizon_bounds() -> None:
    result = slots(
        rules=[rule(0, "09:00", "12:00")],
        hrs=[hours(0, "08:00", "18:00")],
        not_before=utc(2027, 3, 1, 6, 0),
        not_after=utc(2027, 3, 1, 7, 0),
    )
    assert starts(result) == ["06:00", "06:30", "07:00"]


def test_window_until_midnight() -> None:
    result = slots(rules=[rule(0, "23:00", "24:00")], hrs=[hours(0, "00:00", "24:00")])
    assert [local_iso(s.start, "Asia/Dubai") for s in result] == ["2027-03-01T23:00:00+04:00", "2027-03-01T23:30:00+04:00"]
    assert result[-1].end == utc(2027, 3, 1, 20, 0)  # 24:00 local = next day 00:00 = 20:00 UTC


def test_multiple_windows_per_day_and_range() -> None:
    result = slots(
        day=MON,
        to=MON + timedelta(days=2),
        rules=[rule(0, "09:00", "10:00"), rule(0, "14:00", "15:00"), rule(2, "09:00", "10:00")],
        hrs=[hours(d, "08:00", "18:00") for d in range(7)],
        interval=60,
        duration=60,
    )
    assert [local_iso(s.start, "Asia/Dubai")[:16] for s in result] == [
        "2027-03-01T09:00",
        "2027-03-01T14:00",
        "2027-03-03T09:00",
    ]


def test_berlin_offset_changes_between_winter_and_summer() -> None:
    windows = dict(tz="Europe/Berlin", rules=[rule(0, "09:00", "10:00")], hrs=[hours(0, "08:00", "18:00")], interval=60, duration=60)
    assert slots(day=date(2027, 3, 22), **windows)[0].start == utc(2027, 3, 22, 8, 0)  # CET, UTC+1
    assert slots(day=date(2027, 3, 29), **windows)[0].start == utc(2027, 3, 29, 7, 0)  # CEST, UTC+2


def test_berlin_spring_forward_day_skips_missing_hour() -> None:
    sunday = date(2027, 3, 28)  # clocks jump 02:00 -> 03:00
    result = slots(tz="Europe/Berlin", day=sunday, rules=[rule(6, "00:00", "05:00")], hrs=[hours(6, "00:00", "24:00")], interval=60, duration=60)
    assert [local_iso(s.start, "Europe/Berlin") for s in result] == [
        "2027-03-28T00:00:00+01:00",
        "2027-03-28T01:00:00+01:00",
        "2027-03-28T03:00:00+02:00",
        "2027-03-28T04:00:00+02:00",
    ]


def test_berlin_fall_back_day_offers_repeated_hour_twice() -> None:
    sunday = date(2027, 10, 31)  # clocks go back 03:00 -> 02:00
    result = slots(tz="Europe/Berlin", day=sunday, rules=[rule(6, "00:00", "04:00")], hrs=[hours(6, "00:00", "24:00")], interval=60, duration=60)
    assert [local_iso(s.start, "Europe/Berlin") for s in result] == [
        "2027-10-31T00:00:00+02:00",
        "2027-10-31T01:00:00+02:00",
        "2027-10-31T02:00:00+02:00",
        "2027-10-31T02:00:00+01:00",
        "2027-10-31T03:00:00+01:00",
    ]
    assert len({s.start for s in result}) == 5  # distinct instants


def test_invalid_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        slots(rules=[rule(0, "09:00", "10:00")], hrs=[hours(0, "08:00", "18:00")], duration=0)
