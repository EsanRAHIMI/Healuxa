"""Outbox events conform to packages/event-contracts and carry no health data; reminder hand-off."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient

from appointment_service.domain.clock import clock
from appointment_service.domain.sweeper import sweep_once
from appointment_service.infra.db import SessionLocal
from helpers import TUESDAY, FakeDirectory, confirmed, customer, iso, local, ok, outbox, requested, transition, validate_event

START = local(TUESDAY + timedelta(days=2), "10:00")  # Thursday
ALLOWED_PAYLOAD_KEYS = {
    "appointment_id", "user_id", "provider_id", "service_id", "milestone_id", "facility_id", "branch_id", "scheduled_at",
    "ends_at", "requested_at", "channel", "response_seconds", "reason", "completed_at", "duration_minutes", "amount",
    "party", "cancelled_at", "previous_status", "previous_appointment_id", "previous_scheduled_at", "status",
    "expired_at", "reminder_id", "offset_minutes", "due_at", "timezone",
}


async def test_every_staged_event_matches_the_contract(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    a = await confirmed(client, practice, headers, START)
    await ok(await client.post(f"/v1/appointments/{a['id']}/reschedule", json={"scheduled_at": iso(local(TUESDAY + timedelta(days=2), "14:00"))}, headers=practice.owner_headers()), 201)
    b = await requested(client, practice, customer(), local(TUESDAY + timedelta(days=3), "09:00"))
    await transition(client, b["id"], practice.owner_headers(), "decline", reason_code="out_of_scope", reason="private note about the patient")
    c = await confirmed(client, practice, customer(), local(TUESDAY + timedelta(days=3), "11:00"))
    await transition(client, c["id"], practice.owner_headers(), "cancel")
    d = await confirmed(client, practice, customer(), local(TUESDAY + timedelta(days=3), "13:00"))
    e = await requested(client, practice, customer(), local(TUESDAY + timedelta(days=3), "15:00"))
    clock.freeze(local(TUESDAY + timedelta(days=3), "13:20"))
    await transition(client, d["id"], practice.owner_headers(), "no_show")
    clock.freeze(local(TUESDAY + timedelta(days=3), "15:00"))
    await sweep_once(SessionLocal)  # expires request e
    f = await confirmed(client, practice, customer(), local(TUESDAY + timedelta(days=6), "10:00"))
    clock.freeze(local(TUESDAY + timedelta(days=6), "08:30"))
    assert (await sweep_once(SessionLocal)).reminders_dispatched == 2  # 24h and 2h reminders of f
    clock.freeze(local(TUESDAY + timedelta(days=6), "10:05"))
    await transition(client, f["id"], practice.owner_headers(), "complete")
    events = await outbox()
    types = {ev["type"] for ev in events}
    assert types == {
        "appointment.requested", "appointment.accepted", "appointment.created", "appointment.rescheduled",
        "appointment.declined", "appointment.cancelled", "appointment.no_show", "appointment.expired",
        "appointment.completed", "appointment.reminder_due",
    }
    for envelope in events:
        validate_event(envelope)
        assert envelope["producer"] == "appointment-service" and envelope["tenant_id"] == "healuxa-dubai"
        assert set(envelope["payload"]) <= ALLOWED_PAYLOAD_KEYS, envelope["payload"]
        assert "patient" not in str(envelope["payload"])
    assert e["id"] in {ev["payload"]["appointment_id"] for ev in events if ev["type"] == "appointment.expired"}


async def test_reminders_are_scheduled_dispatched_once_and_skipped_when_late(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    assert [(r["offset_minutes"], r["due_at"][:16]) for r in appt["reminders"]] == [(1440, iso(START - timedelta(days=1))[:16]), (120, iso(START - timedelta(hours=2))[:16])]
    clock.freeze(START - timedelta(hours=23))
    assert (await sweep_once(SessionLocal)).reminders_dispatched == 1
    assert (await sweep_once(SessionLocal)).reminders_dispatched == 0  # exactly once
    due = (await outbox("appointment.reminder_due"))[0]["payload"]
    assert due["offset_minutes"] == 1440 and due["timezone"] == "Asia/Dubai"
    current = await ok(await client.get(f"/v1/appointments/{appt['id']}", headers=headers))
    assert [r["status"] for r in current["reminders"]] == ["dispatched", "scheduled"]
    # A late booking (in 3 hours) gets only the 2h reminder; the 24h one is recorded as skipped.
    late = await confirmed(client, practice, customer(), START - timedelta(hours=20))
    assert [r["status"] for r in late["reminders"]] == ["skipped", "scheduled"]


async def test_cancelled_appointment_never_gets_reminders(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    await transition(client, appt["id"], headers, "cancel")
    clock.freeze(START - timedelta(minutes=30))
    assert (await sweep_once(SessionLocal)).reminders_dispatched == 0
    assert await outbox("appointment.reminder_due") == []
