from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from fastapi import Depends, Request
from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import EDGE_SECRET_ENV, EDGE_SECRET_HEADER, Principal, get_principal

from ai_orchestrator.config import settings

CHAT_PERMISSION = "ai:chat"


@dataclass(frozen=True, slots=True)
class Caller:
    principal: Principal
    # The caller's own bearer token, forwarded to platform services so tools run with the caller's
    # permissions and ownership. None when the edge authenticated the request without one.
    token: str | None


def _unauthorized() -> ApiError:
    return ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Missing or invalid token")


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


async def resolve_caller(request: Request, edge_principal: Principal | None = Depends(get_principal)) -> Caller:
    token = _bearer(request)
    if edge_principal is not None:
        return Caller(principal=edge_principal, token=token)
    if not token:
        raise _unauthorized()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                settings.identity_introspect_url,
                json={"token": token},
                headers={
                    "X-Service-Client-Id": settings.service_auth_client_id or "",
                    "X-Service-Client-Secret": settings.service_auth_client_secret or "",
                },
            )
    except httpx.HTTPError:
        raise ApiError(status=503, code="service_unavailable", title="Service unavailable", detail="Identity introspection unavailable") from None
    if response.status_code != 200:
        raise _unauthorized()
    body = response.json()
    if not body.get("active") or not body.get("sub"):
        raise _unauthorized()
    return Caller(
        principal=Principal(
            user_id=body["sub"],
            tenant_id=body.get("tenant") or settings.tenant_default,
            roles=tuple(body.get("roles") or []),
            permissions=tuple(body.get("perms") or []),
            session_id=body.get("session_id"),
        ),
        token=token,
    )


async def require_chat(caller: Caller = Depends(resolve_caller)) -> Caller:
    if CHAT_PERMISSION not in caller.principal.permissions:
        raise ApiError(status=403, code="forbidden", title="Forbidden", detail=f"Missing permission: {CHAT_PERMISSION}")
    return caller


def principal_headers(user_id: str, *, permissions: str = CHAT_PERMISSION, tenant_id: str | None = None) -> dict[str, str]:
    """Test/dev helper: emulates the edge, which must prove itself with the shared secret."""
    return {
        "X-Healuxa-User": user_id,
        "X-Healuxa-Tenant": tenant_id or settings.tenant_default,
        "X-Healuxa-Perms": permissions,
        EDGE_SECRET_HEADER: os.environ.get(EDGE_SECRET_ENV, ""),
    }
