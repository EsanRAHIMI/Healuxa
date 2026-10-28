"""Integration tests against real NATS JetStream, PostgreSQL and MongoDB.

Each backend is opt-in via env var so the unit suite still runs anywhere:
  NATS_URL=nats://127.0.0.1:4222
  OUTBOX_TEST_DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/identity_test
  MONGODB_URI=mongodb://127.0.0.1:27020/?replicaSet=rs0
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest

from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.envelope import build_envelope
from healuxa_py_common.events.jetstream import DLQ_STREAM, JetStreamConnection, dlq_subject_for
from healuxa_py_common.events.outbox import JetStreamPublisher, OutboxRelay, outbox_fields

NATS_URL = os.environ.get("NATS_URL")
SQL_URL = os.environ.get("OUTBOX_TEST_DATABASE_URL")
MONGODB_URI = os.environ.get("MONGODB_URI")

needs_nats = pytest.mark.skipif(not NATS_URL, reason="NATS_URL not set")


def _envelope(event_type: str = "assessment.completed"):
    return build_envelope(
        event_type=event_type,
        version=1,
        schema_ref="ref",
        tenant_id="healuxa-dubai",
        producer="test-producer",
        payload={"n": 1},
        allowed_producers={"test-producer"},
    )


@pytest.fixture
async def connection():
    conn = JetStreamConnection(NATS_URL or "", name="py-common-tests")
    yield conn
    await conn.close()


@pytest.fixture
def subject() -> str:
    # Unique event type per test so durable consumers never see another test's messages.
    return f"healuxa.test{uuid.uuid4().hex[:10]}.happened.v1"


async def _drain(consumer: DurableConsumer, rounds: int = 10) -> None:
    for _ in range(rounds):
        await consumer.run_once(timeout=0.5)


@needs_nats
async def test_publish_is_deduplicated_by_event_id(connection, subject) -> None:
    from healuxa_py_common.events.outbox import OutboxMessage

    publisher = JetStreamPublisher(connection)
    message = OutboxMessage(event_id=str(uuid.uuid4()), subject=subject, body={"x": 1}, attempts=0)
    await publisher.publish(message)
    await publisher.publish(message)  # relay crashed before mark_published → republish

    seen: list[dict] = []

    async def handler(envelope: dict) -> None:
        seen.append(envelope)

    consumer = DurableConsumer(connection, subject=subject, durable=f"d{uuid.uuid4().hex[:8]}", handler=handler)
    await _drain(consumer, rounds=3)
    assert len(seen) == 1


@needs_nats
async def test_failing_handler_is_retried_then_dead_lettered(connection, subject) -> None:
    from healuxa_py_common.events.outbox import OutboxMessage

    event_id = str(uuid.uuid4())
    await JetStreamPublisher(connection).publish(
        OutboxMessage(event_id=event_id, subject=subject, body={"event_id": event_id}, attempts=0)
    )
    attempts = 0

    async def handler(envelope: dict) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("downstream unavailable")

    consumer = DurableConsumer(
        connection,
        subject=subject,
        durable=f"d{uuid.uuid4().hex[:8]}",
        handler=handler,
        max_deliver=3,
        backoff=(0.1,),
    )
    for _ in range(30):
        await consumer.run_once(timeout=0.3)
        if attempts >= 3:
            await consumer.run_once(timeout=0.3)
            break
    assert attempts == 3

    js = await connection.jetstream()
    msg = await js.get_last_msg(DLQ_STREAM, dlq_subject_for(subject))
    assert json.loads(msg.data)["event_id"] == event_id
    assert "downstream unavailable" in msg.headers["Healuxa-Dlq-Reason"]
    assert msg.headers["Healuxa-Original-Subject"] == subject


@needs_nats
async def test_successful_handler_acks_once(connection, subject) -> None:
    from healuxa_py_common.events.outbox import OutboxMessage

    await JetStreamPublisher(connection).publish(
        OutboxMessage(event_id=str(uuid.uuid4()), subject=subject, body={}, attempts=0)
    )
    calls = 0

    async def handler(envelope: dict) -> None:
        nonlocal calls
        calls += 1

    consumer = DurableConsumer(
        connection, subject=subject, durable=f"d{uuid.uuid4().hex[:8]}", handler=handler, ack_wait=1.0
    )
    await _drain(consumer, rounds=2)
    await asyncio.sleep(1.5)  # past ack_wait: an un-acked message would be redelivered now
    await _drain(consumer, rounds=2)
    assert calls == 1


# --- PostgreSQL store -------------------------------------------------------------------------


@pytest.fixture
async def sql_store():
    from sqlalchemy import MetaData
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from healuxa_py_common.events.outbox_sql import SqlOutboxStore, outbox_table

    engine = create_async_engine(SQL_URL or "")
    metadata = MetaData()
    table = outbox_table(metadata)
    table.name = f"outbox_test_{uuid.uuid4().hex[:8]}"
    for index in table.indexes:
        index.name = f"{index.name}_{table.name}"
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield SqlOutboxStore(factory, table), factory, table
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


@pytest.mark.skipif(not SQL_URL, reason="OUTBOX_TEST_DATABASE_URL not set")
async def test_sql_outbox_rollback_never_publishes(sql_store) -> None:
    from healuxa_py_common.events.outbox_sql import enqueue

    store, factory, table = sql_store
    async with factory() as session:
        async with session.begin():
            await enqueue(session, table, _envelope())
        async with session.begin():
            await enqueue(session, table, _envelope())
            await session.rollback()
    assert await store.pending_count() == 1


@pytest.mark.skipif(not SQL_URL, reason="OUTBOX_TEST_DATABASE_URL not set")
async def test_sql_concurrent_claims_never_overlap(sql_store) -> None:
    from datetime import timedelta

    from sqlalchemy import insert

    store, factory, table = sql_store
    async with factory() as session, session.begin():
        await session.execute(insert(table), [outbox_fields(_envelope()) for _ in range(40)])

    batches = await asyncio.gather(*(store.claim_batch(limit=15, lease=timedelta(seconds=30)) for _ in range(4)))
    claimed = [m.event_id for batch in batches for m in batch]
    assert len(claimed) == 40
    assert len(set(claimed)) == 40, "two relays leased the same event"


@needs_nats
@pytest.mark.skipif(not SQL_URL, reason="OUTBOX_TEST_DATABASE_URL not set")
async def test_sql_relay_end_to_end(sql_store, connection) -> None:
    from healuxa_py_common.events.outbox_sql import enqueue

    store, factory, table = sql_store
    envelope = _envelope(f"test{uuid.uuid4().hex[:10]}.happened")
    async with factory() as session, session.begin():
        await enqueue(session, table, envelope)

    assert await OutboxRelay(store, JetStreamPublisher(connection)).run_once() == 1
    assert await store.pending_count() == 0

    received: list[dict] = []

    async def handler(body: dict) -> None:
        received.append(body)

    consumer = DurableConsumer(
        connection,
        subject=f"healuxa.{envelope.type}.v1",
        durable=f"d{uuid.uuid4().hex[:8]}",
        handler=handler,
    )
    await _drain(consumer, rounds=2)
    assert [r["event_id"] for r in received] == [envelope.event_id]


# --- MongoDB store ----------------------------------------------------------------------------


@pytest.fixture
async def mongo_collection():
    from pymongo import AsyncMongoClient

    client = AsyncMongoClient(MONGODB_URI or "", serverSelectionTimeoutMS=5000)
    collection = client["healuxa_pycommon_test"][f"outbox_{uuid.uuid4().hex[:8]}"]
    yield client, collection
    await collection.drop()
    await client.close()


@pytest.mark.skipif(not MONGODB_URI, reason="MONGODB_URI not set")
async def test_mongo_outbox_aborted_transaction_never_publishes(mongo_collection) -> None:
    from healuxa_py_common.events.outbox_mongo import MongoOutboxStore, enqueue

    client, collection = mongo_collection
    await collection.database.create_collection(collection.name)
    async with client.start_session() as session:
        await session.start_transaction()
        await enqueue(collection, _envelope(), session=session)
        await session.abort_transaction()
    async with client.start_session() as session:
        await session.start_transaction()
        await enqueue(collection, _envelope(), session=session)
        await session.commit_transaction()
    assert await MongoOutboxStore(collection).pending_count() == 1


@pytest.mark.skipif(not MONGODB_URI, reason="MONGODB_URI not set")
async def test_mongo_concurrent_claims_never_overlap(mongo_collection) -> None:
    from datetime import timedelta

    from healuxa_py_common.events.outbox_mongo import MongoOutboxStore, enqueue

    _, collection = mongo_collection
    for _ in range(30):
        await enqueue(collection, _envelope())
    store = MongoOutboxStore(collection)
    batches = await asyncio.gather(*(store.claim_batch(limit=10, lease=timedelta(seconds=30)) for _ in range(4)))
    claimed = [m.event_id for batch in batches for m in batch]
    assert len(claimed) == 30
    assert len(set(claimed)) == 30
