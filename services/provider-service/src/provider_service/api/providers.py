from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy.ext.asyncio import AsyncSession

from provider_service.api.deps import get_db, optional_principal, require_permission
from provider_service.config import settings
from provider_service.domain import schemas
from provider_service.domain.access import unprocessable
from provider_service.domain.affiliations import affiliation_service
from provider_service.domain.availability import availability_service
from provider_service.domain.catalog import catalog_service
from provider_service.domain.providers import provider_service

router = APIRouter(prefix="/v1/providers", tags=["providers"])

Db = Annotated[AsyncSession, Depends(get_db)]
Onboarder = Annotated[Principal, Depends(require_permission("providers:onboard"))]
Verifier = Annotated[Principal, Depends(require_permission("providers:verify"))]
MaybePrincipal = Annotated[Principal | None, Depends(optional_principal)]


def _tenant(principal: Principal | None) -> str:
    return principal.tenant_id if principal else settings.public_tenant


def _parse_near(near: str | None) -> tuple[float, float] | None:
    if not near:
        return None
    try:
        lat, lng = (float(part) for part in near.split(","))
    except ValueError as exc:
        raise unprocessable("near must be 'lat,lng'", "near") from exc
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise unprocessable("near is out of range", "near")
    return lat, lng


@router.get("")
async def search_providers(
    db: Db,
    principal: MaybePrincipal,
    type: schemas.ProviderType | None = None,
    specialty: str | None = Query(default=None, max_length=80),
    language: str | None = Query(default=None, max_length=16),
    city: str | None = Query(default=None, max_length=100),
    near: str | None = None,
    radius_km: float | None = Query(default=None, gt=0, le=200),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> dict:
    data, next_cursor, has_more = await provider_service.search(
        db,
        _tenant(principal),
        type_=type,
        specialty=specialty,
        language=language,
        city=city,
        near=_parse_near(near),
        radius_km=radius_km,
        limit=limit,
        cursor=cursor,
    )
    return {
        "data": [p.model_dump(mode="json", exclude_none=False) for p in data],
        "page": {"next_cursor": next_cursor, "limit": limit, "has_more": has_more},
    }


@router.post("", status_code=201)
async def create_provider(
    db: Db,
    principal: Onboarder,
    body: schemas.ProviderInput,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> schemas.Provider:
    # An Idempotency-Key replay returns the original resource with the same 201 response.
    provider, _ = await provider_service.create(db, principal, body, idempotency_key=idempotency_key)
    response.headers["Location"] = f"/v1/providers/{provider.id}"
    response.headers["ETag"] = f'"v{provider.version}"'
    return provider


@router.get("/me")
async def get_my_provider(db: Db, principal: Onboarder) -> schemas.Provider:
    return await provider_service.get_mine(db, principal)


@router.get("/{provider_id}")
async def get_provider(db: Db, principal: MaybePrincipal, provider_id: str, response: Response) -> schemas.Provider:
    provider = await provider_service.get(db, principal, _tenant(principal), provider_id)
    response.headers["ETag"] = f'"v{provider.version}"'
    return provider


@router.patch("/{provider_id}")
async def update_provider(
    db: Db,
    principal: Onboarder,
    provider_id: str,
    body: schemas.ProviderPatch,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> schemas.Provider:
    provider = await provider_service.update(db, principal, provider_id, body, if_match=if_match)
    response.headers["ETag"] = f'"v{provider.version}"'
    return provider


@router.post("/{provider_id}/status")
async def change_provider_status(
    db: Db, principal: Verifier, provider_id: str, body: schemas.StatusChange
) -> schemas.Provider:
    return await provider_service.change_status(db, principal, provider_id, body)


@router.get("/{provider_id}/credentials")
async def list_credentials(db: Db, principal: Onboarder, provider_id: str) -> dict:
    return {"data": await provider_service.list_credentials(db, principal, provider_id)}


@router.post("/{provider_id}/credentials", status_code=201)
async def submit_credential(
    db: Db, principal: Onboarder, provider_id: str, body: schemas.CredentialInput
) -> schemas.Credential:
    return await provider_service.submit_credential(db, principal, provider_id, body)


@router.post("/{provider_id}/credentials/{credential_id}/review")
async def review_credential(
    db: Db, principal: Verifier, provider_id: str, credential_id: str, body: schemas.ReviewDecision
) -> schemas.Credential:
    return await provider_service.review_credential(db, principal, provider_id, credential_id, body)


@router.get("/{provider_id}/affiliations")
async def list_provider_affiliations(db: Db, principal: Onboarder, provider_id: str) -> dict:
    return {"data": await affiliation_service.for_provider(db, principal, provider_id)}


@router.post("/{provider_id}/services", status_code=201)
async def create_service_offering(
    db: Db, principal: Onboarder, provider_id: str, body: schemas.ServiceOfferingInput
) -> schemas.ServiceOffering:
    return await catalog_service.create(db, principal, provider_id, body)


@router.get("/{provider_id}/availability-rules")
async def list_availability_rules(db: Db, principal: Onboarder, provider_id: str) -> dict:
    return {"data": await availability_service.list_rules(db, principal, provider_id)}


@router.post("/{provider_id}/availability-rules", status_code=201)
async def create_availability_rule(
    db: Db, principal: Onboarder, provider_id: str, body: schemas.AvailabilityRuleInput
) -> schemas.AvailabilityRule:
    return await availability_service.create_rule(db, principal, provider_id, body)


@router.get("/{provider_id}/availability-exceptions")
async def list_availability_exceptions(
    db: Db,
    principal: Onboarder,
    provider_id: str,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> dict:
    return {"data": await availability_service.list_exceptions(db, principal, provider_id, from_=from_, to=to)}


@router.post("/{provider_id}/availability-exceptions", status_code=201)
async def create_availability_exception(
    db: Db, principal: Onboarder, provider_id: str, body: schemas.AvailabilityExceptionInput
) -> schemas.AvailabilityException:
    return await availability_service.create_exception(db, principal, provider_id, body)
