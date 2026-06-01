from __future__ import annotations

from healuxa_py_common.errors import ApiError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from identity_service.config import settings
from identity_service.domain.idempotency import (
    hash_request_body,
    read_idempotent_response,
    store_idempotent_response,
)
from identity_service.domain.schemas import RoleRequest, RoleResponse
from identity_service.infra.models import Role


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
        body_payload = body.model_dump()
        body_hash = hash_request_body(body_payload)

        if idempotency_key:
            cached = await read_idempotent_response(db, idempotency_key, request_hash=body_hash)
            if cached:
                return RoleResponse(**cached)

        role = Role(
            id=str(ULID()),
            name=body.name,
            tenant_id=tenant_id,
            permissions=body.permissions,
        )
        db.add(role)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="Role already exists",
            ) from exc

        response = RoleResponse(name=role.name, permissions=list(role.permissions), tenant_id=role.tenant_id)
        response_payload = response.model_dump()

        await db.commit()

        if idempotency_key:
            await store_idempotent_response(
                db,
                idempotency_key,
                request_hash=body_hash,
                status_code=201,
                response_body=response_payload,
            )

        return response


iam_service = IamService()
