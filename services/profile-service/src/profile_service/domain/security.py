from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def format_etag(version: int) -> str:
    return f'v{version}'
