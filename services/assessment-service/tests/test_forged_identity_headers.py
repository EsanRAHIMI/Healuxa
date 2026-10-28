from __future__ import annotations

import pytest
from httpx import AsyncClient
from ulid import ULID

pytestmark = pytest.mark.mongo


async def test_forged_identity_headers_are_rejected(client: AsyncClient) -> None:
    user_id = str(ULID())
    forged = {"X-Healuxa-User": user_id, "X-Healuxa-Perms": "assessments:create,assessments:read"}
    response = await client.post("/v1/assessments", json={"user_id": user_id, "kind": "beauty"}, headers=forged)
    assert response.status_code == 401
