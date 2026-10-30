"""Outbox events (ids + metadata only) and API/event contract compliance."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from httpx import AsyncClient

from concierge_service.events.publisher import event_publisher
from concierge_service.main import app
from helpers import claim, coordinator, create_case, customer, new_user, ok, working_case

REPO = Path(__file__).resolve().parents[3]
CONTRACT = REPO / "packages/api-contracts/openapi/concierge.openapi.yaml"
EVENT_SCHEMA = REPO / "packages/event-contracts/schemas/concierge.schema.json"
SECRET_TEXT = "Wheelchair-accessible hotel"


def _schema_defs() -> dict:
    return json.loads(EVENT_SCHEMA.read_text())["$defs"]


def _assert_matches_schema(envelope: dict, def_name: str) -> None:
    schema = _schema_defs()[def_name]
    payload = envelope["payload"]
    assert set(schema["required"]) <= payload.keys(), payload
    assert payload.keys() <= schema["properties"].keys(), payload
    assert envelope["producer"] == "concierge-service"
    assert envelope["schema_ref"].endswith(def_name)


async def test_submission_stages_case_submitted(client: AsyncClient) -> None:
    from helpers import outbox_events

    owner = new_user()
    case = await create_case(client, owner)
    [event] = await outbox_events("concierge.case_submitted")
    _assert_matches_schema(event, "ConciergeCaseSubmitted")
    assert event["payload"]["case_id"] == case["id"] and event["payload"]["customer_id"] == owner
    assert SECRET_TEXT not in json.dumps(event)


async def test_status_changes_stage_events_without_free_text(client: AsyncClient) -> None:
    from helpers import outbox_events

    setup = await working_case(client)
    await ok(
        await client.post(
            f"/v1/concierge/cases/{setup['case']['id']}/escalation",
            json={"reason": "customer mentioned a private matter"},
            headers=customer(setup["owner"]),
        )
    )
    events = await outbox_events("concierge.case_status_changed")
    assert [(e["payload"]["previous_status"], e["payload"]["status"]) for e in events] == [
        ("submitted", "assigned"),
        ("assigned", "in_progress"),
        ("in_progress", "escalated"),
    ]
    for event in events:
        _assert_matches_schema(event, "ConciergeCaseStatusChanged")
        assert "private matter" not in json.dumps(event)
    assert events[0]["payload"]["coordinator_id"] == setup["coordinator"]


async def test_message_event_never_contains_message_text(client: AsyncClient) -> None:
    from helpers import outbox_events

    setup = await working_case(client)
    body = "My passport number is in the attached form"
    message = await ok(await client.post(f"/v1/concierge/cases/{setup['case']['id']}/messages", json={"body": body}, headers=customer(setup["owner"])), 201)
    [event] = await outbox_events("concierge.message_posted")
    _assert_matches_schema(event, "ConciergeMessagePosted")
    assert event["payload"]["message_id"] == message["id"] and event["payload"]["sender_role"] == "customer"
    assert body not in json.dumps(event) and "body" not in event["payload"]


async def test_failed_transition_stages_nothing(client: AsyncClient) -> None:
    from helpers import outbox_events

    case = await create_case(client, new_user())
    response = await client.post(f"/v1/concierge/cases/{case['id']}/transitions", json={"to_status": "completed"}, headers=coordinator(new_user()))
    assert response.status_code == 409
    assert await outbox_events("concierge.case_status_changed") == []
    await claim(client, case["id"], new_user())
    assert len(await outbox_events("concierge.case_status_changed")) == 1


async def test_publisher_refuses_free_text_keys() -> None:
    with pytest.raises(ValueError):
        await event_publisher.publish(db=None, event_type="concierge.message_posted", tenant_id="t", payload={"body": "x"})  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await event_publisher.publish(db=None, event_type="concierge.unknown", tenant_id="t", payload={})  # type: ignore[arg-type]


def _normalise(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def test_generated_openapi_matches_contract() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    expected = {
        (_normalise("/v1" + path), method.upper(), op["operationId"])
        for path, ops in contract["paths"].items()
        for method, op in ops.items()
    }
    generated = app.openapi()
    actual = {
        (_normalise(path), method.upper(), op["operationId"])
        for path, ops in generated["paths"].items()
        for method, op in ops.items()
    }
    assert actual == expected


@pytest.mark.skipif(not __import__("os").environ.get("NATS_URL"), reason="NATS_URL not set")
async def test_outbox_relay_publishes_to_jetstream(client: AsyncClient) -> None:
    import os

    from healuxa_py_common.events.jetstream import EVENTS_STREAM, JetStreamConnection, subject_for
    from healuxa_py_common.events.outbox import JetStreamPublisher, OutboxRelay
    from healuxa_py_common.events.outbox_sql import SqlOutboxStore
    from ulid import ULID

    from concierge_service.infra.db import SessionLocal
    from concierge_service.infra.models import OUTBOX

    case = await create_case(client, new_user())
    connection = JetStreamConnection(os.environ["NATS_URL"], name="concierge-tests")
    try:
        js = await connection.jetstream()
        sub = await js.pull_subscribe(
            subject_for("concierge.case_submitted"), durable=f"concierge-test-{ULID()}", stream=EVENTS_STREAM
        )
        relay = OutboxRelay(SqlOutboxStore(SessionLocal, OUTBOX), JetStreamPublisher(connection))
        assert await relay.run_once() >= 1
        found = False
        for _ in range(5):
            try:
                messages = await sub.fetch(50, timeout=1)
            except Exception:  # noqa: BLE001 — fetch timeout
                break
            for msg in messages:
                await msg.ack()
                if json.loads(msg.data)["payload"]["case_id"] == case["id"]:
                    found = True
            if found:
                break
        assert found
    finally:
        await connection.close()
