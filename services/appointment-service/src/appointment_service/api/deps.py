from __future__ import annotations

import os
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from healuxa_py_common.errors import error_response
from healuxa_py_common.middleware.auth import EDGE_SECRET_ENV, EDGE_SECRET_HEADER, Principal, get_principal
from healuxa_py_common.observability.tracing import get_trace_id
from sqlalchemy.ext.asyncio import AsyncSession

from appointment_service.clients.provider_directory import ProviderDirectory
from appointment_service.config import settings
from appointment_service.infra.db import get_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(session: Annotated[AsyncSession, Depends(get_session)]) -> AsyncSession:
    return session


def get_directory(request: Request) -> ProviderDirectory:
    """The availability source wired in the lifespan (tests override this dependency with a fake)."""
    return request.app.state.directory


async def resolve_principal(
    request: Request,
    edge_principal: Principal | None = Depends(get_principal),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    if edge_principal is not None:
        return edge_principal

    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()

    if not token:
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

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                settings.identity_introspect_url,
                json={"token": token},
                headers={
                    "X-Service-Client-Id": settings.service_auth_client_id,
                    "X-Service-Client-Secret": settings.service_auth_client_secret,
                },
            )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail=error_response(
                status=503,
                code="service_unavailable",
                title="Service unavailable",
                detail="Identity introspection unavailable",
                trace_id=get_trace_id(),
            ),
        ) from None

    if response.status_code != 200:
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

    body = response.json()
    if not body.get("active") or not body.get("sub"):
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

    return Principal(
        user_id=body["sub"],
        tenant_id=body.get("tenant") or settings.tenant_default,
        roles=tuple(body.get("roles") or []),
        permissions=tuple(body.get("perms") or []),
        session_id=body.get("session_id"),
    )


async def optional_principal(
    request: Request,
    edge_principal: Principal | None = Depends(get_principal),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal | None:
    """Public endpoints: anonymous callers get the public view; a presented token must still be valid."""
    if edge_principal is None and credentials is None and not request.headers.get("Authorization"):
        return None
    return await resolve_principal(request, edge_principal, credentials)


def require_permission(permission: str):
    def _dependency(principal: Principal = Depends(resolve_principal)) -> Principal:
        if permission not in principal.permissions:
            raise HTTPException(
                status_code=403,
                detail=error_response(
                    status=403,
                    code="forbidden",
                    title="Forbidden",
                    detail=f"Missing permission: {permission}",
                    trace_id=get_trace_id(),
                ),
            )
        return principal

    return _dependency


def principal_headers(
    user_id: str,
    *,
    permissions: str = "appointments:create,appointments:read,appointments:write",
    tenant_id: str | None = None,
) -> dict[str, str]:
    return {
        "X-Healuxa-User": user_id,
        "X-Healuxa-Tenant": tenant_id or settings.tenant_default,
        "X-Healuxa-Perms": permissions,
        # Test/dev helper: emulates the edge, which must prove itself with the shared secret.
        EDGE_SECRET_HEADER: os.environ.get(EDGE_SECRET_ENV, ""),
    }
