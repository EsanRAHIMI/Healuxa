from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy.ext.asyncio import AsyncSession

from provider_service.api.deps import get_db, optional_principal, require_permission
from provider_service.config import settings
from provider_service.domain import schemas
from provider_service.domain.affiliations import affiliation_service
from provider_service.domain.facilities import facility_service

router = APIRouter(tags=["facilities"])

Db = Annotated[AsyncSession, Depends(get_db)]
Onboarder = Annotated[Principal, Depends(require_permission("facilities:onboard"))]
Verifier = Annotated[Principal, Depends(require_permission("facilities:verify"))]
MaybePrincipal = Annotated[Principal | None, Depends(optional_principal)]


def _tenant(principal: Principal | None) -> str:
    return principal.tenant_id if principal else settings.public_tenant


@router.get("/v1/facilities")
async def search_facilities(
    db: Db,
    principal: MaybePrincipal,
    type: schemas.FacilityType | None = None,
    city: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> dict:
    data, next_cursor, has_more = await facility_service.search(
        db, _tenant(principal), type_=type, city=city, limit=limit, cursor=cursor
    )
    return {
        "data": [f.model_dump(mode="json") for f in data],
        "page": {"next_cursor": next_cursor, "limit": limit, "has_more": has_more},
    }


@router.post("/v1/facilities", status_code=201)
async def create_facility(
    db: Db,
    principal: Onboarder,
    body: schemas.FacilityInput,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> schemas.Facility:
    facility, _ = await facility_service.create(db, principal, body, idempotency_key=idempotency_key)
    response.headers["Location"] = f"/v1/facilities/{facility.id}"
    return facility


@router.get("/v1/facilities/{facility_id}")
async def get_facility(db: Db, principal: MaybePrincipal, facility_id: str) -> schemas.Facility:
    return await facility_service.get(db, principal, _tenant(principal), facility_id)


@router.patch("/v1/facilities/{facility_id}")
async def update_facility(db: Db, principal: Onboarder, facility_id: str, body: schemas.FacilityPatch) -> schemas.Facility:
    return await facility_service.update(db, principal, facility_id, body)


@router.post("/v1/facilities/{facility_id}/review")
async def review_facility(db: Db, principal: Verifier, facility_id: str, body: schemas.ReviewDecision) -> schemas.Facility:
    return await facility_service.review(db, principal, facility_id, body)


@router.get("/v1/facilities/{facility_id}/branches")
async def list_branches(db: Db, principal: MaybePrincipal, facility_id: str) -> dict:
    return {"data": await facility_service.list_branches(db, principal, _tenant(principal), facility_id)}


@router.post("/v1/facilities/{facility_id}/branches", status_code=201)
async def create_branch(db: Db, principal: Onboarder, facility_id: str, body: schemas.BranchInput) -> schemas.Branch:
    return await facility_service.create_branch(db, principal, facility_id, body)


@router.get("/v1/branches/{branch_id}/operating-hours")
async def get_operating_hours(db: Db, principal: MaybePrincipal, branch_id: str) -> schemas.OperatingHours:
    return await facility_service.get_hours(db, principal, _tenant(principal), branch_id)


@router.put("/v1/branches/{branch_id}/operating-hours")
async def replace_operating_hours(
    db: Db, principal: Onboarder, branch_id: str, body: schemas.OperatingHoursInput
) -> schemas.OperatingHours:
    return await facility_service.replace_hours(db, principal, branch_id, body)


@router.get("/v1/facilities/{facility_id}/staff")
async def list_facility_staff(db: Db, principal: Onboarder, facility_id: str) -> dict:
    return {"data": await facility_service.list_staff(db, principal, facility_id)}


@router.post("/v1/facilities/{facility_id}/staff", status_code=201)
async def add_facility_staff(
    db: Db, principal: Onboarder, facility_id: str, body: schemas.StaffMemberInput
) -> schemas.StaffMember:
    return await facility_service.add_staff(db, principal, facility_id, body)


@router.delete("/v1/facilities/{facility_id}/staff/{user_id}", status_code=204)
async def remove_facility_staff(db: Db, principal: Onboarder, facility_id: str, user_id: str) -> Response:
    await facility_service.remove_staff(db, principal, facility_id, user_id)
    return Response(status_code=204)


@router.get("/v1/facilities/{facility_id}/affiliations")
async def list_facility_affiliations(db: Db, principal: Onboarder, facility_id: str) -> dict:
    return {"data": await affiliation_service.for_facility(db, principal, facility_id)}
