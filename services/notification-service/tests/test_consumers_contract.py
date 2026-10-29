"""Event consumers (handler + real JetStream), idempotency, DLQ, recipient links, contract diff."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from httpx import AsyncClient

from notification_service.consumers.handlers import AWAITING_REGISTRY_MERGE, PLANNERS, PoisonEvent, handle_message, process_event
from notification_service.infra.db import SessionLocal
from notification_service.infra.models import ProcessedEvent
from notification_service.main import app
from helpers import envelope, new_id, notifications_of, ok, service, status_changed, user

REPO = Path(__file__).resolve().parents[3]
needs_nats = pytest.mark.skipif(not os.environ.get("NATS_URL"), reason="NATS_URL not set")


async def _process(env: dict) -> str:
    async with SessionLocal() as db:
        return await process_event(env, db=db)


async def test_status_change_notifies_customer_and_assigned_coordinator(client: AsyncClient) -> None:
    customer, coordinator = new_id(), new_id()
    assert await _process(status_changed(customer, "assigned", coordinator_id=coordinator)) == "notified"
    [to_customer] = await notifications_of(customer)
    [to_coordinator] = await notifications_of(coordinator)
    assert to_customer.template_key == "concierge.case_status_changed" and "Assigned to a coordinator" in to_customer.body
    assert to_coordinator.template_key == "concierge.case_assigned"
    assert to_customer.entity_type == "concierge_case"


async def test_message_posted_notifies_only_the_counterparty(client: AsyncClient) -> None:
    customer, coordinator = new_id(), new_id()
    payload = {
        "case_id": new_id(),
        "message_id": new_id(),
        "customer_id": customer,
        "coordinator_id": coordinator,
        "sender_id": customer,
        "sender_role": "customer",
        "posted_at": datetime.now(UTC).isoformat(),
    }
    await _process(envelope("concierge.message_posted", payload))
    assert await notifications_of(customer) == []
    [note] = await notifications_of(coordinator)
    assert note.template_key == "concierge.message_posted" and "Open the app" in note.body
    # Unassigned case: a customer message has nobody to notify yet.
    unassigned = {**payload, "coordinator_id": None, "message_id": new_id()}
    assert await _process(envelope("concierge.message_posted", unassigned)) == "no_recipient"


async def test_catalog_events_use_recipient_links(client: AsyncClient) -> None:
    owner, facility_admin, provider_id, facility_id = new_id(), new_id(), new_id(), new_id()
    unlinked = envelope("catalog.provider_status_changed", {"provider_id": provider_id, "status": "active", "verification_status": "verified", "changed_at": datetime.now(UTC).isoformat()})
    assert await _process(unlinked) == "no_recipient"
    await ok(await client.post("/v1/notifications/recipient-links", json={"entity_type": "provider", "entity_id": provider_id, "user_id": owner, "role": "owner"}, headers=service()), 201)
    await ok(await client.post("/v1/notifications/recipient-links", json={"entity_type": "facility", "entity_id": facility_id, "user_id": facility_admin}, headers=service()), 201)
    status = envelope("catalog.provider_status_changed", {"provider_id": provider_id, "status": "suspended", "verification_status": "verified", "changed_at": datetime.now(UTC).isoformat()})
    assert await _process(status) == "notified"
    [n] = await notifications_of(owner)
    assert "Suspended" in n.body and n.needs_professional_review is True
    affiliation = envelope("catalog.affiliation_changed", {"affiliation_id": new_id(), "provider_id": provider_id, "facility_id": facility_id, "branch_id": new_id(), "status": "active", "changed_at": datetime.now(UTC).isoformat()})
    await _process(affiliation)
    assert len(await notifications_of(owner)) == 2 and len(await notifications_of(facility_admin)) == 1
    # Links are internal: users may not register them.
    response = await client.post("/v1/notifications/recipient-links", json={"entity_type": "provider", "entity_id": provider_id, "user_id": new_id()}, headers=user(new_id()))
    assert response.status_code == 403
    assert (await client.delete(f"/v1/notifications/recipient-links/provider/{provider_id}/{owner}", headers=service())).status_code == 204
    assert (await client.delete(f"/v1/notifications/recipient-links/provider/{provider_id}/{owner}", headers=service())).status_code == 404


@pytest.mark.parametrize("event_type", sorted(t for t in PLANNERS if t.startswith("appointment.")))
async def test_appointment_events_notify_customer(client: AsyncClient, event_type: str) -> None:
    uid = new_id()
    payload = {"appointment_id": new_id(), "user_id": uid, "provider_id": new_id(), "service_id": new_id(), "scheduled_at": "2026-12-01T10:30:00+00:00"}
    await _process(envelope(event_type, payload))
    [n] = await notifications_of(uid)
    assert n.template_key == event_type and "2026-12-01 10:30 UTC" in n.body and n.category == "appointments"


async def test_duplicate_event_is_processed_once(client: AsyncClient) -> None:
    customer = new_id()
    event = status_changed(customer, "completed")
    assert await _process(event) == "notified"
    assert await _process(event) == "duplicate"
    # Even if the processed marker were lost, (event, recipient, channel) uniqueness holds.
    async with SessionLocal() as db:
        await db.delete(await db.get(ProcessedEvent, event["event_id"]))
        await db.commit()
    assert await _process(event) == "notified"
    assert len(await notifications_of(customer)) == 1


async def test_malformed_events_are_poison(client: AsyncClient) -> None:
    with pytest.raises(PoisonEvent):
        await _process(envelope("concierge.case_status_changed", {"case_id": new_id()}))
    with pytest.raises(PoisonEvent):
        await _process(status_changed(new_id(), "teleported"))
    with pytest.raises(PoisonEvent):
        await _process({"type": "concierge.case_status_changed"})


async def test_unsubscribed_event_type_is_ignored(client: AsyncClient) -> None:
    assert await _process(envelope("journey.created", {"journey_id": new_id(), "user_id": new_id()})) == "ignored"


def test_consumed_events_exist_in_registry_with_us_as_consumer() -> None:
    registry = (REPO / "packages/event-contracts/src/registry.ts").read_text()
    for event_type in sorted(set(PLANNERS) - AWAITING_REGISTRY_MERGE):
        line = next((ln for ln in registry.splitlines() if f'"{event_type}": {{' in ln), None)
        assert line is not None, event_type
        assert '"notification-service"' in line.split("consumers:")[1], event_type
    # Pending the appointment-service merge: when present they must list notification-service.
    for event_type in AWAITING_REGISTRY_MERGE:
        line = next((ln for ln in registry.splitlines() if f'"{event_type}": {{' in ln), None)
        assert line is None or '"notification-service"' in line, event_type


async def _consume(consumer, rounds: int = 6) -> None:
    for _ in range(rounds):
        await consumer.run_once(timeout=0.5)


@needs_nats
async def test_jetstream_end_to_end_inbox_and_duplicate_delivery(client: AsyncClient) -> None:
    from healuxa_py_common.events.consumer import DurableConsumer
    from healuxa_py_common.events.jetstream import EVENTS_STREAM, JetStreamConnection, subject_for

    customer = new_id()
    event = status_changed(customer, "awaiting_customer")
    subject = subject_for("concierge.case_status_changed")
    connection = JetStreamConnection(os.environ["NATS_URL"], name="notification-tests")
    seen: list[str] = []

    async def handler(body: dict) -> None:
        if body.get("event_id") == event["event_id"]:
            seen.append(body["event_id"])
            await handle_message(body)

    try:
        js = await connection.jetstream()
        data = json.dumps(event).encode()
        # Two physical deliveries of one event (no Nats-Msg-Id) simulate at-least-once redelivery.
        await js.publish(subject, data, stream=EVENTS_STREAM)
        await js.publish(subject, data, stream=EVENTS_STREAM)
        consumer = DurableConsumer(connection, subject=subject, durable=f"ns-test-{new_id()}", handler=handler, batch_size=500)
        await _consume(consumer)
    finally:
        await connection.close()
    assert len(seen) == 2
    inbox = await ok(await client.get("/v1/notifications", headers=user(customer)))
    assert [n["template"] for n in inbox["data"]] == ["concierge.case_status_changed"]
    assert "Waiting for your reply" in inbox["data"][0]["body"]


@needs_nats
async def test_jetstream_poison_message_is_dead_lettered(client: AsyncClient) -> None:
    from healuxa_py_common.events.consumer import DurableConsumer
    from healuxa_py_common.events.jetstream import DLQ_STREAM, EVENTS_STREAM, JetStreamConnection, dlq_subject_for, subject_for

    poison = envelope("concierge.message_posted", {"case_id": new_id()})  # required ids missing
    subject = subject_for("concierge.message_posted")
    durable = f"ns-dlq-{new_id()}"
    connection = JetStreamConnection(os.environ["NATS_URL"], name="notification-dlq-tests")

    async def handler(body: dict) -> None:
        if body.get("event_id") == poison["event_id"]:
            await handle_message(body)

    try:
        js = await connection.jetstream()
        dlq = await js.pull_subscribe(dlq_subject_for(subject), durable=f"{durable}-dlq", stream=DLQ_STREAM)
        await js.publish(subject, json.dumps(poison).encode(), stream=EVENTS_STREAM)
        consumer = DurableConsumer(
            connection, subject=subject, durable=durable, handler=handler, max_deliver=2, backoff=(0.2,), batch_size=500
        )
        found = None
        for _ in range(20):
            await consumer.run_once(timeout=0.3)
            try:
                for msg in await dlq.fetch(50, timeout=0.3):
                    await msg.ack()
                    if json.loads(msg.data).get("event_id") == poison["event_id"]:
                        found = msg
            except Exception:  # noqa: BLE001 — fetch timeout: nothing dead-lettered yet
                pass
            if found:
                break
            await asyncio.sleep(0.1)
    finally:
        await connection.close()
    assert found is not None
    assert found.headers["Healuxa-Dlq-Consumer"] == durable and "PoisonEvent" in found.headers["Healuxa-Dlq-Reason"]
    async with SessionLocal() as db:
        assert await db.get(ProcessedEvent, poison["event_id"]) is None


def _normalise(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def test_generated_openapi_matches_contract() -> None:
    contract = yaml.safe_load((REPO / "packages/api-contracts/openapi/notification.openapi.yaml").read_text())
    expected = {(_normalise("/v1" + p), m.upper(), op["operationId"]) for p, ops in contract["paths"].items() for m, op in ops.items()}
    actual = {(_normalise(p), m.upper(), op["operationId"]) for p, ops in app.openapi()["paths"].items() for m, op in ops.items()}
    assert actual == expected
