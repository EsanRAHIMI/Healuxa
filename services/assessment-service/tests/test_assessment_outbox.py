"""assessment.completed must be staged atomically with completion and delivered via JetStream."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from httpx import AsyncClient

from assessment_service.infra.mongo import get_database

pytestmark = pytest.mark.mongo


async def _start(client: AsyncClient, user_id: str, headers: dict) -> str:
    response = await client.post("/v1/assessments", json={"user_id": user_id, "kind": "beauty"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _outbox(assessment_id: str) -> list[dict]:
    return await get_database()["outbox_events"].find({"body.payload.assessment_id": assessment_id}).to_list()


async def test_submit_stages_exactly_one_completed_event(client: AsyncClient, user_id: str, auth_headers: dict):
    assessment_id = await _start(client, user_id, auth_headers)
    trace_id = uuid.uuid4().hex

    submit = await client.post(
        f"/v1/assessments/{assessment_id}/submit",
        json={"responses": [{"q1": "a"}]},
        headers={**auth_headers, "X-Trace-Id": trace_id},
    )
    assert submit.status_code == 200, submit.text

    [entry] = await _outbox(assessment_id)
    assert entry["status"] == "pending"
    assert entry["subject"] == "healuxa.assessment.completed.v1"
    assert entry["body"]["payload"]["user_id"] == user_id
    assert entry["body"]["trace_id"] == trace_id
    assert entry["body"]["correlation_id"] == trace_id


async def test_rejected_submit_stages_no_event(client: AsyncClient, user_id: str, auth_headers: dict):
    assessment_id = await _start(client, user_id, auth_headers)
    url = f"/v1/assessments/{assessment_id}/submit"
    assert (await client.post(url, json={"responses": []}, headers=auth_headers)).status_code == 200
    assert (await client.post(url, json={"responses": []}, headers=auth_headers)).status_code == 409
    assert len(await _outbox(assessment_id)) == 1


async def test_concurrent_submits_complete_once(client: AsyncClient, user_id: str, auth_headers: dict):
    assessment_id = await _start(client, user_id, auth_headers)
    url = f"/v1/assessments/{assessment_id}/submit"

    responses = await asyncio.gather(
        *(client.post(url, json={"responses": [{"n": i}]}, headers=auth_headers) for i in range(6))
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(200) == 1, statuses
    assert set(statuses) <= {200, 409}
    assert len(await _outbox(assessment_id)) == 1, "concurrent submits must not emit duplicate events"


@pytest.mark.skipif(not os.environ.get("NATS_URL"), reason="NATS_URL not set")
async def test_outbox_relay_delivers_to_jetstream(client: AsyncClient, user_id: str, auth_headers: dict):
    from healuxa_py_common.events.consumer import DurableConsumer
    from healuxa_py_common.events.jetstream import JetStreamConnection
    from healuxa_py_common.events.outbox import JetStreamPublisher, OutboxRelay
    from healuxa_py_common.events.outbox_mongo import MongoOutboxStore

    assessment_id = await _start(client, user_id, auth_headers)
    url = f"/v1/assessments/{assessment_id}/submit"
    assert (await client.post(url, json={"responses": []}, headers=auth_headers)).status_code == 200

    connection = JetStreamConnection(os.environ["NATS_URL"], name="assessment-tests")
    try:
        store = MongoOutboxStore(get_database()["outbox_events"])
        assert await OutboxRelay(store, JetStreamPublisher(connection)).run_once() >= 1
        assert (await _outbox(assessment_id))[0]["status"] == "published"

        received: list[dict] = []

        async def handler(envelope: dict) -> None:
            if envelope["payload"]["assessment_id"] == assessment_id:
                received.append(envelope)

        consumer = DurableConsumer(
            connection,
            subject="healuxa.assessment.completed.v1",
            durable=f"assessment-test-{uuid.uuid4().hex[:8]}",
            handler=handler,
            batch_size=100,
        )
        for _ in range(5):
            await consumer.run_once(timeout=0.5)
        assert len(received) == 1
    finally:
        await connection.close()
