"""Contract compliance tests for profile.openapi.yaml."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from ulid import ULID

from profile_service.api.deps import principal_headers

pytestmark = pytest.mark.mongo


@pytest.mark.asyncio
async def test_get_profile_requires_auth(client: AsyncClient, user_id: str) -> None:
    response = await client.get(f"/v1/profiles/{user_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_forbidden_other_user(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    other = str(ULID())
    response = await client.get(f"/v1/profiles/{other}", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_put_profile_forbidden_other_user(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    other = str(ULID())
    response = await client.put(
        f"/v1/profiles/{other}",
        json={"user_id": other, "scores": {}, "consent": {}},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_if_match_conflict(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    body = {"user_id": user_id, "scores": {}, "consent": {}}
    first = await client.put(f"/v1/profiles/{user_id}", json=body, headers=auth_headers)
    assert first.status_code == 200

    conflict = await client.put(
        f"/v1/profiles/{user_id}",
        json=body,
        headers={**auth_headers, "If-Match": "v99"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "conflict"


@pytest.mark.asyncio
async def test_if_match_on_missing_profile(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    response = await client.put(
        f"/v1/profiles/{user_id}",
        json={"user_id": user_id, "scores": {}, "consent": {}},
        headers={**auth_headers, "If-Match": "v1"},
    )
    assert response.status_code == 409
