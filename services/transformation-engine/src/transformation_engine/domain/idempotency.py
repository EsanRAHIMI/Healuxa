from __future__ import annotations

import hashlib
import json

from healuxa_py_common.errors import ApiError
from sqlalchemy.ext.asyncio import AsyncSession

from transformation_engine.infra.models import IdempotencyRecord

IDEMPOTENCY_KEY_MIN_LEN = 8
IDEMPOTENCY_KEY_MAX_LEN = 128


def validate_idempotency_key(key: str | None) -> None:
    if key is None:
        return
    if len(key) < IDEMPOTENCY_KEY_MIN_LEN or len(key) > IDEMPOTENCY_KEY_MAX_LEN:
        raise ApiError(
            status=422,
            code="validation_error",
            title="Validation failed",
            detail="Idempotency-Key must be between 8 and 128 characters",
            errors=[
                {
                    "field": "Idempotency-Key",
                    "code": "invalid_length",
                    "message": "must be between 8 and 128 characters",
                }
            ],
        )


def hash_request_body(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


async def read_idempotent_response(
    db: AsyncSession,
    key: str,
    *,
    request_hash: str,
) -> dict | None:
    record = await db.get(IdempotencyRecord, key)
    if not record:
        return None
    if record.request_hash != request_hash:
        raise ApiError(
            status=409,
            code="idempotency_conflict",
            title="Idempotency conflict",
            detail="Idempotency-Key reused with different body",
        )
    return dict(record.response_body)


async def store_idempotent_response(
    db: AsyncSession,
    key: str,
    *,
    request_hash: str,
    status_code: int,
    response_body: dict,
) -> None:
    db.add(
        IdempotencyRecord(
            key=key,
            request_hash=request_hash,
            status_code=status_code,
            response_body=response_body,
        )
    )
    await db.commit()
