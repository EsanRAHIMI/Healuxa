"""Service tokens must introspect as active so service-to-service calls are authorised."""

from __future__ import annotations

from httpx import AsyncClient

from identity_service.config import settings


async def test_service_token_introspects_active(client: AsyncClient, service_headers: dict) -> None:
    issued = await client.post("/v1/auth/service-token", headers=service_headers)
    assert issued.status_code == 200, issued.text
    result = await client.post("/v1/auth/introspect", json={"token": issued.json()["access_token"]}, headers=service_headers)
    body = result.json()
    assert body["active"] is True
    assert body["sub"] == settings.service_auth_client_id
    assert "service" in body["perms"]


async def test_user_tokens_still_require_a_live_session(client: AsyncClient, service_headers: dict) -> None:
    tokens = (await client.post("/v1/auth/register", json={"identifier": "svc-check@example.com", "password": "password123", "locale": "en"})).json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.post("/v1/auth/logout", headers=auth)).status_code == 204
    result = await client.post("/v1/auth/introspect", json={"token": tokens["access_token"]}, headers=service_headers)
    assert result.json()["active"] is False


async def test_mesh_endpoints_require_explicit_credentials(client: AsyncClient) -> None:
    # No fallback to configured defaults: unauthenticated callers can neither mint nor introspect.
    assert (await client.post("/v1/auth/service-token")).status_code == 401
    assert (await client.post("/v1/auth/introspect", json={"token": "x"})).status_code == 401
    wrong = {"X-Service-Client-Id": settings.service_auth_client_id, "X-Service-Client-Secret": "wrong"}
    assert (await client.post("/v1/auth/service-token", headers=wrong)).status_code == 401
