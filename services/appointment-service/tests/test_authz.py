"""Authentication, RBAC permissions, ownership and tenant isolation, calendar views and pagination."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient

from helpers import TUESDAY, FakeDirectory, customer, hold, iso, local, manager, new_id, ok, requested


async def test_forged_identity_headers_are_rejected(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    forged = {"X-Healuxa-User": new_id(), "X-Healuxa-Perms": "appointments:create,appointments:manage"}
    body = {"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00"))}
    assert (await client.post("/v1/appointments", json=body, headers=forged)).status_code == 401
    assert (await client.get("/v1/appointments", headers=forged)).status_code == 401
    wrong_secret = {**customer(), "X-Healuxa-Edge-Secret": "guess"}
    assert (await client.get("/v1/appointments", headers=wrong_secret)).status_code == 401


async def test_missing_permissions_are_forbidden(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    read_only = customer(permissions="appointments:read")
    body = {"service_id": practice.service_id, "scheduled_at": iso(local(TUESDAY, "09:00"))}
    assert (await client.post("/v1/appointments", json=body, headers=read_only)).status_code == 403
    held = await hold(client, practice, customer(read_only["X-Healuxa-User"]), local(TUESDAY, "09:00"))
    response = await client.post(f"/v1/appointments/{held['id']}/status", json={"transition": "submit"}, headers=read_only)
    assert response.status_code == 403
    assert (await client.get("/v1/appointments", headers=customer(permissions=""))).status_code == 403


async def test_customers_see_only_their_own(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    alice, bob = customer(), customer()
    mine = await hold(client, practice, alice, local(TUESDAY, "09:00"))
    await hold(client, practice, bob, local(TUESDAY, "10:00"))
    listing = await ok(await client.get("/v1/appointments", headers=alice))
    assert [a["id"] for a in listing["data"]] == [mine["id"]]
    assert (await client.get(f"/v1/appointments/{mine['id']}", headers=bob)).status_code == 404
    assert (await client.get("/v1/appointments", params={"user_id": bob["X-Healuxa-User"]}, headers=alice)).status_code == 403
    assert (await client.post(f"/v1/appointments/{mine['id']}/status", json={"transition": "cancel"}, headers=bob)).status_code == 404


async def test_other_tenant_cannot_see_or_touch(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    alice = customer()
    appt = await hold(client, practice, alice, local(TUESDAY, "09:00"))
    europe = customer(alice["X-Healuxa-User"], tenant_id="healuxa-europe")  # same user id, other tenant
    assert (await client.get(f"/v1/appointments/{appt['id']}", headers=europe)).status_code == 404
    assert (await ok(await client.get("/v1/appointments", headers=europe)))["data"] == []
    assert (await client.get(f"/v1/appointments/{appt['id']}", headers=manager(tenant_id="healuxa-europe"))).status_code == 404


async def test_provider_and_facility_calendar_views(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    elsewhere = directory.add_practice(provider_id=practice.provider_id, owner=practice.owner)  # same provider, other facility
    a = await requested(client, practice, customer(), local(TUESDAY, "09:00"))
    b = await requested(client, elsewhere, customer(), local(TUESDAY, "11:00"))
    owner = await ok(await client.get("/v1/appointments", params={"provider_id": practice.provider_id}, headers=practice.owner_headers()))
    assert [x["id"] for x in owner["data"]] == [a["id"], b["id"]]
    # The scheduler of facility 1 sees this provider's bookings at their facility only.
    sched = await ok(await client.get("/v1/appointments", params={"provider_id": practice.provider_id}, headers=practice.scheduler_headers()))
    assert [x["id"] for x in sched["data"]] == [a["id"]]
    branch = await ok(await client.get("/v1/appointments", params={"branch_id": practice.branch_id}, headers=practice.admin_headers()))
    assert [x["id"] for x in branch["data"]] == [a["id"]]
    assert (await ok(await client.get("/v1/appointments", params={"branch_id": elsewhere.branch_id}, headers=practice.admin_headers())))["data"] == []
    stranger = await client.get("/v1/appointments", params={"provider_id": practice.provider_id}, headers=customer())
    assert stranger.status_code == 403
    billing = await client.get("/v1/appointments", params={"facility_id": practice.facility_id}, headers=practice.billing_headers())
    assert billing.status_code == 403
    staff = await ok(await client.get("/v1/appointments", params={"facility_id": elsewhere.facility_id}, headers=manager()))
    assert [x["id"] for x in staff["data"]] == [b["id"]]


async def test_date_range_status_filter_and_cursor_pagination(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    headers = customer()
    # Five holds are over the hold limit, so place them across two customers and list as the provider.
    ids = []
    for i, (offset, hhmm) in enumerate(zip((0, 1, 2, 3, 6), ("09:00", "10:00", "11:00", "12:00", "13:00"))):
        who = headers if i < 3 else customer()
        ids.append((await hold(client, practice, who, local(TUESDAY + timedelta(days=offset), hhmm)))["id"])
    owner = practice.owner_headers()
    page1 = await ok(await client.get("/v1/appointments", params={"provider_id": practice.provider_id, "limit": 2}, headers=owner))
    assert [x["id"] for x in page1["data"]] == ids[:2] and page1["page"]["has_more"] is True
    page2 = await ok(await client.get("/v1/appointments", params={"provider_id": practice.provider_id, "limit": 2, "cursor": page1["page"]["next_cursor"]}, headers=owner))
    page3 = await ok(await client.get("/v1/appointments", params={"provider_id": practice.provider_id, "limit": 2, "cursor": page2["page"]["next_cursor"]}, headers=owner))
    assert [x["id"] for x in page2["data"] + page3["data"]] == ids[2:] and page3["page"]["next_cursor"] is None
    desc = await ok(await client.get("/v1/appointments", params={"provider_id": practice.provider_id, "sort": "-scheduled_at"}, headers=owner))
    assert [x["id"] for x in desc["data"]] == list(reversed(ids))
    window = {"provider_id": practice.provider_id, "from": iso(local(TUESDAY + timedelta(days=1), "00:00")), "to": iso(local(TUESDAY + timedelta(days=3), "00:00"))}
    assert [x["id"] for x in (await ok(await client.get("/v1/appointments", params=window, headers=owner)))["data"]] == ids[1:3]
    assert (await ok(await client.get("/v1/appointments", params={"status": "confirmed"}, headers=headers)))["data"] == []
    bad = await client.get("/v1/appointments", params={"cursor": "not-a-cursor"}, headers=headers)
    assert bad.status_code == 422
    mismatched = await client.get("/v1/appointments", params={"provider_id": practice.provider_id, "sort": "-scheduled_at", "cursor": page1["page"]["next_cursor"]}, headers=owner)
    assert mismatched.status_code == 422


async def test_calendar_lookup_outage_fails_closed(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice()
    directory.down = True
    response = await client.get("/v1/appointments", params={"provider_id": practice.provider_id}, headers=practice.owner_headers())
    assert response.status_code == 503
