from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from healuxa_py_common.errors import error_response
from healuxa_py_common.observability.tracing import get_trace_id

logger = logging.getLogger(__name__)

# Identity headers are only trusted when the edge (Traefik ForwardAuth / mesh) proves it set them by
# sending this shared secret. Without HEALUXA_EDGE_SECRET configured, injected headers are ignored and
# services authenticate the bearer token themselves — never trust identity claims from a client.
EDGE_SECRET_ENV = "HEALUXA_EDGE_SECRET"
EDGE_SECRET_HEADER = "X-Healuxa-Edge-Secret"


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    session_id: str | None = None


def _split_header(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def edge_secret_valid(presented: str | None) -> bool:
    expected = os.environ.get(EDGE_SECRET_ENV)
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented.encode(), expected.encode())


def get_principal(
    request: Request,
    x_healuxa_user: Annotated[str | None, Header(alias="X-Healuxa-User")] = None,
    x_healuxa_tenant: Annotated[str | None, Header(alias="X-Healuxa-Tenant")] = None,
    x_healuxa_roles: Annotated[str | None, Header(alias="X-Healuxa-Roles")] = None,
    x_healuxa_perms: Annotated[str | None, Header(alias="X-Healuxa-Perms")] = None,
    x_healuxa_session: Annotated[str | None, Header(alias="X-Healuxa-Session")] = None,
    x_healuxa_edge_secret: Annotated[str | None, Header(alias=EDGE_SECRET_HEADER)] = None,
) -> Principal | None:
    if not x_healuxa_user:
        return None
    if not edge_secret_valid(x_healuxa_edge_secret):
        logger.warning(
            "ignored untrusted identity headers from %s",
            request.client.host if request.client else "unknown",
        )
        return None
    return Principal(
        user_id=x_healuxa_user,
        tenant_id=x_healuxa_tenant or "healuxa-dubai",
        roles=_split_header(x_healuxa_roles),
        permissions=_split_header(x_healuxa_perms),
        session_id=x_healuxa_session,
    )


def require_principal(
    principal: Principal | None = Depends(get_principal),
) -> Principal:
    if principal is None:
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
    return principal


def require_permission(permission: str):
    def _dependency(principal: Principal = Depends(require_principal)) -> Principal:
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
