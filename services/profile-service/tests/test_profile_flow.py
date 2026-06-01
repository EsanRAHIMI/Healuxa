"""Happy-path profile API flow."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.mongo


@pytest.mark.asyncio
async def test_profile_upsert_get_with_etag(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    missing = await client.get(f"/v1/profiles/{user_id}", headers=auth_headers)
    assert missing.status_code == 404

    body = {
        "user_id": user_id,
        "lifecycle_stage": "onboarding",
        "vip_tier": "none",
        "scores": {},
        "consent": {"marketing_email": True},
    }
    create = await client.put(f"/v1/profiles/{user_id}", json=body, headers=auth_headers)
    assert create.status_code == 200, create.text
    assert create.headers.get("etag") == "v1"

    fetch = await client.get(f"/v1/profiles/{user_id}", headers=auth_headers)
    assert fetch.status_code == 200
    assert fetch.json()["lifecycle_stage"] == "onboarding"
    assert fetch.headers.get("etag") == "v1"

    update = await client.put(
        f"/v1/profiles/{user_id}",
        json={**body, "lifecycle_stage": "active"},
        headers={**auth_headers, "If-Match": "v1"},
    )
    assert update.status_code == 200
    assert update.headers.get("etag") == "v2"
