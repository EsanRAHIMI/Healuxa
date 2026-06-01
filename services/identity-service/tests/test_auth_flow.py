from ulid import ULID

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_jwks(client: AsyncClient) -> None:
    response = await client.get("/.well-known/jwks.json")
    assert response.status_code == 200
    body = response.json()
    assert "keys" in body
    assert len(body["keys"]) >= 1


@pytest.mark.asyncio
async def test_register_login_refresh_logout(
    client: AsyncClient,
    service_headers: dict,
) -> None:
    email = f"user-{ULID()}@example.com"
    register = await client.post(
        "/v1/auth/register",
        json={"identifier": email, "password": "password123", "locale": "en"},
    )
    assert register.status_code == 201, register.text
    tokens = register.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    login = await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    assert login.status_code == 200
    login_tokens = login.json()

    introspect = await client.post(
        "/v1/auth/introspect",
        json={"token": login_tokens["access_token"]},
        headers=service_headers,
    )
    assert introspect.status_code == 200
    intro = introspect.json()
    assert intro["active"] is True
    assert intro["sub"]

    refresh = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": login_tokens["refresh_token"]},
    )
    assert refresh.status_code == 200
    refreshed = refresh.json()
    assert refreshed["access_token"]

    sessions = await client.get(
        "/v1/sessions",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert sessions.status_code == 200
    assert "data" in sessions.json()

    logout = await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert logout.status_code == 204

    introspect_after = await client.post(
        "/v1/auth/introspect",
        json={"token": refreshed["access_token"]},
        headers=service_headers,
    )
    assert introspect_after.json()["active"] is False


@pytest.mark.asyncio
async def test_service_token(client: AsyncClient, service_headers: dict) -> None:
    response = await client.post("/v1/auth/service-token", headers=service_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "Bearer"
