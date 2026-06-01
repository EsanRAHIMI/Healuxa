from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal
from identity_service.api.deps import get_current_principal, get_db
from identity_service.config import settings
from identity_service.domain.idempotency import validate_idempotency_key
from identity_service.domain.iam_service import iam_service
from identity_service.domain.schemas import RoleRequest, RoleResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/v1/iam", tags=["iam"])


def _require_permission(principal: Principal, permission: str) -> None:
    if permission not in principal.permissions:
        raise ApiError(status=403, code="forbidden", title="Forbidden", detail=f"Missing permission: {permission}")


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[RoleResponse]:
    _require_permission(principal, "iam:read")
    return await iam_service.list_roles(db, tenant_id=principal.tenant_id)


@router.post("/roles", status_code=status.HTTP_201_CREATED, response_model=RoleResponse)
async def create_role(
    body: RoleRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RoleResponse:
    validate_idempotency_key(idempotency_key)
    _require_permission(principal, "iam:write")
    if body.tenant_id is None:
        body.tenant_id = principal.tenant_id
    return await iam_service.create_role(db, body, idempotency_key=idempotency_key)
