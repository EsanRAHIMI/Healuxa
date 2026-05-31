from __future__ import annotations

import base64
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from healuxa_py_common.errors import error_response
from healuxa_py_common.middleware.auth import Principal
from healuxa_py_common.observability.tracing import get_trace_id
from identity_service.config import settings
from identity_service.domain.security import verify_client_secret
from identity_service.infra.db import get_session
from identity_service.infra.models import ServiceClient
from identity_service.infra.redis_client import get_redis

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(session: Annotated[AsyncSession, Depends(get_session)]) -> AsyncSession:
    return session


async def get_redis_client():
    return await get_redis()


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client),
) -> Principal:
    if credentials and credentials.credentials:
        from identity_service.domain.auth_service import auth_service

        introspection = await auth_service.introspect(db, redis, credentials.credentials)
        if introspection.active and introspection.sub:
            return Principal(
                user_id=introspection.sub,
                tenant_id=introspection.tenant or settings.tenant_default,
                roles=tuple(introspection.roles or []),
                permissions=tuple(introspection.perms or []),
                session_id=introspection.session_id,
            )
    raise HTTPException(
        status_code=401,
        detail=error_response(
            status=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Missing or invalid token",
            trace_id=get_trace_id(),
        ),
    )


async def require_service_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> str:
    client_id = settings.service_auth_client_id
    client_secret = settings.service_auth_client_secret

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth.split(" ", 1)[1]).decode()
            client_id, _, client_secret = decoded.partition(":")
        except Exception:
            pass
    else:
        client_id = request.headers.get("X-Service-Client-Id", client_id)
        client_secret = request.headers.get("X-Service-Client-Secret", client_secret)

    if client_id == settings.service_auth_client_id and client_secret == settings.service_auth_client_secret:
        return client_id

    client = await db.get(ServiceClient, client_id)
    if client and verify_client_secret(client_secret, client.client_secret_hash):
        return client_id

    raise HTTPException(
        status_code=401,
        detail=error_response(
            status=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Invalid service credentials",
            trace_id=get_trace_id(),
        ),
    )


def extract_bearer_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials:
        return credentials.credentials
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def service_auth_headers() -> dict[str, str]:
    return {
        "X-Service-Client-Id": settings.service_auth_client_id,
        "X-Service-Client-Secret": settings.service_auth_client_secret,
    }
