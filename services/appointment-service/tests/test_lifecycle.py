"""Cancel, check-in, complete, no-show and reschedule rules, If-Match, idempotent transitions, audit trail."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient

from appointment_service.domain.clock import clock
from helpers import TUESDAY, FakeDirectory, confirmed, customer, hold, iso, local, manager, ok, outbox, requested, transition

WEDNESDAY = TUESDAY + timedelta(days=1)
START = local(WEDNESDAY, "10:00")


async def test_customer_cancels_before_cutoff_and_slot_frees(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    cancelled = await transition(client, appt["id"], headers, "cancel", reason="travel plans changed")
    assert cancelled["status"] == "cancelled" and cancelled["cancelled_by"] == "customer"
    assert {r["status"] for r in cancelled["reminders"]} == {"cancelled"}
    payload = (await outbox("appointment.cancelled"))[0]["payload"]
    assert payload["party"] == "customer" and payload["reason"] == "customer_request" and payload["previous_status"] == "confirmed"
    assert "travel" not in str(payload)
    await hold(client, practice, customer(), START)


async def test_customer_cancel_cutoff_but_provider_may_still_cancel(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    clock.freeze(START - timedelta(minutes=119))  # inside the 120 minute cut-off
    late = await client.post(f"/v1/appointments/{appt['id']}/status", json={"transition": "cancel"}, headers=headers)
    assert late.status_code == 409 and "cancelled by the customer until" in late.json()["detail"]
    done = await transition(client, appt["id"], practice.owner_headers(), "cancel", reason_code="provider_unavailable")
    assert done["cancelled_by"] == "provider"
    assert (await outbox("appointment.cancelled"))[0]["payload"]["reason"] == "provider_unavailable"


async def test_releasing_a_hold_is_silent_and_customer_only(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    held = await hold(client, practice, headers, START)
    await transition(client, held["id"], practice.owner_headers(), "cancel", status=403)  # visible to the practice, but only the customer releases a hold
    released = await transition(client, held["id"], headers, "cancel")
    assert released["status"] == "cancelled" and await outbox() == []


async def test_check_in_window_and_completion(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(price_minor=60000)
    appt = await confirmed(client, practice, customer(), START)
    staff = practice.scheduler_headers()
    clock.freeze(START - timedelta(minutes=61))
    await transition(client, appt["id"], staff, "check_in", status=409)
    await transition(client, appt["id"], staff, "complete", status=409)  # not started yet
    clock.freeze(START - timedelta(minutes=30))
    assert (await transition(client, appt["id"], staff, "check_in"))["status"] == "checked_in"
    await transition(client, appt["id"], staff, "cancel", status=409)
    clock.freeze(START + timedelta(minutes=25))
    done = await transition(client, appt["id"], practice.owner_headers(), "complete")
    assert done["status"] == "completed" and done["completed_at"]
    payload = (await outbox("appointment.completed"))[0]["payload"]
    assert payload["duration_minutes"] == 30 and payload["amount"] == {"amount_minor": 60000, "currency": "AED"}


async def test_customer_cannot_run_practice_transitions(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    clock.freeze(START + timedelta(minutes=20))
    for name in ("check_in", "complete", "no_show"):
        await transition(client, appt["id"], headers, name, status=403)


async def test_no_show_rules(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    appt = await confirmed(client, practice, customer(), START)
    clock.freeze(START + timedelta(minutes=10))
    await transition(client, appt["id"], practice.owner_headers(), "no_show", status=409)  # inside grace period
    clock.freeze(START + timedelta(minutes=16))
    await transition(client, appt["id"], practice.owner_headers(), "no_show", status=403, party="provider")
    marked = await transition(client, appt["id"], practice.owner_headers(), "no_show")
    assert marked["status"] == "no_show" and marked["no_show_party"] == "customer"
    assert (await outbox("appointment.no_show"))[0]["payload"]["party"] == "customer"


async def test_platform_records_provider_no_show(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    appt = await confirmed(client, practice, customer(), START)
    clock.freeze(START + timedelta(minutes=30))
    marked = await transition(client, appt["id"], manager(), "no_show", party="provider")
    assert marked["no_show_party"] == "provider"


async def test_customer_reschedule_needs_reconfirmation(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    new_start = local(WEDNESDAY, "14:00")
    response = await client.post(f"/v1/appointments/{appt['id']}/reschedule", json={"scheduled_at": iso(new_start)}, headers=headers)
    new = await ok(response, 201)
    assert response.headers["Location"] == f"/v1/appointments/{new['id']}"
    assert new["status"] == "requested" and new["rescheduled_from_id"] == appt["id"]
    old = await ok(await client.get(f"/v1/appointments/{appt['id']}", headers=headers))
    assert old["status"] == "rescheduled" and old["rescheduled_to_id"] == new["id"]
    assert {r["status"] for r in old["reminders"]} == {"cancelled"}
    rescheduled = (await outbox("appointment.rescheduled"))[0]["payload"]
    assert rescheduled["previous_appointment_id"] == appt["id"] and rescheduled["status"] == "requested"
    assert (await outbox("appointment.requested"))[-1]["payload"]["appointment_id"] == new["id"]
    await hold(client, practice, customer(), START)  # original slot is free
    taken = await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(new_start)}, headers=customer())
    assert taken.status_code == 409


async def test_provider_reschedule_stays_confirmed_and_can_shift_overlapping(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(duration=60)
    appt = await confirmed(client, practice, customer(), START)
    shifted = local(WEDNESDAY, "10:30")  # overlaps its own old time: allowed, the old one is closed first
    new = await ok(await client.post(f"/v1/appointments/{appt['id']}/reschedule", json={"scheduled_at": iso(shifted)}, headers=practice.owner_headers()), 201)
    assert new["status"] == "confirmed" and len(new["reminders"]) == 2
    assert (await outbox("appointment.created"))[-1]["payload"]["appointment_id"] == new["id"]


async def test_reschedule_conflicts_roll_back_and_cutoff_applies(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    other = await hold(client, practice, customer(), local(WEDNESDAY, "15:00"))
    clash = await client.post(f"/v1/appointments/{appt['id']}/reschedule", json={"scheduled_at": other["scheduled_at"]}, headers=headers)
    assert clash.status_code == 409
    assert (await ok(await client.get(f"/v1/appointments/{appt['id']}", headers=headers)))["status"] == "confirmed"
    not_a_slot = await client.post(f"/v1/appointments/{appt['id']}/reschedule", json={"scheduled_at": iso(local(WEDNESDAY, "22:00"))}, headers=headers)
    assert not_a_slot.status_code == 422
    clock.freeze(START - timedelta(minutes=60))
    late = await client.post(f"/v1/appointments/{appt['id']}/reschedule", json={"scheduled_at": iso(local(WEDNESDAY, "16:00"))}, headers=headers)
    assert late.status_code == 409


async def test_if_match_and_idempotent_transitions(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    req = await requested(client, practice, headers, START)
    stale = await client.post(f"/v1/appointments/{req['id']}/status", json={"transition": "accept"}, headers={**practice.owner_headers(), "If-Match": '"v1"'})
    assert stale.status_code == 409
    owner = {**practice.owner_headers(), "If-Match": f'"v{req["version"]}"', "Idempotency-Key": "accept-key-0001"}
    first = await client.post(f"/v1/appointments/{req['id']}/status", json={"transition": "accept"}, headers=owner)
    assert first.status_code == 200 and first.headers["ETag"] == f'"v{req["version"] + 1}"'
    replay = await client.post(f"/v1/appointments/{req['id']}/status", json={"transition": "accept"}, headers=owner)
    assert replay.status_code == 200 and replay.json()["version"] == first.json()["version"]
    assert len(await outbox("appointment.accepted")) == 1
    misuse = await client.post(f"/v1/appointments/{req['id']}/status", json={"transition": "cancel"}, headers={**practice.owner_headers(), "Idempotency-Key": "accept-key-0001"})
    assert misuse.status_code == 409 and misuse.json()["code"] == "idempotency_conflict"


async def test_audit_trail_records_every_transition(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    appt = await confirmed(client, practice, headers, START)
    await transition(client, appt["id"], practice.admin_headers(), "cancel", reason_code="facility_closed", reason="water leak")
    history = await ok(await client.get(f"/v1/appointments/{appt['id']}/transitions", headers=headers))
    rows = [(t["from_status"], t["to_status"], t["actor_type"], t["actor_id"], t["reason_code"]) for t in history["data"]]
    customer_id = headers["X-Healuxa-User"]
    assert rows == [
        (None, "held", "customer", customer_id, None),
        ("held", "requested", "customer", customer_id, None),
        ("requested", "confirmed", "provider", practice.owner, None),
        ("confirmed", "cancelled", "facility", practice.admin, "facility_closed"),
    ]
    assert history["data"][-1]["reason"] == "water leak" and all(t["occurred_at"] for t in history["data"])
    assert (await client.get(f"/v1/appointments/{appt['id']}/transitions", headers=customer())).status_code == 404
