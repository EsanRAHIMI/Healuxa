"""Authentication, forged headers and tenant isolation."""

from __future__ import annotations

from httpx import AsyncClient

from helpers import create_provider, new_user, ok, practice, staff, user


async def test_forged_identity_headers_are_rejected(client: AsyncClient) -> None:
    forged = {"X-Healuxa-User": new_user(), "X-Healuxa-Perms": "providers:onboard,providers:verify"}
    response = await client.post("/v1/providers", json={"type": "doctor", "display_name": "Dr. X", "specialties": ["x"], "languages": ["en"]}, headers=forged)
    assert response.status_code == 401


async def test_missing_permission_is_forbidden(client: AsyncClient) -> None:
    from provider_service.api.deps import principal_headers

    no_perms = principal_headers(new_user(), permissions="")
    response = await client.post("/v1/providers", json={"type": "doctor", "display_name": "Dr. X", "specialties": ["x"], "languages": ["en"]}, headers=no_perms)
    assert response.status_code == 403


async def test_staff_of_another_tenant_cannot_touch_provider(client: AsyncClient) -> None:
    provider = await create_provider(client, new_user())
    other_tenant_staff = staff(tenant_id="healuxa-europe")
    response = await client.post(
        f"/v1/providers/{provider['id']}/status", json={"status": "suspended", "reason": "cross-tenant attempt"}, headers=other_tenant_staff
    )
    assert response.status_code == 404


async def test_directory_is_tenant_scoped(client: AsyncClient) -> None:
    setup = await practice(client)
    other_tenant_user = user(new_user(), tenant_id="healuxa-europe")
    listing = await ok(await client.get("/v1/providers", headers=other_tenant_user))
    assert listing["data"] == []
    assert (await client.get(f"/v1/providers/{setup['provider']['id']}", headers=other_tenant_user)).status_code == 404
