from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from identity_service.config import settings

_hasher = PasswordHasher(
    memory_cost=settings.argon2_memory_cost,
    time_cost=settings.argon2_time_cost,
    parallelism=settings.argon2_parallelism,
)


def hash_password(password: str) -> str:
    material = f"{password}{settings.password_pepper}"
    return _hasher.hash(material)


def verify_password(password: str, password_hash: str) -> bool:
    material = f"{password}{settings.password_pepper}"
    try:
        return _hasher.verify(password_hash, material)
    except VerifyMismatchError:
        return False


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_client_secret(secret: str) -> str:
    material = f"{secret}{settings.password_pepper}"
    return hashlib.sha256(material.encode()).hexdigest()


def verify_client_secret(secret: str, secret_hash: str) -> bool:
    return hash_client_secret(secret) == secret_hash


def utcnow() -> datetime:
    return datetime.now(UTC)
