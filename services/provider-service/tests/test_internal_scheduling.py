"""Service-authenticated scheduling reads consumed by appointment-service."""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient

from helpers import new_user, ok, practice, user, utc
from provider_service.api.deps import principal_headers
from provider_service.config import settings

OFFERING = {
    "category": "consultation",
    "name": "Initial consultation",
    "duration_minutes": 30,
    "buffer_minutes": 10,
    "price_type": "fixed",
    "professional_fee_minor": 50000,
    "facility_fee_minor": 10000,
    "currency": "AED",
}


def service() -> dict[str, str]:
    return principal_headers("appointment-service", permissions="service")


async def _bookable_offering(client: AsyncClient) -> tuple[dict, dict]:
    setup = await practice(client)
    branch_id = setup["branch"]["id"]
    owner = user(setup["owner"])
    offering = await ok(
        await client.post(f"/v1/providers/{setup['provider']['id']}/services", json={**OFFERING, "branch_id": branch_id}, headers=owner),
        201,
    )
    await ok(
        await client.post(
            f"/v1/providers/{setup['provider']['id']}/availability-rules",
            json={"branch_id": branch_id, "weekday": 0, "start": "09:00", "end": "12:00", "effective_from": str(date.today())},
            headers=owner,
        ),
        201,
    )
    await ok(
        await client.post(
            f"/v1/providers/{setup['provider']['id']}/availability-exceptions",
            json={"starts_at": utc(days=3), "ends_at": utc(days=4), "reason": "leave"},
            headers=owner,
        ),
        201,
    )
    return setup, offering


def _window(days: int = 14) -> dict[str, str]:
    return {"tenant_id": settings.tenant_default, "from": utc(), "to": utc(days=days)}


async def test_scheduling_context_returns_raw_facts(client: AsyncClient) -> None:
    setup, offering = await _bookable_offering(client)
    body = await ok(await client.get(f"/v1/internal/scheduling/services/{offering['id']}", params=_window(), headers=service()))
    assert body["bookable"] is True and body["affiliation_active"] is True
    assert body["offering"]["duration_minutes"] == 30 and body["offering"]["buffer_minutes"] == 10
    assert body["provider"]["user_id"] == setup["owner"]
    assert body["branch"]["timezone"] == "Asia/Dubai"
    assert {(h["weekday"], h["start_minute"], h["end_minute"]) for h in body["operating_hours"]} == {(d, 540, 1080) for d in range(5)}
    assert [(r["weekday"], r["start_minute"], r["end_minute"]) for r in body["availability_rules"]] == [(0, 540, 720)]
    assert [e["reason"] for e in body["exceptions"]] == ["leave"]
    # Exceptions outside the requested window are not returned.
    outside = {"tenant_id": settings.tenant_default, "from": utc(days=10), "to": utc(days=20)}
    later = await ok(await client.get(f"/v1/internal/scheduling/services/{offering['id']}", params=outside, headers=service()))
    assert later["exceptions"] == []


async def test_scheduling_context_flags_unbookable_offering(client: AsyncClient) -> None:
    setup, offering = await _bookable_offering(client)
    await ok(await client.patch(f"/v1/services/{offering['id']}", json={"status": "retired"}, headers=user(setup["owner"])))
    body = await ok(await client.get(f"/v1/internal/scheduling/services/{offering['id']}", params=_window(), headers=service()))
    assert body["bookable"] is False and body["offering"]["status"] == "retired"


async def test_scheduling_endpoints_require_service_credentials(client: AsyncClient) -> None:
    _, offering = await _bookable_offering(client)
    url = f"/v1/internal/scheduling/services/{offering['id']}"
    assert (await client.get(url, params=_window())).status_code == 401
    assert (await client.get(url, params=_window(), headers=user(new_user()))).status_code == 403
    forged = {"X-Healuxa-User": "appointment-service", "X-Healuxa-Perms": "service"}
    assert (await client.get(url, params=_window(), headers=forged)).status_code == 401
    assert (await client.get(f"/v1/internal/scheduling/actors/{new_user()}", params={"tenant_id": settings.tenant_default}, headers=user(new_user()))).status_code == 403


async def test_scheduling_context_is_tenant_scoped_and_validates_window(client: AsyncClient) -> None:
    _, offering = await _bookable_offering(client)
    url = f"/v1/internal/scheduling/services/{offering['id']}"
    other = {**_window(), "tenant_id": "healuxa-europe"}
    assert (await client.get(url, params=other, headers=service())).status_code == 404
    too_long = {**_window(), "to": utc(days=90)}
    assert (await client.get(url, params=too_long, headers=service())).status_code == 422
    naive = {**_window(), "from": (date.today() + timedelta(days=1)).isoformat() + "T00:00:00"}
    assert (await client.get(url, params=naive, headers=service())).status_code == 422


async def test_scheduling_actor_lists_owned_providers_and_facility_roles(client: AsyncClient) -> None:
    setup = await practice(client)
    scheduler = new_user()
    await ok(
        await client.post(
            f"/v1/facilities/{setup['facility']['id']}/staff", json={"user_id": scheduler, "role": "scheduler"}, headers=user(setup["admin"])
        ),
        201,
    )
    params = {"tenant_id": settings.tenant_default}
    owner = await ok(await client.get(f"/v1/internal/scheduling/actors/{setup['owner']}", params=params, headers=service()))
    assert owner["provider_ids"] == [setup["provider"]["id"]] and owner["facility_roles"] == []
    staff = await ok(await client.get(f"/v1/internal/scheduling/actors/{scheduler}", params=params, headers=service()))
    assert staff["provider_ids"] == [] and staff["facility_roles"] == [{"facility_id": setup["facility"]["id"], "role": "scheduler"}]
    admin = await ok(await client.get(f"/v1/internal/scheduling/actors/{setup['admin']}", params=params, headers=service()))
    assert admin["facility_roles"] == [{"facility_id": setup["facility"]["id"], "role": "facility_admin"}]
    other_tenant = await ok(
        await client.get(f"/v1/internal/scheduling/actors/{setup['owner']}", params={"tenant_id": "healuxa-europe"}, headers=service())
    )
    assert other_tenant["provider_ids"] == []
