from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.config import settings
from identity_service.infra.models import JwksKey


def _fernet_key() -> bytes:
    digest = hashlib.sha256(settings.mfa_encryption_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_pem(pem: str) -> str:
    from cryptography.fernet import Fernet

    return Fernet(_fernet_key()).encrypt(pem.encode()).decode()


def decrypt_pem(encrypted: str) -> str:
    from cryptography.fernet import Fernet

    return Fernet(_fernet_key()).decrypt(encrypted.encode()).decode()


def _pem_to_jwk(public_pem: str, kid: str) -> dict:
    public_key = serialization.load_pem_public_key(public_pem.encode())
    numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": jwt.utils.base64url_encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")).decode(),
        "e": jwt.utils.base64url_encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")).decode(),
    }


class JwtService:
    def __init__(self) -> None:
        self._active_kid: str | None = None
        self._private_pem: str | None = None

    async def ensure_active_key(self, db: AsyncSession) -> None:
        if self._private_pem:
            return
        if settings.jwt_private_key_pem:
            self._private_pem = settings.jwt_private_key_pem
            self._active_kid = "env-key"
            return

        result = await db.execute(
            select(JwksKey).where(JwksKey.status == "active").order_by(JwksKey.created_at.desc())
        )
        row = result.scalar_one_or_none()
        if row:
            self._active_kid = row.kid
            self._private_pem = decrypt_pem(row.private_pem_enc)
            return

        from ulid import ULID

        kid = str(ULID())
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        db.add(
            JwksKey(
                kid=kid,
                public_pem=public_pem,
                private_pem_enc=encrypt_pem(private_pem),
                status="active",
            )
        )
        await db.commit()
        self._active_kid = kid
        self._private_pem = private_pem

    async def jwks(self, db: AsyncSession) -> dict:
        await self.ensure_active_key(db)
        result = await db.execute(select(JwksKey).where(JwksKey.status.in_(["active", "retired"])))
        keys = [_pem_to_jwk(row.public_pem, row.kid) for row in result.scalars()]
        return {"keys": keys}

    def issue_access_token(
        self,
        *,
        user_id: str,
        tenant_id: str,
        roles: list[str],
        permissions: list[str],
        session_id: str,
        ttl_seconds: int | None = None,
        subject_type: str = "user",
    ) -> tuple[str, int]:
        if not self._private_pem or not self._active_kid:
            raise RuntimeError("JWT key not initialized")
        expires_in = ttl_seconds or settings.jwt_access_ttl
        now = datetime.now(UTC)
        exp = now + timedelta(seconds=expires_in)
        payload = {
            "sub": user_id,
            "tenant": tenant_id,
            "roles": roles,
            "perms": permissions,
            "session_id": session_id,
            "typ": subject_type,
            "iss": settings.jwt_issuer,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, self._private_pem, algorithm="RS256", headers={"kid": self._active_kid})
        return token, expires_in

    def decode_access_token(self, token: str, db_keys: list[JwksKey]) -> dict | None:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        public_pem = None
        for row in db_keys:
            if row.kid == kid:
                public_pem = row.public_pem
                break
        if not public_pem and settings.jwt_private_key_pem:
            public_pem = (
                serialization.load_pem_private_key(settings.jwt_private_key_pem.encode(), password=None)
                .public_key()
                .public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                .decode()
            )
        if not public_pem:
            return None
        try:
            return jwt.decode(
                token,
                public_pem,
                algorithms=["RS256"],
                issuer=settings.jwt_issuer,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError:
            return None


jwt_service = JwtService()
