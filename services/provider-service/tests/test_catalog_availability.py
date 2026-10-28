"""Service offerings, pricing transparency and availability rules."""

from __future__ import annotations

import asyncio
from datetime import date

from httpx import AsyncClient

from helpers import create_provider, new_user, ok, outbox_events, practice, staff, user, utc

CONSULT = {"category": "Consultation", "name": "Infectious diseases consultation", "duration_minutes": 30, "buffer_minutes": 10, "price_type": "fixed", "professional_fee_minor": 60000, "facility_fee_minor": 15000}


async def test_offering_requires_active_affiliation(client: AsyncClient) -> None:
    setup = await practice(client)
    other = await create_provider(client, new_user())
    response = await client.post(
        f"/v1/providers/{setup['provider']['id']}/services",
        json={**CONSULT, "branch_id": "01NOTABRANCH0000000000000"},
        headers=user(setup["owner"]),
    )
    assert response.status_code == 404
    unaffiliated = await client.post(
        f"/v1/providers/{other['id']}/services", json={**CONSULT, "branch_id": setup["branch"]["id"]}, headers=user(other["user_id"])
    )
    assert unaffiliated.status_code == 422


async def test_fee_breakdown_and_public_catalog(client: AsyncClient) -> None:
    setup = await practice(client)
    offering = await ok(
        await client.post(f"/v1/providers/{setup['provider']['id']}/services", json={**CONSULT, "branch_id": setup["branch"]["id"]}, headers=user(setup["owner"])),
        201,
    )
    assert offering["price"] == {"amount_minor": 75000, "currency": "AED"}
    assert offering["professional_fee"]["amount_minor"] == 60000
    assert offering["facility_fee"]["amount_minor"] == 15000
    assert offering["category"] == "consultation"

    catalog = await ok(await client.get("/v1/services", params={"category": "consultation"}))
    assert [o["id"] for o in catalog["data"]] == [offering["id"]]
    assert (await ok(await client.get(f"/v1/services/{offering['id']}")))["id"] == offering["id"]


async def test_on_request_and_currency_rules(client: AsyncClient) -> None:
    setup = await practice(client)
    url = f"/v1/providers/{setup['provider']['id']}/services"
    on_request = await ok(
        await client.post(url, json={"branch_id": setup["branch"]["id"], "category": "travel", "name": "Medical travel planning", "duration_minutes": 60, "price_type": "on_request"}, headers=user(setup["owner"])),
        201,
    )
    assert on_request["price"] is None
    bad_mix = {**CONSULT, "branch_id": setup["branch"]["id"], "price_type": "on_request"}
    assert (await client.post(url, json=bad_mix, headers=user(setup["owner"]))).status_code == 422
    usd = {**CONSULT, "branch_id": setup["branch"]["id"], "currency": "USD"}
    assert (await client.post(url, json=usd, headers=user(setup["owner"]))).status_code == 422


async def test_retired_offering_leaves_catalog(client: AsyncClient) -> None:
    setup = await practice(client)
    offering = await ok(
        await client.post(f"/v1/providers/{setup['provider']['id']}/services", json={**CONSULT, "branch_id": setup["branch"]["id"]}, headers=user(setup["admin"])),
        201,
    )
    await ok(await client.patch(f"/v1/services/{offering['id']}", json={"status": "retired"}, headers=user(setup["admin"])))
    assert (await ok(await client.get("/v1/services")))["data"] == []
    assert (await client.get(f"/v1/services/{offering['id']}")).status_code == 404


def _rule(branch_id: str, weekday: int = 0, start: str = "09:00", end: str = "12:00") -> dict:
    return {"branch_id": branch_id, "weekday": weekday, "start": start, "end": end, "effective_from": str(date.today())}


async def test_rules_must_fit_opening_hours_and_not_overlap(client: AsyncClient) -> None:
    setup = await practice(client)
    url = f"/v1/providers/{setup['provider']['id']}/availability-rules"
    headers = user(setup["owner"])
    created = await ok(await client.post(url, json=_rule(setup["branch"]["id"]), headers=headers), 201)
    assert created["timezone"] == "Asia/Dubai"
    assert (await client.post(url, json=_rule(setup["branch"]["id"], start="11:00", end="13:00"), headers=headers)).status_code == 409
    assert (await client.post(url, json=_rule(setup["branch"]["id"], start="17:00", end="19:00"), headers=headers)).status_code == 422
    assert (await client.post(url, json=_rule(setup["branch"]["id"], weekday=5), headers=headers)).status_code == 422  # closed Saturday
    rules = await ok(await client.get(url, headers=user(setup["admin"])))
    assert [r["id"] for r in rules["data"]] == [created["id"]]


async def test_concurrent_overlapping_rules_only_one_wins(client: AsyncClient) -> None:
    setup = await practice(client)
    url = f"/v1/providers/{setup['provider']['id']}/availability-rules"
    responses = await asyncio.gather(
        *(client.post(url, json=_rule(setup["branch"]["id"], start="09:00", end="10:30"), headers=user(setup["owner"])) for _ in range(5))
    )
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]


async def test_scheduler_can_manage_rules_but_strangers_cannot(client: AsyncClient) -> None:
    setup = await practice(client)
    scheduler = new_user()
    await ok(await client.post(f"/v1/facilities/{setup['facility']['id']}/staff", json={"user_id": scheduler, "role": "scheduler"}, headers=user(setup["admin"])), 201)
    url = f"/v1/providers/{setup['provider']['id']}/availability-rules"
    rule = await ok(await client.post(url, json=_rule(setup["branch"]["id"]), headers=user(scheduler)), 201)
    assert (await client.post(url, json=_rule(setup["branch"]["id"], weekday=1), headers=user(new_user()))).status_code == 403
    assert (await client.delete(f"/v1/availability-rules/{rule['id']}", headers=user(new_user()))).status_code == 404
    assert (await client.delete(f"/v1/availability-rules/{rule['id']}", headers=user(scheduler))).status_code == 204
    changes = [e["payload"]["change"] for e in await outbox_events("catalog.availability_changed")]
    assert changes == ["rule_added", "rule_removed"]


async def test_exceptions_validate_ranges(client: AsyncClient) -> None:
    setup = await practice(client)
    url = f"/v1/providers/{setup['provider']['id']}/availability-exceptions"
    headers = user(setup["owner"])
    leave = await ok(await client.post(url, json={"starts_at": utc(days=7), "ends_at": utc(days=9), "reason": "leave"}, headers=headers), 201)
    assert (await client.post(url, json={"starts_at": utc(days=9), "ends_at": utc(days=7), "reason": "leave"}, headers=headers)).status_code == 422
    naive = {"starts_at": "2026-12-01T09:00:00", "ends_at": "2026-12-01T10:00:00", "reason": "training"}
    assert (await client.post(url, json=naive, headers=headers)).status_code == 422
    listed = await ok(await client.get(url, headers=headers))
    assert [e["id"] for e in listed["data"]] == [leave["id"]]
    # Without a branch, only the provider or platform staff may block time.
    assert (await client.post(url, json={"starts_at": utc(days=1), "ends_at": utc(days=2), "reason": "other"}, headers=user(setup["admin"]))).status_code == 403
    assert (await client.post(url, json={"starts_at": utc(days=1), "ends_at": utc(days=2), "reason": "other"}, headers=staff())).status_code == 201
