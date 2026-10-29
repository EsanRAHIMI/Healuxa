"""Staff-only verification queues (provider.openapi.yaml v3.5 `admin` tag).

Read-only, permission-gated, tenant-scoped and cursor-paginated (oldest first, so queues are FIFO).
Decisions still go through the existing review / status endpoints.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from provider_service.api.deps import get_db, require_permission
from provider_service.domain import schemas
from provider_service.domain.facilities import facility_schema
from provider_service.domain.pagination import decode_cursor, encode_cursor
from provider_service.domain.providers import credential_schema, to_schema
from provider_service.infra.models import Credential, Facility, Provider

router = APIRouter(prefix="/v1/admin", tags=["admin"])

Db = Annotated[AsyncSession, Depends(get_db)]
ProviderVerifier = Annotated[Principal, Depends(require_permission("providers:verify"))]
FacilityVerifier = Annotated[Principal, Depends(require_permission("facilities:verify"))]
Limit = Annotated[int, Query(ge=1, le=100)]


def _page(model, stmt, cursor: str | None, limit: int):
    if cursor:
        created_at, last_id = decode_cursor(cursor)
        stmt = stmt.where(or_(model.created_at > created_at, and_(model.created_at == created_at, model.id > last_id)))
    return stmt.order_by(model.created_at, model.id).limit(limit + 1)


def _split(rows: list, limit: int) -> tuple[list, str | None, bool]:
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more else None
    return rows, next_cursor, has_more


@router.get("/providers")
async def list_admin_providers(
    db: Db,
    principal: ProviderVerifier,
    status: schemas.ProviderStatus | None = None,
    verification_status: schemas.VerificationStatus | None = None,
    limit: Limit = 20,
    cursor: str | None = None,
) -> dict:
    stmt = select(Provider).where(Provider.tenant_id == principal.tenant_id)
    if status:
        stmt = stmt.where(Provider.status == status)
    if verification_status:
        stmt = stmt.where(Provider.verification_status == verification_status)
    rows, next_cursor, has_more = _split(list((await db.scalars(_page(Provider, stmt, cursor, limit))).all()), limit)
    return {
        "data": [(await to_schema(db, p, private=True)).model_dump(mode="json") for p in rows],
        "page": {"next_cursor": next_cursor, "limit": limit, "has_more": has_more},
    }


@router.get("/credentials")
async def list_admin_credentials(
    db: Db,
    principal: ProviderVerifier,
    status: Literal["submitted", "verified", "rejected"] | None = "submitted",
    provider_id: str | None = Query(default=None, max_length=36),
    limit: Limit = 20,
    cursor: str | None = None,
) -> dict:
    stmt = select(Credential).where(Credential.tenant_id == principal.tenant_id)
    if status:
        stmt = stmt.where(Credential.status == status)
    if provider_id:
        stmt = stmt.where(Credential.provider_id == provider_id)
    rows, next_cursor, has_more = _split(list((await db.scalars(_page(Credential, stmt, cursor, limit))).all()), limit)
    return {
        "data": [
            {**credential_schema(c).model_dump(mode="json"), "submitted_at": c.created_at.isoformat()} for c in rows
        ],
        "page": {"next_cursor": next_cursor, "limit": limit, "has_more": has_more},
    }


@router.get("/facilities")
async def list_admin_facilities(
    db: Db,
    principal: FacilityVerifier,
    status: schemas.ProviderStatus | None = None,
    verification_status: schemas.VerificationStatus | None = None,
    limit: Limit = 20,
    cursor: str | None = None,
) -> dict:
    stmt = select(Facility).where(Facility.tenant_id == principal.tenant_id)
    if status:
        stmt = stmt.where(Facility.status == status)
    if verification_status:
        stmt = stmt.where(Facility.verification_status == verification_status)
    rows, next_cursor, has_more = _split(list((await db.scalars(_page(Facility, stmt, cursor, limit))).all()), limit)
    return {
        "data": [facility_schema(f, private=True).model_dump(mode="json") for f in rows],
        "page": {"next_cursor": next_cursor, "limit": limit, "has_more": has_more},
    }
