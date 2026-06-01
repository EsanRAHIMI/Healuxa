"""Happy-path and authorization tests for assessment.openapi.yaml."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from ulid import ULID

from assessment_service.api.deps import principal_headers

pytestmark = pytest.mark.mongo


@pytest.mark.asyncio
async def test_start_get_submit_assessment(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    start = await client.post(
        "/v1/assessments",
        json={"user_id": user_id, "kind": "beauty"},
        headers=auth_headers,
    )
    assert start.status_code == 201, start.text
    assessment_id = start.json()["id"]
    assert start.json()["status"] == "in_progress"
    assert start.json()["user_id"] == user_id

    fetch = await client.get(f"/v1/assessments/{assessment_id}", headers=auth_headers)
    assert fetch.status_code == 200
    assert fetch.json()["id"] == assessment_id

    submit = await client.post(
        f"/v1/assessments/{assessment_id}/submit",
        json={"responses": [{"q1": "answer"}]},
        headers=auth_headers,
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["status"] == "completed"
    assert body["recommended_goals"] == []
    assert body["scores"] == {}


@pytest.mark.asyncio
async def test_submit_twice_returns_409(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    start = await client.post(
        "/v1/assessments",
        json={"user_id": user_id, "kind": "wellness"},
        headers=auth_headers,
    )
    assert start.status_code == 201
    assessment_id = start.json()["id"]

    first = await client.post(
        f"/v1/assessments/{assessment_id}/submit",
        json={"responses": []},
        headers=auth_headers,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/v1/assessments/{assessment_id}/submit",
        json={"responses": [{"q1": "again"}]},
        headers=auth_headers,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "conflict"


@pytest.mark.asyncio
async def test_missing_assessment_returns_404(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    missing_id = str(ULID())
    response = await client.get(f"/v1/assessments/{missing_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_other_user_cannot_read_or_submit(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    start = await client.post(
        "/v1/assessments",
        json={"user_id": user_id, "kind": "intake"},
        headers=auth_headers,
    )
    assert start.status_code == 201
    assessment_id = start.json()["id"]

    other_headers = principal_headers(str(ULID()))
    forbidden_get = await client.get(f"/v1/assessments/{assessment_id}", headers=other_headers)
    assert forbidden_get.status_code == 403

    forbidden_submit = await client.post(
        f"/v1/assessments/{assessment_id}/submit",
        json={"responses": []},
        headers=other_headers,
    )
    assert forbidden_submit.status_code == 403


@pytest.mark.asyncio
async def test_start_for_other_user_forbidden(
    client: AsyncClient,
    user_id: str,
    auth_headers: dict,
) -> None:
    other = str(ULID())
    response = await client.post(
        "/v1/assessments",
        json={"user_id": other, "kind": "beauty"},
        headers=auth_headers,
    )
    assert response.status_code == 403
