"""Provider options and secure messaging (customer ⇄ assigned coordinator only)."""

from __future__ import annotations

from httpx import AsyncClient
from ulid import ULID

from helpers import OTHER_TENANT, coordinator, create_case, customer, move, new_user, ok, propose, supervisor, working_case


async def test_options_store_references_only_and_selection_is_exclusive(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, coord, owner = setup["case"]["id"], setup["coordinator"], setup["owner"]
    a = await propose(client, case_id, coord)
    b = await propose(client, case_id, coord, label="Option B")
    assert set(a) == {"id", "case_id", "provider_id", "facility_id", "branch_id", "service_id", "label", "status", "proposed_by", "created_at"}
    selected = await ok(await client.post(f"/v1/concierge/cases/{case_id}/options/{b['id']}/select", headers=customer(owner)))
    assert selected["status"] == "selected"
    listing = await ok(await client.get(f"/v1/concierge/cases/{case_id}/options", headers=customer(owner)))
    assert {o["id"]: o["status"] for o in listing["data"]} == {a["id"]: "not_selected", b["id"]: "selected"}
    again = await client.post(f"/v1/concierge/cases/{case_id}/options/{a['id']}/select", headers=customer(owner))
    assert again.status_code == 409


async def test_duplicate_option_rejected(client: AsyncClient) -> None:
    setup = await working_case(client)
    ref = {"provider_id": str(ULID()), "branch_id": str(ULID())}
    await propose(client, setup["case"]["id"], setup["coordinator"], **ref)
    response = await client.post(f"/v1/concierge/cases/{setup['case']['id']}/options", json=ref, headers=coordinator(setup["coordinator"]))
    assert response.status_code == 409


async def test_only_assigned_coordinator_or_supervisor_proposes(client: AsyncClient) -> None:
    setup = await working_case(client)
    body = {"provider_id": str(ULID())}
    other = await client.post(f"/v1/concierge/cases/{setup['case']['id']}/options", json=body, headers=coordinator(new_user()))
    assert other.status_code == 403
    by_customer = await client.post(f"/v1/concierge/cases/{setup['case']['id']}/options", json=body, headers=customer(setup["owner"]))
    assert by_customer.status_code == 403
    await ok(await client.post(f"/v1/concierge/cases/{setup['case']['id']}/options", json=body, headers=supervisor(new_user())), 201)


async def test_options_cannot_be_proposed_before_assignment(client: AsyncClient) -> None:
    case = await create_case(client, new_user())
    response = await client.post(f"/v1/concierge/cases/{case['id']}/options", json={"provider_id": str(ULID())}, headers=supervisor(new_user()))
    assert response.status_code == 409


async def test_another_customer_cannot_select_option(client: AsyncClient) -> None:
    setup = await working_case(client)
    option = await propose(client, setup["case"]["id"], setup["coordinator"])
    response = await client.post(f"/v1/concierge/cases/{setup['case']['id']}/options/{option['id']}/select", headers=customer(new_user()))
    assert response.status_code == 404


async def test_messaging_between_customer_and_assigned_coordinator(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, coord, owner = setup["case"]["id"], setup["coordinator"], setup["owner"]
    m1 = await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": "Hello, can you arrange airport pickup?"}, headers=customer(owner)), 201)
    m2 = await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": "Yes, booked for 14:00."}, headers=coordinator(coord)), 201)
    assert m1["sender_role"] == "customer" and m2["sender_role"] == "coordinator"
    thread = await ok(await client.get(f"/v1/concierge/cases/{case_id}/messages", headers=coordinator(coord)))
    assert [m["id"] for m in thread["data"]] == [m1["id"], m2["id"]]


async def test_no_third_party_can_read_or_post_messages(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id = setup["case"]["id"]
    await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": "private"}, headers=customer(setup["owner"])), 201)
    outsiders = [
        coordinator(new_user()),
        supervisor(new_user()),
        customer(new_user()),
        coordinator(setup["coordinator"], tenant_id=OTHER_TENANT),
    ]
    for headers in outsiders:
        assert (await client.get(f"/v1/concierge/cases/{case_id}/messages", headers=headers)).status_code == 404
        assert (await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": "hi"}, headers=headers)).status_code == 404


async def test_read_receipts_mark_only_counterparty_messages(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, coord, owner = setup["case"]["id"], setup["coordinator"], setup["owner"]
    first = await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": "one"}, headers=coordinator(coord)), 201)
    await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": "two"}, headers=coordinator(coord)), 201)
    await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": "mine"}, headers=customer(owner)), 201)
    partial = await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages/read", json={"up_to_message_id": first["id"]}, headers=customer(owner)))
    assert partial == {"marked": 1}
    rest = await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages/read", headers=customer(owner)))
    assert rest == {"marked": 1}
    thread = await ok(await client.get(f"/v1/concierge/cases/{case_id}/messages", headers=coordinator(coord)))
    read = {m["body"]: m["read_at"] is not None for m in thread["data"]}
    assert read == {"one": True, "two": True, "mine": False}


async def test_messages_paginate(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, owner = setup["case"]["id"], setup["owner"]
    for i in range(5):
        await ok(await client.post(f"/v1/concierge/cases/{case_id}/messages", json={"body": f"m{i}"}, headers=customer(owner)), 201)
    page1 = await ok(await client.get(f"/v1/concierge/cases/{case_id}/messages", params={"limit": 3}, headers=customer(owner)))
    page2 = await ok(
        await client.get(f"/v1/concierge/cases/{case_id}/messages", params={"limit": 3, "cursor": page1["page"]["next_cursor"]}, headers=customer(owner))
    )
    assert [m["body"] for m in page1["data"] + page2["data"]] == [f"m{i}" for i in range(5)]
    assert page2["page"] == {"next_cursor": None, "limit": 3, "has_more": False}


async def test_messaging_closes_with_the_case(client: AsyncClient) -> None:
    setup = await working_case(client)
    await move(client, setup["case"]["id"], customer(setup["owner"]), "cancelled")
    response = await client.post(f"/v1/concierge/cases/{setup['case']['id']}/messages", json={"body": "still there?"}, headers=customer(setup["owner"]))
    assert response.status_code == 409
