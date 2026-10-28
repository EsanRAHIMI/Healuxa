from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.mongo


async def test_forged_identity_headers_are_rejected(client: AsyncClient, user_id: str) -> None:
    forged = {"X-Healuxa-User": user_id, "X-Healuxa-Perms": "profiles:read,profiles:write"}
    response = await client.get(f"/v1/profiles/{user_id}", headers=forged)
    assert response.status_code == 401
