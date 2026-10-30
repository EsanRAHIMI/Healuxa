"""Authorisation matrix: customer / coordinator / supervisor / stranger / other tenant / forged headers."""

from __future__ import annotations

from httpx import AsyncClient

from concierge_service.api.deps import principal_headers
from helpers import (
    CASE_BODY,
    OTHER_TENANT,
    coordinator,
    create_case,
    customer,
    new_user,
    ok,
    supervisor,
    working_case,
)


async def test_forged_identity_headers_are_rejected(client: AsyncClient) -> None:
    forged = {"X-Healuxa-User": new_user(), "X-Healuxa-Perms": "concierge:request,concierge:supervise"}
    assert (await client.post("/v1/concierge/cases", json=CASE_BODY, headers=forged)).status_code == 401
    assert (await client.get("/v1/concierge/queue", headers=forged)).status_code == 401


async def test_wrong_edge_secret_is_rejected(client: AsyncClient) -> None:
    headers = {**customer(new_user()), "X-Healuxa-Edge-Secret": "not-the-secret"}
    assert (await client.get("/v1/concierge/cases", headers=headers)).status_code == 401


async def test_missing_permission_cannot_submit(client: AsyncClient) -> None:
    response = await client.post("/v1/concierge/cases", json=CASE_BODY, headers=principal_headers(new_user(), permissions=""))
    assert response.status_code == 403


async def test_customer_sees_only_own_cases(client: AsyncClient) -> None:
    alice, bob = new_user(), new_user()
    case = await create_case(client, alice)
    await create_case(client, bob)
    listing = await ok(await client.get("/v1/concierge/cases", headers=customer(alice)))
    assert [c["id"] for c in listing["data"]] == [case["id"]]
    assert (await client.get(f"/v1/concierge/cases/{case['id']}", headers=customer(bob))).status_code == 404
    assert (await client.get(f"/v1/concierge/cases/{case['id']}/options", headers=customer(bob))).status_code == 404


async def test_stranger_without_permissions_gets_404(client: AsyncClient) -> None:
    case = await create_case(client, new_user())
    stranger = principal_headers(new_user(), permissions="")
    assert (await client.get(f"/v1/concierge/cases/{case['id']}", headers=stranger)).status_code == 404
    response = await client.post(f"/v1/concierge/cases/{case['id']}/transitions", json={"to_status": "cancelled"}, headers=stranger)
    assert response.status_code == 404


async def test_customer_cannot_use_queue_notes_or_audit(client: AsyncClient) -> None:
    owner = new_user()
    case = await create_case(client, owner)
    assert (await client.get("/v1/concierge/queue", headers=customer(owner))).status_code == 403
    assert (await client.get(f"/v1/concierge/cases/{case['id']}/notes", headers=customer(owner))).status_code == 403
    assert (await client.post(f"/v1/concierge/cases/{case['id']}/notes", json={"body": "x"}, headers=customer(owner))).status_code == 403
    assert (await client.get(f"/v1/concierge/cases/{case['id']}/audit", headers=customer(owner))).status_code == 403


async def test_coordinator_of_other_tenant_gets_404(client: AsyncClient) -> None:
    case = await create_case(client, new_user())
    foreign = coordinator(new_user(), tenant_id=OTHER_TENANT)
    assert (await client.get(f"/v1/concierge/cases/{case['id']}", headers=foreign)).status_code == 404
    assert (await client.post(f"/v1/concierge/cases/{case['id']}/assignment", json={}, headers=foreign)).status_code == 404
    queue = await ok(await client.get("/v1/concierge/queue", headers=foreign))
    assert queue["data"] == []
    foreign_boss = supervisor(new_user(), tenant_id=OTHER_TENANT)
    assert (await client.get(f"/v1/concierge/cases/{case['id']}/notes", headers=foreign_boss)).status_code == 404


async def test_customer_of_other_tenant_with_same_user_id_sees_nothing(client: AsyncClient) -> None:
    owner = new_user()
    case = await create_case(client, owner)
    assert (await client.get(f"/v1/concierge/cases/{case['id']}", headers=customer(owner, tenant_id=OTHER_TENANT))).status_code == 404


async def test_coordinator_sees_tenant_case_and_internal_notes_stay_internal(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, coord, owner = setup["case"]["id"], setup["coordinator"], setup["owner"]
    note = await ok(
        await client.post(f"/v1/concierge/cases/{case_id}/notes", json={"body": "Prefers morning calls."}, headers=coordinator(coord)), 201
    )
    notes = await ok(await client.get(f"/v1/concierge/cases/{case_id}/notes", headers=supervisor(new_user())))
    assert [n["id"] for n in notes["data"]] == [note["id"]]
    customer_view = await ok(await client.get(f"/v1/concierge/cases/{case_id}", headers=customer(owner)))
    assert "Prefers morning calls." not in str(customer_view)
    # Any tenant coordinator can read the case (work queue), not only the assignee.
    await ok(await client.get(f"/v1/concierge/cases/{case_id}", headers=coordinator(new_user())))
