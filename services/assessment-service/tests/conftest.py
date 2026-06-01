from __future__ import annotations

import os

os.environ.setdefault("MONGODB_DATABASE", "healuxa_assessment_test")

import pytest
from httpx import ASGITransport, AsyncClient
from ulid import ULID

from assessment_service.api.deps import principal_headers
from assessment_service.config import settings
from assessment_service.infra.mongo import close_client, ensure_indexes, get_database
from assessment_service.main import app, lifespan

ASSESSMENTS_COLLECTION = "assessments"
IDEMPOTENCY_COLLECTION = "idempotency_records"


def _assert_safe_test_database() -> None:
    database = settings.mongodb_database
    if "test" not in database.lower():
        pytest.fail(
            f"Refusing to run destructive MongoDB tests: MONGODB_DATABASE={database!r} "
            "must contain 'test' (e.g. healuxa_assessment_test)."
        )


@pytest.fixture(autouse=True)
async def _mongo_test_setup(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("mongo") is None:
        return
    if not os.environ.get("MONGODB_URI"):
        pytest.skip(
            "MONGODB_URI not set — assessment-service Mongo tests skipped "
            "(configure Atlas test URI locally or MONGODB_URI_TEST in CI)."
        )
    _assert_safe_test_database()
    await ensure_indexes()
    db = get_database()
    await db[ASSESSMENTS_COLLECTION].delete_many({})
    await db[IDEMPOTENCY_COLLECTION].delete_many({})


@pytest.fixture
async def client():
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    await close_client()


@pytest.fixture
def user_id() -> str:
    return str(ULID())


@pytest.fixture
def auth_headers(user_id: str) -> dict[str, str]:
    return principal_headers(user_id)
