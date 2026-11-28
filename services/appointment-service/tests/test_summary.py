"""Practice reporting: counts per status and completed revenue, under the calendar access rules."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient

from helpers import TUESDAY, FakeDirectory, confirmed, customer, hold, iso, local, new_id, ok, requested, transition


async def test_summary_counts_by_status_and_completed_revenue(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    other = directory.add_practice()
    await hold(client, practice, customer(), local(TUESDAY, "09:00"))  # never requested: not a booking
    await requested(client, practice, customer(), local(TUESDAY, "10:00"))
    await confirmed(client, practice, customer(), local(TUESDAY, "11:00"))
    cancelled = await confirmed(client, practice, customer(), local(TUESDAY, "12:00"))
    await transition(client, cancelled["id"], practice.owner_headers(), "cancel", reason_code="provider_unavailable")
    await requested(client, other, customer(), local(TUESDAY, "10:00"))

    params = {"provider_id": practice.provider_id, "from": iso(local(TUESDAY, "00:00")), "to": iso(local(TUESDAY, "00:00") + timedelta(days=1))}
    report = await ok(await client.get("/v1/appointments/summary", params=params, headers=practice.owner_headers()))
    assert report["by_status"] == {"requested": 1, "confirmed": 1, "cancelled": 1}
    assert report["total"] == 3
    assert report["completed_revenue"] == []

    outside = {**params, "from": iso(local(TUESDAY, "00:00") + timedelta(days=1)), "to": iso(local(TUESDAY, "00:00") + timedelta(days=2))}
    assert (await ok(await client.get("/v1/appointments/summary", params=outside, headers=practice.owner_headers())))["total"] == 0


async def test_summary_enforces_scope(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    other = directory.add_practice()
    await requested(client, other, customer(), local(TUESDAY, "10:00"))
    window = {"from": iso(local(TUESDAY, "00:00")), "to": iso(local(TUESDAY, "00:00") + timedelta(days=1))}

    # A customer has no practice scope at all.
    assert (await client.get("/v1/appointments/summary", params={**window, "provider_id": practice.provider_id}, headers=customer())).status_code == 403
    # A practitioner asking about someone else's practice sees nothing of it.
    foreign = await ok(await client.get("/v1/appointments/summary", params={**window, "provider_id": other.provider_id}, headers=practice.owner_headers()))
    assert foreign["total"] == 0
    # A scope and a sane window are required.
    assert (await client.get("/v1/appointments/summary", params=window, headers=practice.owner_headers())).status_code == 422
    reversed_window = {"provider_id": practice.provider_id, "from": window["to"], "to": window["from"]}
    assert (await client.get("/v1/appointments/summary", params=reversed_window, headers=practice.owner_headers())).status_code == 422
    assert (await client.get("/v1/appointments/summary", params={**window, "provider_id": new_id()})).status_code == 401
