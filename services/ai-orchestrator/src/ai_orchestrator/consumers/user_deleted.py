"""Right-to-erasure consumer: deletes assistant sessions and turns of users removed by identity-service.

identity-service emits ``auth.user_deleted`` when an account is deleted. Deleting by user id is
naturally idempotent, so redelivery is harmless; failures are retried and dead-lettered by
DurableConsumer.
"""

from __future__ import annotations

import logging
from typing import Any

from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.jetstream import JetStreamConnection, subject_for

from ai_orchestrator.config import settings
from ai_orchestrator.domain.session_service import erase_user
from ai_orchestrator.infra.db import SessionLocal

logger = logging.getLogger(__name__)

SUBJECT = subject_for("auth.user_deleted")
DURABLE_NAME = f"{settings.service_name}-user-deleted"


async def handle_user_deleted(envelope: dict[str, Any]) -> None:
    user_id = (envelope.get("payload") or {}).get("user_id")
    tenant_id = envelope.get("tenant_id")
    if not user_id or not tenant_id:
        raise ValueError("auth.user_deleted without user_id/tenant_id")
    async with SessionLocal() as db:
        erased = await erase_user(db, tenant_id=tenant_id, user_id=user_id)
    logger.info("erased %d assistant session(s) for deleted user %s", erased, user_id)


def build_consumer(connection: JetStreamConnection) -> DurableConsumer:
    return DurableConsumer(connection, subject=SUBJECT, durable=DURABLE_NAME, handler=handle_user_deleted)
