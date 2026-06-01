"""Contract compliance tests for identity.openapi.yaml (PR-1)."""

from __future__ import annotations

from ulid import ULID

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from identity_service.config import settings
from identity_service.infra.db import SessionLocal
from identity_service.infra.models import Role, UserRole


async def _register(client: AsyncClient, email: str | None = None) -> dict:
    email = email or f"user-{ULID()}@example.com"
    response = await client.post(
        "/v1/auth/register",
        json={"identifier": email, "password": "password123", "locale": "en"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _user_id(client: AsyncClient, tokens: dict, service_headers: dict) -> str:
    intro = await client.post(
        "/v1/auth/introspect",
        json={"token": tokens["access_token"]},
        headers=service_headers,
    )
    assert intro.status_code == 200
    return intro.json()["sub"]


async def _clear_roles(user_id: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        await db.commit()


async def _assign_role(user_id: str, *, role_name: str | None = None, permissions: list[str] | None = None) -> None:
    async with SessionLocal() as db:
        if role_name:
            role = await db.scalar(
                select(Role).where(Role.tenant_id == settings.tenant_default, Role.name == role_name)
            )
            assert role is not None
        else:
            role = Role(
                id=str(ULID()),
                name=f"custom-{ULID()}",
                tenant_id=settings.tenant_default,
                permissions=permissions or [],
            )
            db.add(role)
            await db.flush()
        db.add(UserRole(user_id=user_id, role_id=role.id))
        await db.commit()


@pytest.mark.asyncio
async def test_login_with_mfa_code_returns_422(client: AsyncClient) -> None:
    email = f"mfa-{ULID()}@example.com"
    await _register(client, email)
    response = await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123", "mfa_code": "123456"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "unprocessable"
    assert "MFA" in body["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_returns_409(client: AsyncClient) -> None:
    email = f"dup-{ULID()}@example.com"
    first = await client.post(
        "/v1/auth/register",
        json={"identifier": email, "password": "password123"},
    )
    assert first.status_code == 201
    second = await client.post(
        "/v1/auth/register",
        json={"identifier": email, "password": "password123"},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "conflict"


@pytest.mark.asyncio
async def test_register_location_points_to_sessions_path(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"identifier": f"loc-{ULID()}@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    location = response.headers["location"]
    assert location.startswith("/v1/sessions/")
    assert "/v1/users/" not in location


@pytest.mark.asyncio
async def test_register_idempotency_replay(client: AsyncClient) -> None:
    email = f"idem-{ULID()}@example.com"
    headers = {"Idempotency-Key": "idem-key-replay-01"}
    payload = {"identifier": email, "password": "password123"}
    first = await client.post("/v1/auth/register", json=payload, headers=headers)
    second = await client.post("/v1/auth/register", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert first.headers["location"] == second.headers["location"]


@pytest.mark.asyncio
async def test_register_idempotency_conflict(client: AsyncClient) -> None:
    headers = {"Idempotency-Key": "idem-key-conflict-01"}
    first = await client.post(
        "/v1/auth/register",
        json={"identifier": f"a-{ULID()}@example.com", "password": "password123"},
        headers=headers,
    )
    assert first.status_code == 201
    second = await client.post(
        "/v1/auth/register",
        json={"identifier": f"b-{ULID()}@example.com", "password": "password123"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_register_idempotency_key_length_validation(client: AsyncClient) -> None:
    short = await client.post(
        "/v1/auth/register",
        json={"identifier": f"short-{ULID()}@example.com", "password": "password123"},
        headers={"Idempotency-Key": "short"},
    )
    assert short.status_code == 422
    assert short.json()["code"] == "validation_error"


@pytest.mark.asyncio
async def test_list_sessions_cursor_pagination(client: AsyncClient) -> None:
    email = f"page-{ULID()}@example.com"
    tokens = await _register(client, email)
    for _ in range(2):
        login = await client.post(
            "/v1/auth/login",
            json={"identifier": email, "password": "password123"},
        )
        assert login.status_code == 200

    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    first = await client.get("/v1/sessions", params={"limit": 2}, headers=auth)
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["data"]) == 2
    assert first_body["page"]["has_more"] is True
    assert first_body["page"]["next_cursor"]

    second = await client.get(
        "/v1/sessions",
        params={"limit": 2, "cursor": first_body["page"]["next_cursor"]},
        headers=auth,
    )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["data"]) >= 1
    first_ids = {item["id"] for item in first_body["data"]}
    second_ids = {item["id"] for item in second_body["data"]}
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
async def test_delete_session_success(client: AsyncClient, service_headers: dict) -> None:
    email = f"del-{ULID()}@example.com"
    tokens = await _register(client, email)
    await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )

    sessions = await client.get(
        "/v1/sessions",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    intro = await client.post(
        "/v1/auth/introspect",
        json={"token": tokens["access_token"]},
        headers=service_headers,
    )
    current_session = intro.json()["session_id"]
    target_id = next(item["id"] for item in sessions.json()["data"] if item["id"] != current_session)

    delete = await client.delete(
        f"/v1/sessions/{target_id}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_delete_session_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)
    delete = await client.delete(
        "/v1/sessions/01JNONEXISTENT000000000",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert delete.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_forbidden(client: AsyncClient, service_headers: dict) -> None:
    email = f"forbid-del-{ULID()}@example.com"
    tokens = await _register(client, email)
    user_id = await _user_id(client, tokens, service_headers)
    await _clear_roles(user_id)
    await _assign_role(user_id, permissions=[])

    login = await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    login_tokens = login.json()

    sessions = await client.get(
        "/v1/sessions",
        headers={"Authorization": f"Bearer {login_tokens['access_token']}"},
    )
    session_id = sessions.json()["data"][0]["id"]

    delete = await client.delete(
        f"/v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {login_tokens['access_token']}"},
    )
    assert delete.status_code == 403
    assert delete.json()["code"] == "forbidden"


@pytest.mark.asyncio
async def test_iam_list_roles_success(client: AsyncClient, service_headers: dict) -> None:
    email = f"iam-admin-{ULID()}@example.com"
    tokens = await _register(client, email)
    user_id = await _user_id(client, tokens, service_headers)
    await _assign_role(user_id, role_name="admin")

    login = await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    admin_tokens = login.json()

    response = await client.get(
        "/v1/iam/roles",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert any(role["name"] == "admin" for role in response.json())


@pytest.mark.asyncio
async def test_iam_list_roles_forbidden(client: AsyncClient) -> None:
    tokens = await _register(client)
    response = await client.get(
        "/v1/iam/roles",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


@pytest.mark.asyncio
async def test_iam_create_role_success(client: AsyncClient, service_headers: dict) -> None:
    email = f"iam-create-{ULID()}@example.com"
    tokens = await _register(client, email)
    user_id = await _user_id(client, tokens, service_headers)
    await _assign_role(user_id, role_name="admin")

    login = await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    admin_tokens = login.json()

    role_name = f"ops-{ULID()}"
    response = await client.post(
        "/v1/iam/roles",
        json={"name": role_name, "permissions": ["sessions:revoke"]},
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == role_name


@pytest.mark.asyncio
async def test_iam_create_role_forbidden(client: AsyncClient) -> None:
    tokens = await _register(client)
    response = await client.post(
        "/v1/iam/roles",
        json={"name": f"blocked-{ULID()}", "permissions": ["iam:read"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_iam_create_role_idempotency_replay(client: AsyncClient, service_headers: dict) -> None:
    email = f"iam-idem-{ULID()}@example.com"
    tokens = await _register(client, email)
    user_id = await _user_id(client, tokens, service_headers)
    await _assign_role(user_id, role_name="admin")
    login = await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    admin_tokens = login.json()

    role_name = f"idem-role-{ULID()}"
    headers = {
        "Authorization": f"Bearer {admin_tokens['access_token']}",
        "Idempotency-Key": "iam-idem-replay-01",
    }
    payload = {"name": role_name, "permissions": ["sessions:revoke"]}
    first = await client.post("/v1/iam/roles", json=payload, headers=headers)
    second = await client.post("/v1/iam/roles", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()


@pytest.mark.asyncio
async def test_iam_create_role_idempotency_conflict(client: AsyncClient, service_headers: dict) -> None:
    email = f"iam-conflict-{ULID()}@example.com"
    tokens = await _register(client, email)
    user_id = await _user_id(client, tokens, service_headers)
    await _assign_role(user_id, role_name="admin")
    login = await client.post(
        "/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    admin_tokens = login.json()

    headers = {
        "Authorization": f"Bearer {admin_tokens['access_token']}",
        "Idempotency-Key": "iam-idem-conflict-01",
    }
    first = await client.post(
        "/v1/iam/roles",
        json={"name": f"role-a-{ULID()}", "permissions": ["sessions:revoke"]},
        headers=headers,
    )
    assert first.status_code == 201
    second = await client.post(
        "/v1/iam/roles",
        json={"name": f"role-b-{ULID()}", "permissions": ["sessions:revoke"]},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "idempotency_conflict"
