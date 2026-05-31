from __future__ import annotations

from redis.asyncio import Redis

SESSION_DENY_PREFIX = "deny:session:"
LOCKOUT_PREFIX = "lockout:"


async def deny_session(redis: Redis, session_id: str, ttl_seconds: int) -> None:
    await redis.set(f"{SESSION_DENY_PREFIX}{session_id}", "1", ex=ttl_seconds)


async def is_session_denied(redis: Redis, session_id: str) -> bool:
    return bool(await redis.exists(f"{SESSION_DENY_PREFIX}{session_id}"))


async def set_lockout(redis: Redis, identifier: str, seconds: int) -> None:
    await redis.set(f"{LOCKOUT_PREFIX}{identifier}", "1", ex=seconds)


async def is_locked_out(redis: Redis, identifier: str) -> bool:
    return bool(await redis.exists(f"{LOCKOUT_PREFIX}{identifier}"))
