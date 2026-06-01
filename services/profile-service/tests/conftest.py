from __future__ import annotations

import os

# Tests must target an isolated Atlas database name (never production).
os.environ.setdefault("MONGODB_DATABASE", "healuxa_profile_test")

import pytest
from httpx import ASGITransport, AsyncClient
from ulid import ULID

from profile_service.api.deps import principal_headers
from profile_service.config import settings
from profile_service.infra.mongo import close_client, ensure_indexes, get_database
from profile_service.main import app, lifespan

COLLECTION_NAME = "customer_profiles"


def _assert_safe_test_database() -> None:
    database = settings.mongodb_database
    if "test" not in database.lower():
        pytest.fail(
            f"Refusing to run destructive MongoDB tests: MONGODB_DATABASE={database!r} "
            "must contain 'test' (e.g. healuxa_profile_test)."
        )


@pytest.fixture(scope="session", autouse=True)
def mongo_tests_gate() -> None:
    if not os.environ.get("MONGODB_URI"):
        pytest.skip(
            "MONGODB_URI not set — profile-service Mongo tests skipped "
            "(configure Atlas test URI locally or MONGODB_URI_TEST in CI)."
        )
    _assert_safe_test_database()


@pytest.fixture(autouse=True)
async def _reset_customer_profiles() -> None:
    _assert_safe_test_database()
    await ensure_indexes()
    await get_database()[COLLECTION_NAME].delete_many({})


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
