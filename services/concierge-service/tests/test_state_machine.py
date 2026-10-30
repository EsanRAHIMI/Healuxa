"""Case lifecycle: the explicit state graph, role rules and illegal transitions."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from concierge_service.domain import state_machine as sm
from helpers import (
    claim,
    coordinator,
    create_case,
    customer,
    move,
    new_user,
    ok,
    propose,
    supervisor,
    working_case,
)


def test_terminal_states_have_no_exits() -> None:
    assert sm.TRANSITIONS["completed"] == frozenset()
    assert sm.TRANSITIONS["cancelled"] == frozenset()
    assert set(sm.TRANSITIONS) == sm.OPEN | sm.TERMINAL


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        ("submitted", "completed"),
        ("submitted", "arranged"),
        ("triaged", "in_progress"),
        ("assigned", "arranged"),
        ("in_progress", "submitted"),
        ("completed", "in_progress"),
        ("cancelled", "submitted"),
        ("escalated", "completed"),
    ],
)
def test_illegal_edges_are_rejected(from_status: str, to_status: str) -> None:
    assert not sm.can_transition(from_status, to_status)


def test_only_supervisor_leaves_escalation() -> None:
    for role in ("customer", "coordinator"):
        assert not sm.role_may_transition(role, from_status="escalated", to_status="in_progress", is_assignee=True)
    assert sm.role_may_transition("supervisor", from_status="escalated", to_status="in_progress", is_assignee=False)


async def test_full_happy_path_to_completed(client: AsyncClient) -> None:
    owner, coord = new_user(), new_user()
    case = await create_case(client, owner)
    assert case["status"] == "submitted"
    case = await move(client, case["id"], coordinator(coord), "triaged")
    case = await claim(client, case["id"], coord)
    assert case["status"] == "assigned" and case["coordinator_id"] == coord
    case = await move(client, case["id"], coordinator(coord), "in_progress")
    option = await propose(client, case["id"], coord)
    case = await move(client, case["id"], coordinator(coord), "awaiting_customer")
    await ok(await client.post(f"/v1/concierge/cases/{case['id']}/options/{option['id']}/select", headers=customer(owner)))
    case = await ok(await client.get(f"/v1/concierge/cases/{case['id']}", headers=customer(owner)))
    assert case["status"] == "in_progress" and case["selected_option_id"] == option["id"]
    case = await move(client, case["id"], coordinator(coord), "arranged")
    case = await move(client, case["id"], coordinator(coord), "completed")
    assert case["status"] == "completed" and case["closed_at"] is not None


async def test_illegal_transition_returns_409(client: AsyncClient) -> None:
    owner, coord = new_user(), new_user()
    case = await create_case(client, owner)
    body = await move(client, case["id"], supervisor(coord), "completed", expect=409)
    assert body["code"] == "conflict"


async def test_completed_case_cannot_be_reopened(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, coord, owner = setup["case"]["id"], setup["coordinator"], setup["owner"]
    option = await propose(client, case_id, coord)
    await ok(await client.post(f"/v1/concierge/cases/{case_id}/options/{option['id']}/select", headers=customer(owner)))
    await move(client, case_id, coordinator(coord), "arranged")
    await move(client, case_id, coordinator(coord), "completed")
    await move(client, case_id, supervisor(new_user()), "in_progress", expect=409)
    await move(client, case_id, customer(owner), "cancelled", expect=409)


async def test_arranged_requires_a_selected_option(client: AsyncClient) -> None:
    setup = await working_case(client)
    body = await move(client, setup["case"]["id"], coordinator(setup["coordinator"]), "arranged", expect=409)
    assert "select" in body["detail"]


async def test_assigned_and_escalated_need_their_own_endpoints(client: AsyncClient) -> None:
    case = await create_case(client, new_user())
    await move(client, case["id"], supervisor(new_user()), "assigned", expect=422)
    await move(client, case["id"], supervisor(new_user()), "escalated", expect=422)


async def test_customer_may_only_cancel(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, owner = setup["case"]["id"], setup["owner"]
    await move(client, case_id, customer(owner), "awaiting_customer", expect=403)
    case = await move(client, case_id, customer(owner), "cancelled")
    assert case["status"] == "cancelled"


async def test_staff_cancel_requires_reason(client: AsyncClient) -> None:
    setup = await working_case(client)
    await move(client, setup["case"]["id"], coordinator(setup["coordinator"]), "cancelled", expect=422)
    case = await move(client, setup["case"]["id"], coordinator(setup["coordinator"]), "cancelled", reason="customer unreachable for 30 days")
    assert case["status"] == "cancelled"


async def test_non_assignee_coordinator_cannot_progress_case(client: AsyncClient) -> None:
    setup = await working_case(client)
    await move(client, setup["case"]["id"], coordinator(new_user()), "awaiting_customer", expect=403)


async def test_claimed_case_cannot_be_stolen(client: AsyncClient) -> None:
    setup = await working_case(client)
    response = await client.post(f"/v1/concierge/cases/{setup['case']['id']}/assignment", json={}, headers=coordinator(new_user()))
    assert response.status_code == 409


async def test_only_supervisor_assigns_to_someone_else(client: AsyncClient) -> None:
    case = await create_case(client, new_user())
    target = new_user()
    response = await client.post(
        f"/v1/concierge/cases/{case['id']}/assignment", json={"coordinator_id": target}, headers=coordinator(new_user())
    )
    assert response.status_code == 403
    case = await ok(
        await client.post(f"/v1/concierge/cases/{case['id']}/assignment", json={"coordinator_id": target}, headers=supervisor(new_user()))
    )
    assert case["coordinator_id"] == target and case["status"] == "assigned"


async def test_escalation_and_supervisor_resolution(client: AsyncClient) -> None:
    setup = await working_case(client)
    case_id, coord = setup["case"]["id"], setup["coordinator"]
    case = await ok(
        await client.post(f"/v1/concierge/cases/{case_id}/escalation", json={"reason": "no availability on dates"}, headers=coordinator(coord))
    )
    assert case["status"] == "escalated" and case["escalated_from"] == "in_progress"
    await move(client, case_id, coordinator(coord), "in_progress", expect=403)
    # Escalating twice is illegal.
    response = await client.post(f"/v1/concierge/cases/{case_id}/escalation", json={"reason": "again"}, headers=customer(setup["owner"]))
    assert response.status_code == 409
    boss, new_coord = new_user(), new_user()
    await ok(await client.post(f"/v1/concierge/cases/{case_id}/assignment", json={"coordinator_id": new_coord}, headers=supervisor(boss)))
    case = await move(client, case_id, supervisor(boss), "in_progress", reason="reassigned to senior coordinator")
    assert case["status"] == "in_progress" and case["coordinator_id"] == new_coord and case["escalated_from"] is None


async def test_customer_can_escalate_own_case(client: AsyncClient) -> None:
    owner = new_user()
    case = await create_case(client, owner)
    case = await ok(await client.post(f"/v1/concierge/cases/{case['id']}/escalation", json={"reason": "nobody replied"}, headers=customer(owner)))
    assert case["status"] == "escalated"
