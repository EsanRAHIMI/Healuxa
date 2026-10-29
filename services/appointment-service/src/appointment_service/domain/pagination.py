from __future__ import annotations

import base64
import json
from datetime import datetime

from healuxa_py_common.errors import ApiError


def _invalid() -> ApiError:
    return ApiError(
        status=422,
        code="validation_error",
        title="Validation failed",
        detail="Invalid cursor",
        errors=[{"field": "cursor", "code": "invalid", "message": "cursor is malformed"}],
    )


def encode_cursor(starts_at: datetime, resource_id: str, sort: str) -> str:
    payload = {"t": starts_at.isoformat(), "i": resource_id, "s": sort}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: str, sort: str) -> tuple[datetime, str]:
    """Keyset cursor over (scheduled_at, id); it is bound to the sort order it was issued for."""
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        starts_at = datetime.fromisoformat(payload["t"])
        resource_id = payload["i"]
        if not isinstance(resource_id, str) or not resource_id or starts_at.tzinfo is None:
            raise ValueError("invalid cursor")
    except Exception as exc:
        raise _invalid() from exc
    if payload.get("s") != sort:
        raise _invalid()
    return starts_at, resource_id
