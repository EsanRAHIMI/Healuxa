"""Facilities, staff roles and the affiliation handshake."""

from __future__ import annotations

from httpx import AsyncClient

from helpers import (
    BRANCH_BODY,
    FACILITY_BODY,
    create_provider,
    create_verified_facility,
    new_user,
    ok,
    outbox_events,
    staff,
    user,
    verify_provider,
)


async def test_creator_becomes_admin_and_license_is_unique(client: AsyncClient) -> None:
    admin = new_user()
    facility = await ok(await client.post("/v1/facilities", json=FACILITY_BODY, headers=user(admin)), 201)
    assert facility["status"] == "pending"
    team = await ok(await client.get(f"/v1/facilities/{facility['id']}/staff", headers=user(admin)))
    assert [(m["user_id"], m["role"]) for m in team["data"]] == [(admin, "facility_admin")]
    duplicate = await client.post("/v1/facilities", json=FACILITY_BODY, headers=user(new_user()))
    assert duplicate.status_code == 409


async def test_pending_facility_is_not_public(client: AsyncClient) -> None:
    facility = await ok(await client.post("/v1/facilities", json=FACILITY_BODY, headers=user(new_user())), 201)
    assert (await client.get(f"/v1/facilities/{facility['id']}")).status_code == 404
    await ok(await client.post(f"/v1/facilities/{facility['id']}/review", json={"decision": "verify"}, headers=staff()))
    public = await ok(await client.get(f"/v1/facilities/{facility['id']}"))
    assert public["status"] == "active"


async def test_non_admin_cannot_manage_facility(client: AsyncClient) -> None:
    facility, branch = await create_verified_facility(client, new_user())
    outsider = user(new_user())
    assert (await client.post(f"/v1/facilities/{facility['id']}/branches", json=BRANCH_BODY, headers=outsider)).status_code == 403
    assert (await client.put(f"/v1/branches/{branch['id']}/operating-hours", json={"windows": []}, headers=outsider)).status_code == 403
    assert (await client.get(f"/v1/facilities/{facility['id']}/staff", headers=outsider)).status_code == 403


async def test_last_admin_cannot_be_removed(client: AsyncClient) -> None:
    admin = new_user()
    facility, _ = await create_verified_facility(client, admin)
    blocked = await client.delete(f"/v1/facilities/{facility['id']}/staff/{admin}", headers=user(admin))
    assert blocked.status_code == 409
    second = new_user()
    await ok(await client.post(f"/v1/facilities/{facility['id']}/staff", json={"user_id": second, "role": "facility_admin"}, headers=user(admin)), 201)
    assert (await client.delete(f"/v1/facilities/{facility['id']}/staff/{admin}", headers=user(second))).status_code == 204


async def test_scheduler_role_cannot_add_staff(client: AsyncClient) -> None:
    admin, scheduler = new_user(), new_user()
    facility, _ = await create_verified_facility(client, admin)
    await ok(await client.post(f"/v1/facilities/{facility['id']}/staff", json={"user_id": scheduler, "role": "scheduler"}, headers=user(admin)), 201)
    response = await client.post(f"/v1/facilities/{facility['id']}/staff", json={"user_id": new_user(), "role": "billing"}, headers=user(scheduler))
    assert response.status_code == 403


async def test_overlapping_operating_hours_rejected(client: AsyncClient) -> None:
    admin = new_user()
    _, branch = await create_verified_facility(client, admin)
    body = {"windows": [{"weekday": 0, "start": "09:00", "end": "13:00"}, {"weekday": 0, "start": "12:00", "end": "17:00"}]}
    assert (await client.put(f"/v1/branches/{branch['id']}/operating-hours", json=body, headers=user(admin))).status_code == 422


async def test_affiliation_handshake(client: AsyncClient) -> None:
    owner, admin = new_user(), new_user()
    provider = await create_provider(client, owner)
    _, branch = await create_verified_facility(client, admin)
    affiliation = await ok(
        await client.post("/v1/affiliations", json={"provider_id": provider["id"], "branch_id": branch["id"]}, headers=user(owner)), 201
    )
    assert affiliation["initiated_by"] == "provider"
    url = f"/v1/affiliations/{affiliation['id']}/decision"

    # The initiator cannot approve its own request.
    assert (await client.post(url, json={"decision": "approve"}, headers=user(owner))).status_code == 403
    # Facility approves, but the provider is not verified yet.
    assert (await client.post(url, json={"decision": "approve"}, headers=user(admin))).status_code == 422

    await verify_provider(client, provider["id"], owner)
    approved = await ok(await client.post(url, json={"decision": "approve"}, headers=user(admin)))
    assert approved["status"] == "active"

    duplicate = await client.post("/v1/affiliations", json={"provider_id": provider["id"], "branch_id": branch["id"]}, headers=user(owner))
    assert duplicate.status_code == 409

    ended = await ok(await client.post(url, json={"decision": "end"}, headers=user(owner)))
    assert ended["status"] == "ended"
    statuses = [e["payload"]["status"] for e in await outbox_events("catalog.affiliation_changed")]
    assert statuses == ["pending", "active", "ended"]


async def test_strangers_cannot_request_or_see_affiliations(client: AsyncClient) -> None:
    provider = await create_provider(client, new_user())
    facility, branch = await create_verified_facility(client, new_user())
    stranger = user(new_user())
    assert (await client.post("/v1/affiliations", json={"provider_id": provider["id"], "branch_id": branch["id"]}, headers=stranger)).status_code == 403
    assert (await client.get(f"/v1/facilities/{facility['id']}/affiliations", headers=stranger)).status_code == 404
