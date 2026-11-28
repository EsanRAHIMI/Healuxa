from __future__ import annotations

from typing import Any

from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.jetstream import JetStreamConnection

from transformation_engine.domain.appointment_event_handler import appointment_event_handler
from transformation_engine.infra.db import SessionLocal
from transformation_engine.infra.event_models import CONSUMER_NAME

# All appointment lifecycle events, v1; the handler ignores the types it does not project.
SUBJECT = "healuxa.appointment.*.v1"
DURABLE_NAME = f"{CONSUMER_NAME}-appointment-events"


async def handle_message(envelope_data: dict[str, Any]) -> None:
    """JetStream entry point. Raising leads to redelivery; the handler is idempotent on event_id."""
    async with SessionLocal() as db:
        await appointment_event_handler.handle(envelope_data, db=db)


def build_consumer(connection: JetStreamConnection) -> DurableConsumer:
    return DurableConsumer(connection, subject=SUBJECT, durable=DURABLE_NAME, handler=handle_message)
