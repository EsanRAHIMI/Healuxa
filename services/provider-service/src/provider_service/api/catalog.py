from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy.ext.asyncio import AsyncSession

from provider_service.api.deps import get_db, optional_principal, require_permission
from provider_service.config import settings
from provider_service.domain import schemas
from provider_service.domain.affiliations import affiliation_service
from provider_service.domain.availability import availability_service
from provider_service.domain.catalog import catalog_service

router = APIRouter(tags=["services", "affiliations", "availability"])

Db = Annotated[AsyncSession, Depends(get_db)]
Onboarder = Annotated[Principal, Depends(require_permission("providers:onboard"))]
MaybePrincipal = Annotated[Principal | None, Depends(optional_principal)]


@router.get("/v1/services")
async def list_services(
    db: Db,
    principal: MaybePrincipal,
    category: str | None = Query(default=None, max_length=80),
    provider_id: str | None = None,
    facility_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> dict:
    tenant = principal.tenant_id if principal else settings.public_tenant
    data, next_cursor, has_more = await catalog_service.search(
        db, tenant, category=category, provider_id=provider_id, facility_id=facility_id, limit=limit, cursor=cursor
    )
    return {
        "data": [o.model_dump(mode="json") for o in data],
        "page": {"next_cursor": next_cursor, "limit": limit, "has_more": has_more},
    }


@router.get("/v1/services/{service_id}")
async def get_service(db: Db, principal: MaybePrincipal, service_id: str) -> schemas.ServiceOffering:
    tenant = principal.tenant_id if principal else settings.public_tenant
    return await catalog_service.get(db, principal, tenant, service_id)


@router.patch("/v1/services/{service_id}")
async def update_service(
    db: Db, principal: Onboarder, service_id: str, body: schemas.ServiceOfferingPatch
) -> schemas.ServiceOffering:
    return await catalog_service.update(db, principal, service_id, body)


@router.post("/v1/affiliations", status_code=201)
async def request_affiliation(db: Db, principal: Onboarder, body: schemas.AffiliationInput) -> schemas.Affiliation:
    return await affiliation_service.request(db, principal, body)


@router.post("/v1/affiliations/{affiliation_id}/decision")
async def decide_affiliation(
    db: Db, principal: Onboarder, affiliation_id: str, body: schemas.AffiliationDecision
) -> schemas.Affiliation:
    return await affiliation_service.decide(db, principal, affiliation_id, body)


@router.delete("/v1/availability-rules/{rule_id}", status_code=204)
async def delete_availability_rule(db: Db, principal: Onboarder, rule_id: str) -> Response:
    await availability_service.delete_rule(db, principal, rule_id)
    return Response(status_code=204)
