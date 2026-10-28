"""profile.updated is staged atomically with the profile write it describes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from profile_service.infra.mongo import get_database

pytestmark = pytest.mark.mongo


async def _events(user_id: str) -> list[dict]:
    return await get_database()["outbox_events"].find({"body.payload.user_id": user_id}).to_list()


async def test_upserts_stage_one_event_each(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    body = {"user_id": user_id, "scores": {}, "consent": {}}
    first = await client.put(f"/v1/profiles/{user_id}", json=body, headers=auth_headers)
    assert first.status_code == 200, first.text
    second = await client.put(
        f"/v1/profiles/{user_id}", json=body, headers={**auth_headers, "If-Match": first.headers["ETag"]}
    )
    assert second.status_code == 200, second.text

    events = await _events(user_id)
    assert len(events) == 2
    assert {e["subject"] for e in events} == {"healuxa.profile.updated.v1"}


async def test_conflicting_write_stages_no_event(client: AsyncClient, user_id: str, auth_headers: dict) -> None:
    body = {"user_id": user_id, "scores": {}, "consent": {}}
    assert (await client.put(f"/v1/profiles/{user_id}", json=body, headers=auth_headers)).status_code == 200
    conflict = await client.put(f"/v1/profiles/{user_id}", json=body, headers={**auth_headers, "If-Match": "v99"})
    assert conflict.status_code == 409
    assert len(await _events(user_id)) == 1
