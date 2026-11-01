"""Content Rights: profiles are published only under the owner's accepted content licence."""

from __future__ import annotations

from httpx import AsyncClient

from helpers import FACILITY_BODY, PROVIDER_BODY, new_user, ok, practice, user


async def test_create_requires_content_license(client: AsyncClient) -> None:
    body = {k: v for k, v in PROVIDER_BODY.items() if k != "accept_content_license"}
    assert (await client.post("/v1/providers", json=body, headers=user(new_user()))).status_code == 422
    rejected = {**PROVIDER_BODY, "accept_content_license": False}
    assert (await client.post("/v1/providers", json=rejected, headers=user(new_user()))).status_code == 422
    fac = {k: v for k, v in FACILITY_BODY.items() if k != "accept_content_license"}
    assert (await client.post("/v1/facilities", json=fac, headers=user(new_user()))).status_code == 422


async def test_acceptance_is_recorded_privately(client: AsyncClient) -> None:
    owner = new_user()
    provider = await ok(await client.post("/v1/providers", json=PROVIDER_BODY, headers=user(owner)), 201)
    assert provider["content_license_version"] and provider["content_license_accepted_at"]


async def test_public_views_never_expose_license_metadata(client: AsyncClient) -> None:
    setup = await practice(client)
    public = await ok(await client.get(f"/v1/providers/{setup['provider']['id']}"))
    assert public["content_license_version"] is None and public["content_license_accepted_at"] is None


async def test_unlicensed_profiles_are_not_published(client: AsyncClient) -> None:
    from sqlalchemy import update

    from provider_service.infra.db import SessionLocal
    from provider_service.infra.models import Provider

    setup = await practice(client)
    pid = setup["provider"]["id"]
    assert (await client.get(f"/v1/providers/{pid}")).status_code == 200
    async with SessionLocal() as db:  # e.g. a profile created before the licence existed
        await db.execute(update(Provider).where(Provider.id == pid).values(content_license_accepted_at=None))
        await db.commit()
    assert (await client.get(f"/v1/providers/{pid}")).status_code == 404
    assert (await ok(await client.get("/v1/providers")))["data"] == []
    # The owner re-accepts and the profile is public again.
    await ok(await client.patch(f"/v1/providers/{pid}", json={"accept_content_license": True}, headers=user(setup["owner"])))
    assert (await client.get(f"/v1/providers/{pid}")).status_code == 200
