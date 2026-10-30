"""Booking requests are confirmed only by the provider side; payment hook gates confirmation."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import update

from appointment_service.config import settings
from appointment_service.domain.clock import clock
from appointment_service.domain.sweeper import sweep_once
from appointment_service.infra.db import SessionLocal
from appointment_service.infra.models import Appointment
from helpers import TUESDAY, FakeDirectory, customer, hold, local, manager, ok, outbox, requested, transition

START = local(TUESDAY + timedelta(days=1), "10:00")  # Wednesday, > 24h ahead


async def test_submit_creates_request_and_never_confirms(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    req = await requested(client, practice, headers, START)
    assert req["status"] == "requested" and req["requested_at"] and req["confirmed_at"] is None
    assert req["hold_expires_at"] is None
    events = await outbox()
    assert [e["type"] for e in events] == ["appointment.requested"]
    # The customer cannot confirm their own request.
    await transition(client, req["id"], headers, "accept", status=403)


async def test_provider_owner_accepts(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    req = await requested(client, practice, customer(), START)
    clock.travel(timedelta(minutes=7))
    accepted = await transition(client, req["id"], practice.owner_headers(), "accept")
    assert accepted["status"] == "confirmed" and accepted["confirmed_at"]
    assert [(r["offset_minutes"], r["status"]) for r in accepted["reminders"]] == [(1440, "scheduled"), (120, "scheduled")]
    events = {e["type"]: e for e in await outbox()}
    assert events["appointment.accepted"]["payload"]["response_seconds"] == 420
    assert events["appointment.created"]["payload"]["appointment_id"] == req["id"]


async def test_facility_scheduler_and_admin_may_confirm_but_billing_and_strangers_not(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    a = await requested(client, practice, customer(), START)
    b = await requested(client, practice, customer(), START + timedelta(hours=1))
    await transition(client, a["id"], practice.billing_headers(), "accept", status=404)  # billing cannot even see it
    await transition(client, a["id"], customer(), "accept", status=404)
    other_practice = directory.add_practice()
    await transition(client, a["id"], other_practice.owner_headers(), "accept", status=404)
    assert (await transition(client, a["id"], practice.scheduler_headers(), "accept"))["status"] == "confirmed"
    assert (await transition(client, b["id"], practice.admin_headers(), "accept"))["status"] == "confirmed"
    history = await ok(await client.get(f"/v1/appointments/{a['id']}/transitions", headers=practice.scheduler_headers()))
    assert history["data"][-1]["actor_type"] == "facility" and history["data"][-1]["actor_id"] == practice.scheduler


async def test_decline_records_reason_and_frees_slot(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    req = await requested(client, practice, customer(), START)
    await transition(client, req["id"], practice.owner_headers(), "decline", status=422, reason_code="customer_request")
    declined = await transition(client, req["id"], practice.owner_headers(), "decline", reason_code="no_capacity", reason="fully booked")
    assert declined["status"] == "declined" and declined["decline_reason"] == "no_capacity"
    payload = (await outbox("appointment.declined"))[0]["payload"]
    assert payload["reason"] == "no_capacity" and "fully booked" not in str(payload)
    await hold(client, practice, customer(), START)  # slot is free again


async def test_invalid_transitions_conflict(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    held = await hold(client, practice, headers, START)
    await transition(client, held["id"], practice.owner_headers(), "accept", status=409)  # not submitted yet
    await transition(client, held["id"], practice.owner_headers(), "complete", status=409)
    await transition(client, held["id"], headers, "submit")
    await transition(client, held["id"], headers, "submit", status=409)


async def test_payment_gate_blocks_confirmation_until_authorized(client: AsyncClient, directory: FakeDirectory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "payment_required", True)
    practice = directory.add_practice(price_minor=60000)
    req = await requested(client, practice, customer(), START)
    assert req["payment_status"] == "pending"
    blocked = await client.post(f"/v1/appointments/{req['id']}/status", json={"transition": "accept"}, headers=practice.owner_headers())
    assert blocked.status_code == 409 and "Payment" in blocked.json()["detail"]
    async with SessionLocal() as db:  # stands in for the future payment.succeeded consumer
        await db.execute(update(Appointment).where(Appointment.id == req["id"]).values(payment_status="authorized"))
        await db.commit()
    assert (await transition(client, req["id"], practice.owner_headers(), "accept"))["status"] == "confirmed"


async def test_free_offering_needs_no_payment_even_when_gated(client: AsyncClient, directory: FakeDirectory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "payment_required", True)
    practice = directory.add_practice(price_minor=None)
    req = await requested(client, practice, customer(), START)
    assert req["payment_status"] == "not_required" and req["price"] is None
    await transition(client, req["id"], practice.owner_headers(), "accept")


async def test_accept_refused_when_practice_no_longer_bookable(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    req = await requested(client, practice, customer(), START)
    directory.set_bookable(practice, False)
    await transition(client, req["id"], practice.owner_headers(), "accept", status=409)
    directory.down = True
    response = await client.post(f"/v1/appointments/{req['id']}/status", json={"transition": "accept"}, headers=practice.owner_headers())
    assert response.status_code == 503


async def test_unanswered_request_expires_at_start(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    req = await requested(client, practice, customer(), START)
    clock.freeze(START)
    result = await sweep_once(SessionLocal)
    assert result.requests_expired == 1
    expired = (await outbox("appointment.expired"))[0]["payload"]
    assert expired["appointment_id"] == req["id"]
    await transition(client, req["id"], manager(), "accept", status=409)
