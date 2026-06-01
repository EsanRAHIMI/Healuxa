"""Contract compliance tests for assessment.openapi.yaml."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_assessment_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/v1/assessments/01JAAAAAAAAAAAAAAAAAAAAAAAA")
    assert response.status_code == 401
