from __future__ import annotations

from healuxa_py_common.errors import ApiError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from identity_service.config import settings
from identity_service.domain.schemas import RoleRequest, RoleResponse
from identity_service.infra.models import IdempotencyRecord, Role


class IamService:
    async def list_roles(self, db: AsyncSession, *, tenant_id: str) -> list[RoleResponse]:
        result = await db.execute(select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name))
        return [
            RoleResponse(name=role.name, permissions=list(role.permissions or []), tenant_id=role.tenant_id)
            for role in result.scalars()
        ]

    async def create_role(
        self,
        db: AsyncSession,
        body: RoleRequest,
        *,
        idempotency_key: str | None,
    ) -> RoleResponse:
        tenant_id = body.tenant_id or settings.tenant_default
        if idempotency_key:
            record = await db.get(IdempotencyRecord, idempotency_key)
            if record:
                return RoleResponse(**record.response_body)

        role = Role(
            id=str(ULID()),
            name=body.name,
            tenant_id=tenant_id,
            permissions=body.permissions,
        )
        db.add(role)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="Role already exists",
            ) from exc

        response = RoleResponse(name=role.name, permissions=list(role.permissions), tenant_id=role.tenant_id)
        if idempotency_key:
            db.add(
                IdempotencyRecord(
                    key=idempotency_key,
                    request_hash=role.name,
                    status_code=201,
                    response_body=response.model_dump(),
                )
            )
            await db.commit()
        return response


iam_service = IamService()
