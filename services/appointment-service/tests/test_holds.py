"""Reservation holds: creation rules, expiry (lazy + sweeper), idempotency, limits."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select

from appointment_service.config import settings
from appointment_service.domain.clock import clock
from appointment_service.domain.sweeper import sweep_once
from appointment_service.infra.db import SessionLocal
from appointment_service.infra.models import Appointment
from helpers import NOW, TUESDAY, FakeDirectory, customer, hold, iso, local, manager, new_id, ok, outbox, transition


async def _count() -> int:
    async with SessionLocal() as db:
        return int(await db.scalar(select(func.count()).select_from(Appointment)) or 0)


async def test_hold_is_created_with_expiry_and_audit(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(duration=45, buffer=15, price_minor=60000)
    headers = customer()
    response = await client.post(
        "/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00")), "channel": "web"}, headers=headers
    )
    body = await ok(response, 201)
    assert response.headers["Location"] == f"/v1/appointments/{body['id']}"
    assert response.headers["ETag"] == '"v1"'
    assert body["status"] == "held" and body["user_id"] == headers["X-Healuxa-User"]
    assert body["hold_expires_at"].startswith(iso(NOW + timedelta(minutes=10))[:19])
    assert body["scheduled_at"].startswith("2027-03-02T05:00:00") and body["ends_at"].startswith("2027-03-02T05:45:00")
    assert body["local_start"] == "2027-03-02T09:00:00+04:00" and body["timezone"] == "Asia/Dubai"
    assert body["price"] == {"amount_minor": 60000, "currency": "AED"} and body["payment_status"] == "not_required"
    assert (body["provider_id"], body["facility_id"], body["branch_id"]) == (practice.provider_id, practice.facility_id, practice.branch_id)
    history = await ok(await client.get(f"/v1/appointments/{body['id']}/transitions", headers=headers))
    assert [(t["from_status"], t["to_status"], t["actor_type"]) for t in history["data"]] == [(None, "held", "customer")]
    assert await outbox() == []  # holds are private: nothing announced


async def test_hold_must_match_a_derived_slot(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(rules=[(1, "09:00", "12:00")])
    headers = customer()
    for start in (local(TUESDAY, "09:07"), local(TUESDAY, "13:00"), local(TUESDAY, "08:00")):
        response = await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(start)}, headers=headers)
        assert response.status_code == 422, start
    naive = await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": "2027-03-02T09:00:00"}, headers=headers)
    assert naive.status_code == 422
    assert await _count() == 0


async def test_hold_respects_lead_time_and_horizon(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(rules=[(d, "08:00", "17:00") for d in range(5)])
    too_soon = await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(local(NOW.date(), "08:30"))}, headers=customer())
    assert too_soon.status_code == 422 and "minutes from now" in too_soon.json()["detail"]
    too_far = await client.post(
        "/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY + timedelta(days=97), "09:00"))}, headers=customer()
    )
    assert too_far.status_code == 422


async def test_expired_hold_frees_slot_lazily_and_cannot_be_submitted(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    first = customer()
    held = await hold(client, practice, first, local(TUESDAY, "10:00"))
    second = customer()
    assert (await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": held["scheduled_at"]}, headers=second)).status_code == 409
    clock.travel(timedelta(minutes=settings.hold_ttl_minutes, seconds=1))
    assert (await ok(await client.get(f"/v1/appointments/{held['id']}", headers=first)))["status"] == "expired"
    late = await client.post(f"/v1/appointments/{held['id']}/status", json={"transition": "submit"}, headers=first)
    assert late.status_code == 409
    await hold(client, practice, second, local(TUESDAY, "10:00"))


async def test_sweeper_expires_stale_holds(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    held = await hold(client, practice, headers, local(TUESDAY, "11:00"))
    assert (await sweep_once(SessionLocal)).holds_expired == 0
    clock.travel(timedelta(minutes=10))
    result = await sweep_once(SessionLocal)
    assert result.holds_expired == 1
    history = await ok(await client.get(f"/v1/appointments/{held['id']}/transitions", headers=headers))
    assert history["data"][-1]["to_status"] == "expired" and history["data"][-1]["actor_type"] == "system"
    assert history["data"][-1]["reason_code"] == "hold_expired"


async def test_idempotent_create_replays_and_rejects_changed_body(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = {**customer(), "Idempotency-Key": "booking-key-0001"}
    body = {"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00"))}
    first = await ok(await client.post("/v1/appointments", json=body, headers=headers), 201)
    again = await ok(await client.post("/v1/appointments", json=body, headers=headers), 201)
    assert again["id"] == first["id"] and await _count() == 1
    changed = await client.post("/v1/appointments", json={**body, "scheduled_at": iso(local(TUESDAY, "09:30"))}, headers=headers)
    assert changed.status_code == 409 and changed.json()["code"] == "idempotency_conflict"
    # The key is scoped to the customer: another customer may use the same key value.
    other = {**customer(), "Idempotency-Key": "booking-key-0001"}
    assert (await client.post("/v1/appointments", json={**body, "scheduled_at": iso(local(TUESDAY, "11:00"))}, headers=other)).status_code == 201


async def test_concurrent_idempotent_retries_create_one_hold(client: AsyncClient, directory: FakeDirectory) -> None:
    import asyncio

    practice = directory.add_practice()
    headers = {**customer(), "Idempotency-Key": "retry-storm-0001"}
    body = {"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00"))}
    responses = await asyncio.gather(*(client.post("/v1/appointments", json=body, headers=headers) for _ in range(5)))
    assert {r.status_code for r in responses} == {201}
    assert len({r.json()["id"] for r in responses}) == 1 and await _count() == 1


async def test_customer_hold_limit(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    for hhmm in ("09:00", "10:00", "11:00"):
        await hold(client, practice, headers, local(TUESDAY, hhmm))
    response = await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "12:00"))}, headers=headers)
    assert response.status_code == 409 and "active holds" in response.json()["detail"]


async def test_customer_cannot_double_book_overlapping_time(client: AsyncClient, directory: FakeDirectory) -> None:
    dermatology = directory.add_practice(duration=60)
    physio = directory.add_practice(duration=60)
    headers = customer()
    await hold(client, dermatology, headers, local(TUESDAY, "09:00"))
    response = await client.post("/v1/appointments", json={"service_id": physio.service_id, "scheduled_at": iso(local(TUESDAY, "09:30"))}, headers=headers)
    assert response.status_code == 409 and "customer already has" in response.json()["detail"]


async def test_provider_outage_on_create_is_503_and_writes_nothing(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    directory.down = True
    response = await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00"))}, headers=customer())
    assert response.status_code == 503 and await _count() == 0


async def test_booking_on_behalf_requires_manage(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    patient = new_id()
    body = {"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00")), "user_id": patient, "channel": "concierge"}
    assert (await client.post("/v1/appointments", json=body, headers=customer())).status_code == 403
    created = await ok(await client.post("/v1/appointments", json=body, headers=manager()), 201)
    assert created["user_id"] == patient and created["channel"] == "concierge"
    # The customer sees and can submit the hold the concierge placed for them.
    await transition(client, created["id"], customer(patient), "submit")


async def test_provider_cannot_book_own_offering_and_unknown_service_404(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    own = await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00"))}, headers=practice.owner_headers())
    assert own.status_code == 422
    unknown = await client.post("/v1/appointments", json={"service_id": new_id(), "scheduled_at": iso(local(TUESDAY, "09:00"))}, headers=customer())
    assert unknown.status_code == 404
