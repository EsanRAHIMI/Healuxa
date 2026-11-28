"""Streaming, degradation without a model, rate limiting, idempotency, history, erasure, migrations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from ai_orchestrator.config import settings
from ai_orchestrator.consumers.user_deleted import handle_user_deleted
from ai_orchestrator.infra.db import SessionLocal
from ai_orchestrator.infra.models import AiSession, AiTurn
from ai_orchestrator.llm import set_llm
from ai_orchestrator.llm.base import LLMError
from ai_orchestrator.llm.fake import FakeProvider
from conftest import ask
from platform_stub import SERVICE_DENTAL

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    events = []
    for block in raw.strip().split("\n\n"):
        name = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            events.append((name, data))
    return events


async def test_streaming_response(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    async with client.stream(
        "POST", f"/v1/ai/sessions/{session_id}/messages", json={"content": "I need dental care"}, headers={**auth_headers, "Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store"
        raw = "".join([chunk async for chunk in response.aiter_text()])
    events = parse_sse(raw)
    names = [n for n, _ in events]
    assert names[0] == "turn" and names[-1] == "done"
    assert "delta" in names and "status" in names
    assert {"tool": "search_services"} in [d for n, d in events if n == "status"]
    done = events[-1][1]["turn"]
    assert done["role"] == "assistant" and any(c["id"] == SERVICE_DENTAL for c in done["cards"])
    streamed = "".join(d["text"] for n, d in events if n == "delta")
    assert "check" in streamed.lower()


async def test_session_history_persists_turns(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    await ask(client, session_id, auth_headers, "dental")
    await ask(client, session_id, auth_headers, "find me a doctor")
    session = (await client.get(f"/v1/ai/sessions/{session_id}", headers=auth_headers)).json()
    assert [t["role"] for t in session["turns"]] == ["user", "assistant", "user", "assistant"]
    assert session["turns"][0]["content"] == "dental" and session["turns"][1]["cards"]
    assert session["turn_count"] == 4


async def test_no_api_key_degrades_to_503_without_storing_the_message(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    set_llm(FakeProvider(available=False))
    created = await client.post("/v1/ai/sessions", json={}, headers=auth_headers)
    assert created.status_code == 201 and created.json()["assistant_available"] is False
    response = await ask(client, session_id, auth_headers, "dental")
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable" and "dental" not in response.text
    # Safety guardrails still answer without a model.
    emergency = await ask(client, session_id, auth_headers, "chest pain, can't breathe")
    assert emergency.status_code == 200 and emergency.json()["guardrail"] == "emergency"
    async with SessionLocal() as db:
        contents = (await db.scalars(select(AiTurn.content).where(AiTurn.session_id == session_id))).all()
    assert "dental" not in contents
    ready = await client.get("/ready")
    assert ready.json() == {"status": "ready", "assistant": "unavailable"}


async def test_real_provider_without_key_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_orchestrator.llm.anthropic_provider import AnthropicProvider

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    provider = AnthropicProvider()
    assert provider.available is False and provider.model == "claude-opus-5-5"


async def test_provider_error_midway_streams_error_and_drops_the_question(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    class Broken(FakeProvider):
        async def stream_step(self, **kwargs):
            raise LLMError("unavailable")
            yield  # pragma: no cover

    set_llm(Broken())
    async with client.stream("POST", f"/v1/ai/sessions/{session_id}/messages", json={"content": "dental"}, headers={**auth_headers, "Accept": "text/event-stream"}) as response:
        raw = "".join([c async for c in response.aiter_text()])
    assert parse_sse(raw)[-1] == ("error", {"code": "service_unavailable"})
    non_stream = await ask(client, session_id, auth_headers, "dental")
    assert non_stream.status_code == 503
    session = (await client.get(f"/v1/ai/sessions/{session_id}", headers=auth_headers)).json()
    assert session["turns"] == [] and session["turn_count"] == 0


async def test_rate_limit_per_user(client: AsyncClient, session_id: str, auth_headers: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    assert (await ask(client, session_id, auth_headers, "hello")).status_code == 200
    assert (await ask(client, session_id, auth_headers, "hello again")).status_code == 200
    limited = await ask(client, session_id, auth_headers, "third")
    assert limited.status_code == 429 and limited.json()["code"] == "rate_limited"
    assert 1 <= int(limited.headers["retry-after"]) <= 61
    # The limit is per user, across sessions.
    other_session = (await client.post("/v1/ai/sessions", json={}, headers=auth_headers)).json()["id"]
    assert (await ask(client, other_session, auth_headers, "hi")).status_code == 429


async def test_idempotent_replay_returns_the_same_answer(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    first = await ask(client, session_id, auth_headers, "dental", **{"Idempotency-Key": "msg-0000-0001"})
    calls = len(llm.requests)
    second = await ask(client, session_id, auth_headers, "dental", **{"Idempotency-Key": "msg-0000-0001"})
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"]
    assert len(llm.requests) == calls
    bad = await ask(client, session_id, auth_headers, "dental", **{"Idempotency-Key": "short"})
    assert bad.status_code == 422


async def test_session_turn_cap(client: AsyncClient, session_id: str, auth_headers: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_turns_per_session", 1)
    assert (await ask(client, session_id, auth_headers, "hello")).status_code == 200
    full = await ask(client, session_id, auth_headers, "hello")
    assert full.status_code == 409


async def test_user_deleted_erases_sessions(client: AsyncClient, session_id: str, auth_headers: dict, user_id: str) -> None:
    await ask(client, session_id, auth_headers, "dental")
    await handle_user_deleted({"tenant_id": settings.tenant_default, "payload": {"user_id": user_id, "deleted_at": "2030-01-01T00:00:00Z"}})
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(AiSession).where(AiSession.user_id == user_id)) == 0
        assert await db.scalar(select(func.count()).select_from(AiTurn).where(AiTurn.user_id == user_id)) == 0
    # Redelivery is harmless.
    await handle_user_deleted({"tenant_id": settings.tenant_default, "payload": {"user_id": user_id}})
    with pytest.raises(ValueError):
        await handle_user_deleted({"payload": {}})


async def test_message_content_is_not_logged(client: AsyncClient, session_id: str, auth_headers: dict, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    marker = "ZEBRA-PRIVATE-MARKER dental"
    await ask(client, session_id, auth_headers, marker)
    assert "ZEBRA-PRIVATE-MARKER" not in caplog.text


def test_migration_downgrade_and_upgrade() -> None:
    env = {**os.environ}
    alembic = [sys.executable, "-m", "alembic"]
    for step in (["downgrade", "base"], ["upgrade", "head"], ["downgrade", "-1"], ["upgrade", "head"]):
        result = subprocess.run([*alembic, *step], cwd=SERVICE_ROOT, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    current = subprocess.run([*alembic, "current"], cwd=SERVICE_ROOT, env=env, capture_output=True, text=True)
    assert "0001_ai_sessions (head)" in current.stdout
