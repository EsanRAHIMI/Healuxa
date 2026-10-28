"""Service catalog: bookable offerings with a transparent professional + facility fee breakdown."""

from __future__ import annotations

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from provider_service.config import settings
from provider_service.domain import schemas
from provider_service.domain.access import forbidden, is_provider_staff, not_found, owns_provider, unprocessable
from provider_service.domain.affiliations import active_affiliation, can_manage_practice
from provider_service.domain.facilities import get_branch
from provider_service.domain.pagination import decode_cursor, encode_cursor
from provider_service.domain.providers import get_provider, utcnow
from provider_service.infra.models import Affiliation, Facility, Provider, ServiceOffering

MANAGERS = ("facility_admin",)


def _money(amount: int | None, currency: str) -> schemas.Money | None:
    return None if amount is None else schemas.Money(amount_minor=amount, currency=currency)


def offering_schema(offering: ServiceOffering) -> schemas.ServiceOffering:
    total = None
    if offering.price_type != "on_request":
        total = (offering.professional_fee_minor or 0) + (offering.facility_fee_minor or 0)
    return schemas.ServiceOffering(
        id=offering.id,
        provider_id=offering.provider_id,
        facility_id=offering.facility_id,
        branch_id=offering.branch_id,
        category=offering.category,
        name=offering.name,
        description=offering.description or {},
        duration_minutes=offering.duration_minutes,
        buffer_minutes=offering.buffer_minutes,
        mode=offering.mode,
        price_type=offering.price_type,
        price=_money(total, offering.currency),
        professional_fee=_money(offering.professional_fee_minor, offering.currency),
        facility_fee=_money(offering.facility_fee_minor, offering.currency),
        status=offering.status,
    )


def _bookable(stmt):
    """Restrict to offerings a customer may book: active offering, provider, facility and affiliation."""
    return (
        stmt.join(Provider, Provider.id == ServiceOffering.provider_id)
        .join(Facility, Facility.id == ServiceOffering.facility_id)
        .join(
            Affiliation,
            and_(
                Affiliation.provider_id == ServiceOffering.provider_id,
                Affiliation.branch_id == ServiceOffering.branch_id,
                Affiliation.status == "active",
            ),
        )
        .where(
            ServiceOffering.status == "active",
            Provider.status == "active",
            Provider.verification_status == "verified",
            Facility.status == "active",
            Facility.verification_status == "verified",
        )
    )


class CatalogService:
    async def create(
        self, db: AsyncSession, principal: Principal, provider_id: str, body: schemas.ServiceOfferingInput
    ) -> schemas.ServiceOffering:
        provider = await get_provider(db, principal.tenant_id, provider_id)
        branch = await get_branch(db, principal.tenant_id, body.branch_id)
        if not await can_manage_practice(db, principal, provider, branch.facility_id, MANAGERS):
            raise forbidden("Only the provider or the facility's admin can add offerings")
        if await active_affiliation(db, provider, branch.id) is None:
            raise unprocessable("Provider has no active affiliation at this branch", "branch_id")
        if body.currency not in settings.supported_currencies:
            raise unprocessable(f"Currency {body.currency} is not supported", "currency")
        is_priced = body.price_type != "on_request"
        offering = ServiceOffering(
            id=str(ULID()),
            tenant_id=principal.tenant_id,
            provider_id=provider.id,
            facility_id=branch.facility_id,
            branch_id=branch.id,
            category=body.category.strip().lower(),
            name=body.name.strip(),
            description=body.description or {},
            duration_minutes=body.duration_minutes,
            buffer_minutes=body.buffer_minutes,
            mode=body.mode,
            price_type=body.price_type,
            professional_fee_minor=body.professional_fee_minor if is_priced else None,
            facility_fee_minor=(body.facility_fee_minor or 0) if is_priced else None,
            currency=body.currency,
            status="active",
        )
        db.add(offering)
        await db.commit()
        await db.refresh(offering)
        return offering_schema(offering)

    async def update(
        self, db: AsyncSession, principal: Principal, offering_id: str, body: schemas.ServiceOfferingPatch
    ) -> schemas.ServiceOffering:
        offering = await db.scalar(
            select(ServiceOffering)
            .where(ServiceOffering.id == offering_id, ServiceOffering.tenant_id == principal.tenant_id)
            .with_for_update()
        )
        if offering is None:
            raise not_found("Service offering")
        provider = await get_provider(db, principal.tenant_id, offering.provider_id)
        if not await can_manage_practice(db, principal, provider, offering.facility_id, MANAGERS):
            raise not_found("Service offering")
        changes = body.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(offering, field, value if field != "description" else (value or {}))
        if offering.price_type == "on_request":
            offering.professional_fee_minor = None
            offering.facility_fee_minor = None
        else:
            if offering.professional_fee_minor is None:
                raise unprocessable("professional_fee_minor is required for fixed and from prices", "professional_fee_minor")
            offering.facility_fee_minor = offering.facility_fee_minor or 0
        offering.updated_at = utcnow()
        await db.commit()
        await db.refresh(offering)
        return offering_schema(offering)

    async def get(self, db: AsyncSession, principal: Principal | None, tenant_id: str, offering_id: str) -> schemas.ServiceOffering:
        public = await db.scalar(_bookable(select(ServiceOffering)).where(ServiceOffering.id == offering_id, ServiceOffering.tenant_id == tenant_id))
        if public is not None:
            return offering_schema(public)
        offering = await db.scalar(
            select(ServiceOffering).where(ServiceOffering.id == offering_id, ServiceOffering.tenant_id == tenant_id)
        )
        if offering is not None and principal is not None:
            provider = await get_provider(db, tenant_id, offering.provider_id)
            if owns_provider(principal, provider) or is_provider_staff(principal) or await can_manage_practice(
                db, principal, provider, offering.facility_id, MANAGERS
            ):
                return offering_schema(offering)
        raise not_found("Service offering")

    async def search(
        self,
        db: AsyncSession,
        tenant_id: str,
        *,
        category: str | None,
        provider_id: str | None,
        facility_id: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[schemas.ServiceOffering], str | None, bool]:
        stmt = _bookable(select(ServiceOffering)).where(ServiceOffering.tenant_id == tenant_id)
        if category:
            stmt = stmt.where(ServiceOffering.category == category.strip().lower())
        if provider_id:
            stmt = stmt.where(ServiceOffering.provider_id == provider_id)
        if facility_id:
            stmt = stmt.where(ServiceOffering.facility_id == facility_id)
        if cursor:
            created_at, last_id = decode_cursor(cursor)
            stmt = stmt.where(
                or_(
                    ServiceOffering.created_at > created_at,
                    and_(ServiceOffering.created_at == created_at, ServiceOffering.id > last_id),
                )
            )
        rows = list(
            (await db.scalars(stmt.order_by(ServiceOffering.created_at, ServiceOffering.id).limit(limit + 1))).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more else None
        return [offering_schema(o) for o in rows], next_cursor, has_more


catalog_service = CatalogService()
