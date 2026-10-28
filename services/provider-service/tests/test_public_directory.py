"""Anonymous directory reads expose only verified, active data and no private fields."""

from __future__ import annotations

from httpx import AsyncClient

from helpers import create_provider, new_user, ok, practice, user


async def test_unverified_provider_is_hidden(client: AsyncClient) -> None:
    provider = await create_provider(client, new_user())
    assert (await client.get(f"/v1/providers/{provider['id']}")).status_code == 404
    listing = await ok(await client.get("/v1/providers"))
    assert listing["data"] == []


async def test_active_provider_public_view_has_no_private_fields(client: AsyncClient) -> None:
    setup = await practice(client)
    public = await ok(await client.get(f"/v1/providers/{setup['provider']['id']}"))
    assert public["user_id"] is None
    assert public["verified_credentials"][0]["issuing_authority"] == "DHA"
    assert "number" not in public["verified_credentials"][0]

    facility = await ok(await client.get(f"/v1/facilities/{setup['facility']['id']}"))
    assert facility["license_number"] is None


async def test_search_filters(client: AsyncClient) -> None:
    setup = await practice(client)
    pid = setup["provider"]["id"]
    by_specialty = await ok(await client.get("/v1/providers", params={"specialty": "Infectious Diseases"}))
    assert [p["id"] for p in by_specialty["data"]] == [pid]
    assert (await ok(await client.get("/v1/providers", params={"specialty": "cardiology"})))["data"] == []
    assert [p["id"] for p in (await ok(await client.get("/v1/providers", params={"language": "fa"})))["data"]] == [pid]
    assert [p["id"] for p in (await ok(await client.get("/v1/providers", params={"city": "dubai"})))["data"]] == [pid]
    near = await ok(await client.get("/v1/providers", params={"near": "25.21,55.27", "radius_km": 5}))
    assert [p["id"] for p in near["data"]] == [pid]
    far = await ok(await client.get("/v1/providers", params={"near": "24.45,54.37", "radius_km": 5}))  # Abu Dhabi
    assert far["data"] == []


async def test_pagination_walks_all_results(client: AsyncClient) -> None:
    ids = {(await practice(client))["provider"]["id"] for _ in range(3)}
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = await ok(await client.get("/v1/providers", params=params))
        seen += [p["id"] for p in page["data"]]
        if not page["page"]["has_more"]:
            break
        cursor = page["page"]["next_cursor"]
    assert set(seen) == ids and len(seen) == 3


async def test_suspended_provider_leaves_directory_and_catalog(client: AsyncClient) -> None:
    from helpers import staff

    setup = await practice(client)
    pid = setup["provider"]["id"]
    await ok(
        await client.post(
            f"/v1/providers/{pid}/services",
            json={"branch_id": setup["branch"]["id"], "category": "consultation", "name": "Consultation", "duration_minutes": 30, "price_type": "fixed", "professional_fee_minor": 50000},
            headers=user(setup["owner"]),
        ),
        201,
    )
    assert len((await ok(await client.get("/v1/services")))["data"]) == 1
    await ok(await client.post(f"/v1/providers/{pid}/status", json={"status": "suspended", "reason": "license audit"}, headers=staff()))
    assert (await client.get(f"/v1/providers/{pid}")).status_code == 404
    assert (await ok(await client.get("/v1/services")))["data"] == []


async def test_invalid_token_on_public_endpoint_is_rejected(client: AsyncClient) -> None:
    # A presented bearer token must be valid even on public endpoints (no silent downgrade).
    response = await client.get("/v1/providers", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code in (401, 503)
