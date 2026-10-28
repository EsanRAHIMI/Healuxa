from __future__ import annotations

from httpx import AsyncClient


async def test_forged_identity_headers_are_rejected(client: AsyncClient, user_id: str) -> None:
    forged = {"X-Healuxa-User": user_id, "X-Healuxa-Perms": "journeys:create,journeys:read"}
    response = await client.post("/v1/journeys", json={"user_id": user_id, "primary_goals": ["x"]}, headers=forged)
    assert response.status_code == 401
