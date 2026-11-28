from __future__ import annotations

import os

# Simulated edge secret so principal_headers() is trusted; forged headers without it are not.
os.environ.setdefault("HEALUXA_EDGE_SECRET", "test-edge-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/ai_e2e_test")
os.environ["LLM_PROVIDER"] = "fake"
os.environ.pop("ANTHROPIC_API_KEY", None)
# Tools resolve against the in-process platform stub (same paths as the real services).
for name in ("PROVIDER", "APPOINTMENT", "TRANSFORMATION", "CONCIERGE"):
    os.environ[f"{name}_API_URL"] = "http://platform.test/v1"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from ulid import ULID

from ai_orchestrator.api import sessions as sessions_api
from ai_orchestrator.api.deps import principal_headers
from ai_orchestrator.config import settings
from ai_orchestrator.infra.db import SessionLocal, engine
from ai_orchestrator.llm import set_llm
from ai_orchestrator.llm.fake import FakeProvider
from ai_orchestrator.main import app, lifespan
from platform_stub import TOKEN, PlatformStub


@pytest.fixture(autouse=True)
async def _reset_tables() -> None:
    try:
        async with SessionLocal() as db:
            await db.execute(text("TRUNCATE TABLE ai_turns, ai_sessions RESTART IDENTITY CASCADE"))
            await db.commit()
    except Exception as exc:
        pytest.skip(f"ai_e2e_test database not ready (run alembic upgrade head): {exc}")


@pytest.fixture(autouse=True)
def _default_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_per_minute", 100)
    monkeypatch.setattr(settings, "rate_limit_per_day", 1000)


@pytest.fixture
def user_id() -> str:
    return str(ULID())


@pytest.fixture
def platform(user_id: str):
    stub = PlatformStub(user_id=user_id)
    sessions_api.platform_transport = stub.transport()
    yield stub
    sessions_api.platform_transport = None


@pytest.fixture
def llm():
    provider = FakeProvider()
    set_llm(provider)
    yield provider
    set_llm(None)


@pytest.fixture
async def client(platform: PlatformStub, llm: FakeProvider):
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
            yield async_client
    await engine.dispose()


@pytest.fixture
def auth_headers(user_id: str) -> dict[str, str]:
    # Edge-asserted identity plus the caller's own bearer, which tools forward to platform services.
    return {**principal_headers(user_id), "Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
async def session_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    response = await client.post("/v1/ai/sessions", json={"locale": "en"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def ask(client: AsyncClient, session_id: str, headers: dict[str, str], content: str, **extra_headers: str):
    return await client.post(f"/v1/ai/sessions/{session_id}/messages", json={"content": content}, headers={**headers, **extra_headers})
