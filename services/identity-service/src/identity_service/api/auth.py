from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from healuxa_py_common.errors import ApiError
from identity_service.api.deps import (
    extract_bearer_token,
    get_client_ip,
    get_current_principal,
    get_db,
    get_redis_client,
    require_service_auth,
)
from identity_service.domain.auth_service import auth_service
from identity_service.domain.idempotency import validate_idempotency_key
from identity_service.domain.schemas import (
    IntrospectRequest,
    IntrospectionResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/v1/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def auth_register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    validate_idempotency_key(idempotency_key)
    tokens, location = await auth_service.register(
        db,
        redis,
        body,
        ip=get_client_ip(request),
        idempotency_key=idempotency_key,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=tokens.model_dump(),
        headers={"Location": location},
    )


@router.post("/login", response_model=TokenResponse)
async def auth_login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client),
) -> TokenResponse:
    return await auth_service.login(db, redis, body, ip=get_client_ip(request))


@router.post("/refresh", response_model=TokenResponse)
async def auth_refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client),
) -> TokenResponse:
    return await auth_service.refresh(db, redis, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def auth_logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Response:
    token = extract_bearer_token(request, credentials)
    if not token:
        raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Missing token")
    await auth_service.logout(db, redis, access_token=token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/introspect", response_model=IntrospectionResponse)
async def auth_introspect(
    body: IntrospectRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client),
    _: str = Depends(require_service_auth),
) -> IntrospectionResponse:
    return await auth_service.introspect(db, redis, body.token)


@router.post("/service-token", response_model=TokenResponse)
async def issue_service_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_service_auth),
) -> TokenResponse:
    client_id = request.headers.get("X-Service-Client-Id") or request.headers.get("X-Healuxa-Service-Client")
    client_secret = request.headers.get("X-Service-Client-Secret") or ""
    from identity_service.config import settings

    client_id = client_id or settings.service_auth_client_id
    return await auth_service.issue_service_token(db, client_id, client_secret or settings.service_auth_client_secret)
