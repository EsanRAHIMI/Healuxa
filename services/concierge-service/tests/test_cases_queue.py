"""Submission, data minimisation, idempotency, work queue filters, pagination and SLA."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update

from concierge_service.infra.db import SessionLocal
from concierge_service.infra.models import ConciergeCase
from helpers import CASE_BODY, claim, coordinator, create_case, customer, move, new_user, ok, supervisor


async def _overdue(case_id: str) -> None:
    async with SessionLocal() as db:
        await db.execute(
            update(ConciergeCase)
            .where(ConciergeCase.id == case_id)
            .values(first_response_due_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await db.commit()


async def test_submit_creates_submitted_case_with_sla(client: AsyncClient) -> None:
    owner = new_user()
    response = await client.post("/v1/concierge/cases", json=CASE_BODY, headers=customer(owner))
    case = await ok(response, 201)
    assert response.headers["location"] == f"/v1/concierge/cases/{case['id']}"
    assert case["status"] == "submitted" and case["customer_id"] == owner
    assert case["coordinator_id"] is None and case["sla_breached"] is False
    due = datetime.fromisoformat(case["first_response_due_at"])
    assert timedelta(minutes=230) < due - datetime.fromisoformat(case["created_at"]) <= timedelta(minutes=240)


async def test_no_clinical_fields_are_accepted(client: AsyncClient) -> None:
    response = await client.post("/v1/concierge/cases", json={**CASE_BODY, "diagnosis": "x"}, headers=customer(new_user()))
    assert response.status_code == 422
    minimal = await ok(await client.post("/v1/concierge/cases", json={"category": "logistics"}, headers=customer(new_user())), 201)
    assert minimal["needs_note"] is None and minimal["languages"] == []


async def test_invalid_category_dates_and_languages_rejected(client: AsyncClient) -> None:
    headers = customer(new_user())
    assert (await client.post("/v1/concierge/cases", json={"category": "surgery"}, headers=headers)).status_code == 422
    bad_dates = {**CASE_BODY, "preferred_start_date": "2026-12-10", "preferred_end_date": "2026-12-01"}
    assert (await client.post("/v1/concierge/cases", json=bad_dates, headers=headers)).status_code == 422
    assert (await client.post("/v1/concierge/cases", json={**CASE_BODY, "languages": ["English!"]}, headers=headers)).status_code == 422
    assert (await client.post("/v1/concierge/cases", json={**CASE_BODY, "needs_note": "x" * 2001}, headers=headers)).status_code == 422


async def test_idempotent_create_replays_same_case(client: AsyncClient) -> None:
    owner = new_user()
    headers = {**customer(owner), "Idempotency-Key": "concierge-create-0001"}
    first = await ok(await client.post("/v1/concierge/cases", json=CASE_BODY, headers=headers), 201)
    second = await ok(await client.post("/v1/concierge/cases", json=CASE_BODY, headers=headers), 201)
    assert first["id"] == second["id"]
    listing = await ok(await client.get("/v1/concierge/cases", headers=customer(owner)))
    assert len(listing["data"]) == 1


async def test_idempotency_key_with_different_body_conflicts(client: AsyncClient) -> None:
    headers = {**customer(new_user()), "Idempotency-Key": "concierge-create-0002"}
    await ok(await client.post("/v1/concierge/cases", json=CASE_BODY, headers=headers), 201)
    response = await client.post("/v1/concierge/cases", json={**CASE_BODY, "category": "logistics"}, headers=headers)
    assert response.status_code == 409 and response.json()["code"] == "idempotency_conflict"


async def test_idempotency_keys_are_scoped_per_customer(client: AsyncClient) -> None:
    key = {"Idempotency-Key": "shared-key-12345"}
    a = await ok(await client.post("/v1/concierge/cases", json=CASE_BODY, headers={**customer(new_user()), **key}), 201)
    b = await ok(await client.post("/v1/concierge/cases", json=CASE_BODY, headers={**customer(new_user()), **key}), 201)
    assert a["id"] != b["id"]


async def test_own_cases_paginate_newest_first(client: AsyncClient) -> None:
    owner = new_user()
    ids = [(await create_case(client, owner))["id"] for _ in range(5)]
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = await ok(await client.get("/v1/concierge/cases", params=params, headers=customer(owner)))
        seen += [c["id"] for c in page["data"]]
        if not page["page"]["has_more"]:
            break
        cursor = page["page"]["next_cursor"]
    assert seen == list(reversed(ids))


async def test_queue_filters_and_oldest_first(client: AsyncClient) -> None:
    coord = new_user()
    a = await create_case(client, new_user(), category="logistics")
    b = await create_case(client, new_user())
    c = await create_case(client, new_user())
    await claim(client, b["id"], coord)
    await move(client, c["id"], customer(c["customer_id"]), "cancelled")
    headers = coordinator(new_user())
    open_ids = [x["id"] for x in (await ok(await client.get("/v1/concierge/queue", headers=headers)))["data"]]
    assert open_ids == [a["id"], b["id"]]
    unassigned = await ok(await client.get("/v1/concierge/queue", params={"assignee": "unassigned"}, headers=headers))
    assert [x["id"] for x in unassigned["data"]] == [a["id"]]
    mine = await ok(await client.get("/v1/concierge/queue", params={"assignee": "me"}, headers=coordinator(coord)))
    assert [x["id"] for x in mine["data"]] == [b["id"]]
    logistics = await ok(await client.get("/v1/concierge/queue", params={"category": "logistics"}, headers=headers))
    assert [x["id"] for x in logistics["data"]] == [a["id"]]
    everything = await ok(await client.get("/v1/concierge/queue", params={"open_only": "false"}, headers=headers))
    assert len(everything["data"]) == 3
    cancelled = await ok(await client.get("/v1/concierge/queue", params={"status": "cancelled"}, headers=headers))
    assert [x["id"] for x in cancelled["data"]] == [c["id"]]


async def test_queue_pagination(client: AsyncClient) -> None:
    ids = [(await create_case(client, new_user()))["id"] for _ in range(3)]
    headers = coordinator(new_user())
    first = await ok(await client.get("/v1/concierge/queue", params={"limit": 2}, headers=headers))
    assert first["page"]["has_more"] is True
    second = await ok(await client.get("/v1/concierge/queue", params={"limit": 2, "cursor": first["page"]["next_cursor"]}, headers=headers))
    assert [x["id"] for x in first["data"] + second["data"]] == ids and second["page"]["has_more"] is False
    bad = await client.get("/v1/concierge/queue", params={"cursor": "not-a-cursor"}, headers=headers)
    assert bad.status_code == 422


async def test_sla_breach_is_computed_and_filterable(client: AsyncClient) -> None:
    late = await create_case(client, new_user())
    on_time = await create_case(client, new_user())
    await _overdue(late["id"])
    headers = coordinator(new_user())
    breached = await ok(await client.get("/v1/concierge/queue", params={"breached": "true"}, headers=headers))
    assert [x["id"] for x in breached["data"]] == [late["id"]] and breached["data"][0]["sla_breached"] is True
    fine = await ok(await client.get("/v1/concierge/queue", params={"breached": "false"}, headers=headers))
    assert [x["id"] for x in fine["data"]] == [on_time["id"]]
    # Responding late keeps the breach on record.
    responded = await move(client, late["id"], headers, "triaged")
    assert responded["first_responded_at"] is not None and responded["sla_breached"] is True


async def test_first_response_within_sla_is_not_breached(client: AsyncClient) -> None:
    case = await create_case(client, new_user())
    case = await claim(client, case["id"], new_user())
    assert case["first_responded_at"] is not None and case["sla_breached"] is False


async def test_audit_trail_records_every_transition(client: AsyncClient) -> None:
    owner, coord, boss = new_user(), new_user(), new_user()
    case = await create_case(client, owner)
    await move(client, case["id"], coordinator(coord), "triaged")
    await claim(client, case["id"], coord)
    await move(client, case["id"], coordinator(coord), "in_progress")
    await ok(await client.post(f"/v1/concierge/cases/{case['id']}/escalation", json={"reason": "dates impossible"}, headers=customer(owner)))
    await move(client, case["id"], supervisor(boss), "cancelled", reason="customer withdrew")
    audit = await ok(await client.get(f"/v1/concierge/cases/{case['id']}/audit", headers=supervisor(boss)))
    trail = [(e["action"], e["from_status"], e["to_status"], e["actor_role"]) for e in audit["data"]]
    assert trail == [
        ("submitted", None, "submitted", "customer"),
        ("status_changed", "submitted", "triaged", "coordinator"),
        ("assigned", "triaged", "triaged", "coordinator"),
        ("status_changed", "triaged", "assigned", "coordinator"),
        ("status_changed", "assigned", "in_progress", "coordinator"),
        ("status_changed", "in_progress", "escalated", "customer"),
        ("status_changed", "escalated", "cancelled", "supervisor"),
    ]
    last = audit["data"][-1]
    assert last["actor_id"] == boss and last["reason"] == "customer withdrew" and last["created_at"]
    assert audit["data"][5]["actor_id"] == owner and audit["data"][5]["reason"] == "dates impossible"
    page = await ok(await client.get(f"/v1/concierge/cases/{case['id']}/audit", params={"limit": 3}, headers=supervisor(boss)))
    assert len(page["data"]) == 3 and page["page"]["has_more"] is True
