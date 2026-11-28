"""Authentication, permission and ownership."""

from __future__ import annotations

from httpx import AsyncClient
from ulid import ULID

from ai_orchestrator.api.deps import principal_headers
from conftest import ask
from platform_stub import TOKEN


async def test_requires_authentication(client: AsyncClient) -> None:
    assert (await client.post("/v1/ai/sessions", json={})).status_code == 401


async def test_forged_identity_headers_are_rejected(client: AsyncClient, user_id: str) -> None:
    forged = {"X-Healuxa-User": user_id, "X-Healuxa-Perms": "ai:chat"}
    assert (await client.post("/v1/ai/sessions", json={}, headers=forged)).status_code == 401


async def test_requires_ai_chat_permission(client: AsyncClient, user_id: str) -> None:
    headers = principal_headers(user_id, permissions="journeys:read,concierge:request")
    response = await client.post("/v1/ai/sessions", json={}, headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_create_and_get_session(client: AsyncClient, auth_headers: dict) -> None:
    created = await client.post("/v1/ai/sessions", json={"locale": "ar"}, headers=auth_headers)
    assert created.status_code == 201
    body = created.json()
    assert body["locale"] == "ar" and body["turns"] == [] and body["assistant_available"] is True
    assert created.headers["location"] == f"/v1/ai/sessions/{body['id']}"
    fetched = await client.get(f"/v1/ai/sessions/{body['id']}", headers=auth_headers)
    assert fetched.status_code == 200 and fetched.json()["id"] == body["id"]


async def test_unsupported_locale_is_rejected(client: AsyncClient, auth_headers: dict) -> None:
    assert (await client.post("/v1/ai/sessions", json={"locale": "xx"}, headers=auth_headers)).status_code == 422


async def test_other_users_session_is_not_found(client: AsyncClient, session_id: str) -> None:
    other = {**principal_headers(str(ULID())), "Authorization": f"Bearer {TOKEN}"}
    assert (await client.get(f"/v1/ai/sessions/{session_id}", headers=other)).status_code == 404
    assert (await ask(client, session_id, other, "dental")).status_code == 404
    assert (await client.delete(f"/v1/ai/sessions/{session_id}", headers=other)).status_code == 404


async def test_other_tenant_cannot_read_session(client: AsyncClient, session_id: str, user_id: str) -> None:
    other_tenant = principal_headers(user_id, tenant_id="another-tenant")
    assert (await client.get(f"/v1/ai/sessions/{session_id}", headers=other_tenant)).status_code == 404


async def test_delete_own_session(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    await ask(client, session_id, auth_headers, "hello")
    assert (await client.delete(f"/v1/ai/sessions/{session_id}", headers=auth_headers)).status_code == 204
    assert (await client.get(f"/v1/ai/sessions/{session_id}", headers=auth_headers)).status_code == 404
