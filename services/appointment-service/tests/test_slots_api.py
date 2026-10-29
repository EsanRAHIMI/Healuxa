"""GET /v1/services/{id}/slots — provider-service facts + this service's bookings."""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient

from appointment_service.domain.clock import clock
from helpers import TUESDAY, FakeDirectory, customer, hold, iso, local, ok


def _url(practice) -> str:
    return f"/v1/services/{practice.service_id}/slots"


async def test_slots_are_utc_with_branch_zone_and_public(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(rules=[(1, "09:00", "11:00")], duration=60)
    body = await ok(await client.get(_url(practice), params={"from": str(TUESDAY), "to": str(TUESDAY)}))
    assert body["timezone"] == "Asia/Dubai" and body["from"] == str(TUESDAY)
    assert body["duration_minutes"] == 60 and body["provider_id"] == practice.provider_id
    assert [s["scheduled_at"] for s in body["slots"]] == ["2027-03-02T05:00:00Z", "2027-03-02T05:15:00Z", "2027-03-02T05:30:00Z", "2027-03-02T05:45:00Z", "2027-03-02T06:00:00Z"]
    assert body["slots"][0]["local_start"] == "2027-03-02T09:00:00+04:00"
    assert body["slots"][0]["ends_at"] == "2027-03-02T06:00:00Z"


async def test_berlin_branch_slots_cross_dst(client: AsyncClient, directory: FakeDirectory) -> None:
    clock.travel(timedelta(days=20))  # 2027-03-21
    practice = directory.add_practice(tz="Europe/Berlin", rules=[(0, "09:00", "09:30")], duration=30)
    body = await ok(await client.get(_url(practice), params={"from": "2027-03-22", "to": "2027-03-29"}))
    assert [s["scheduled_at"] for s in body["slots"]] == ["2027-03-22T08:00:00Z", "2027-03-29T07:00:00Z"]
    assert [s["local_start"] for s in body["slots"]] == ["2027-03-22T09:00:00+01:00", "2027-03-29T09:00:00+02:00"]


async def test_lead_time_hides_imminent_slots(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(rules=[(0, "08:00", "12:00")], duration=60)
    body = await ok(await client.get(_url(practice), params={"from": "2027-03-01", "to": "2027-03-01"}))
    # Now is 08:00 local and the minimum lead is 60 minutes.
    assert body["slots"][0]["local_start"] == "2027-03-01T09:00:00+04:00"


async def test_exceptions_from_provider_service_block_slots(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(
        rules=[(1, "09:00", "11:00")], duration=60, exceptions=[(local(TUESDAY, "09:00"), local(TUESDAY, "09:30"))]
    )
    body = await ok(await client.get(_url(practice), params={"from": str(TUESDAY), "to": str(TUESDAY)}))
    assert [s["local_start"][11:16] for s in body["slots"]] == ["09:30", "09:45", "10:00"]


async def test_holds_take_slots_and_expired_holds_free_them(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(rules=[(1, "09:00", "10:00")], duration=30, buffer=0)
    params = {"from": str(TUESDAY), "to": str(TUESDAY)}
    before = await ok(await client.get(_url(practice), params=params))
    assert len(before["slots"]) == 3  # 09:00, 09:15, 09:30
    await hold(client, practice, customer(), local(TUESDAY, "09:00"))
    taken = await ok(await client.get(_url(practice), params=params))
    assert [s["local_start"][11:16] for s in taken["slots"]] == ["09:30"]
    clock.travel(timedelta(minutes=11))  # hold TTL is 10 minutes; lazy expiry on read
    freed = await ok(await client.get(_url(practice), params=params))
    assert len(freed["slots"]) == 3


async def test_provider_service_outage_returns_503_not_slots(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    directory.down = True
    response = await client.get(_url(practice), params={"from": str(TUESDAY), "to": str(TUESDAY)})
    assert response.status_code == 503 and response.json()["code"] == "service_unavailable"


async def test_unknown_or_unbookable_offering_is_404(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(bookable=False)
    params = {"from": str(TUESDAY), "to": str(TUESDAY)}
    assert (await client.get(_url(practice), params=params)).status_code == 404
    assert (await client.get("/v1/services/01HZZZZZZZZZZZZZZZZZZZZZZZ/slots", params=params)).status_code == 404


async def test_slot_range_is_validated(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    assert (await client.get(_url(practice), params={"from": "2027-03-05", "to": "2027-03-04"})).status_code == 422
    too_long = {"from": "2027-03-01", "to": str(date(2027, 3, 1) + timedelta(days=31))}
    assert (await client.get(_url(practice), params=too_long)).status_code == 422


async def test_slot_discovery_is_tenant_scoped(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(tenant_id="healuxa-europe")
    params = {"from": str(TUESDAY), "to": str(TUESDAY)}
    # Anonymous callers browse the public tenant; the European practice is not visible there.
    assert (await client.get(_url(practice), params=params)).status_code == 404
    body = await ok(await client.get(_url(practice), params=params, headers=customer(tenant_id="healuxa-europe")))
    assert body["slots"] and iso(local(TUESDAY, "09:00")) == body["slots"][0]["scheduled_at"]
