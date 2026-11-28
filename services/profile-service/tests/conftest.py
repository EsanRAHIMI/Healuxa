from __future__ import annotations

import os

# Simulated edge secret so principal_headers() is trusted; forged headers without it are not.
os.environ.setdefault("HEALUXA_EDGE_SECRET", "test-edge-secret")

# Tests must target an isolated Atlas database name (never production).
os.environ.setdefault("MONGODB_DATABASE", "healuxa_profile_test")

# Records tests: a throwaway AES-256 key (base64 of 32 bytes); production keys come from the secret store.
os.environ.setdefault("RECORDS_ENCRYPTION_KEY", "dGVzdC1vbmx5LXJlY29yZHMta2V5LTMyLWJ5dGVzISE=")
os.environ.setdefault("RECORDS_KEY_ID", "t1")

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
async def _reset_customer_profiles():
    _assert_safe_test_database()
    try:
        await ensure_indexes()
        await get_database()[COLLECTION_NAME].delete_many({})
        await get_database()["outbox_events"].delete_many({})
        for name in (
            "medical_records",
            "record_grants",
            "record_access_log",
            "record_blob_gc",
            "record_idempotency",
            "record_files.files",
            "record_files.chunks",
        ):
            await get_database()[name].delete_many({})
        yield
    finally:
        # Each test runs on its own event loop; never leak a loop-bound client.
        await close_client()


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


@pytest.fixture
def directory():
    """Fake provider-service for records authorisation; real-HTTP behaviour is tested separately."""
    from records_helpers import FakeDirectory

    from profile_service.api.records import get_directory

    fake = FakeDirectory()
    app.dependency_overrides[get_directory] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_directory, None)
