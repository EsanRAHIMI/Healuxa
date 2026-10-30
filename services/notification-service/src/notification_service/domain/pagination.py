from __future__ import annotations

import base64
import json
from datetime import datetime

from healuxa_py_common.errors import ApiError


def encode_cursor(*, created_at: datetime, resource_id: str) -> str:
    payload = {"t": created_at.isoformat(), "i": resource_id}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        payload = json.loads(raw)
        created_at = datetime.fromisoformat(payload["t"])
        resource_id = payload["i"]
        if not isinstance(resource_id, str) or not resource_id:
            raise ValueError("invalid id")
        return created_at, resource_id
    except Exception as exc:
        raise ApiError(
            status=422,
            code="validation_error",
            title="Validation failed",
            detail="Invalid cursor",
            errors=[{"field": "cursor", "code": "invalid", "message": "cursor is malformed"}],
        ) from exc
