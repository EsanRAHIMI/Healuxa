"""Provider–facility affiliations: a two-sided handshake between verified parties."""

from __future__ import annotations

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from provider_service.domain import schemas
from provider_service.domain.access import (
    actor_of,
    conflict,
    facility_role,
    forbidden,
    is_facility_staff,
    is_provider_staff,
    not_found,
    owns_provider,
    unprocessable,
)
from provider_service.domain.facilities import get_branch, get_facility
from provider_service.domain.providers import get_manageable_provider, get_provider, utcnow
from provider_service.events.publisher import event_publisher
from provider_service.infra.models import Affiliation, Facility, Provider

ADMIN = "facility_admin"


def affiliation_schema(affiliation: Affiliation) -> schemas.Affiliation:
    return schemas.Affiliation(
        id=affiliation.id,
        provider_id=affiliation.provider_id,
        facility_id=affiliation.facility_id,
        branch_id=affiliation.branch_id,
        status=affiliation.status,
        initiated_by=affiliation.initiated_by,
        decided_at=affiliation.decided_at,
        created_at=affiliation.created_at,
    )


async def _stage(db: AsyncSession, affiliation: Affiliation, principal: Principal) -> None:
    await event_publisher.publish(
        db=db,
        event_type="catalog.affiliation_changed",
        tenant_id=affiliation.tenant_id,
        payload={
            "affiliation_id": affiliation.id,
            "provider_id": affiliation.provider_id,
            "facility_id": affiliation.facility_id,
            "branch_id": affiliation.branch_id,
            "status": affiliation.status,
            "changed_at": utcnow().isoformat(),
        },
        actor=actor_of(principal),
    )


async def _is_facility_admin(db: AsyncSession, principal: Principal, facility_id: str) -> bool:
    return await facility_role(db, principal, facility_id) == ADMIN


class AffiliationService:
    async def request(self, db: AsyncSession, principal: Principal, body: schemas.AffiliationInput) -> schemas.Affiliation:
        provider = await get_provider(db, principal.tenant_id, body.provider_id)
        branch = await get_branch(db, principal.tenant_id, body.branch_id)
        if branch.status != "active":
            raise unprocessable("Branch is not accepting affiliations", "branch_id")
        if owns_provider(principal, provider):
            initiated_by = "provider"
        elif await _is_facility_admin(db, principal, branch.facility_id):
            initiated_by = "facility"
        else:
            raise forbidden("Only the provider or the facility's admin can request an affiliation")
        if provider.status == "offboarded":
            raise unprocessable("Provider is offboarded", "provider_id")
        affiliation = Affiliation(
            id=str(ULID()),
            tenant_id=principal.tenant_id,
            provider_id=provider.id,
            facility_id=branch.facility_id,
            branch_id=branch.id,
            status="pending",
            initiated_by=initiated_by,
        )
        db.add(affiliation)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise conflict("An open affiliation already exists for this provider and branch") from exc
        await _stage(db, affiliation, principal)
        await db.commit()
        await db.refresh(affiliation)
        return affiliation_schema(affiliation)

    async def decide(
        self, db: AsyncSession, principal: Principal, affiliation_id: str, body: schemas.AffiliationDecision
    ) -> schemas.Affiliation:
        affiliation = await db.scalar(
            select(Affiliation)
            .where(Affiliation.id == affiliation_id, Affiliation.tenant_id == principal.tenant_id)
            .with_for_update()
        )
        if affiliation is None:
            raise not_found("Affiliation")
        provider = await get_provider(db, principal.tenant_id, affiliation.provider_id)
        is_provider_side = owns_provider(principal, provider)
        is_facility_side = await _is_facility_admin(db, principal, affiliation.facility_id)
        is_platform = is_provider_staff(principal) or is_facility_staff(principal)
        if not (is_provider_side or is_facility_side or is_platform):
            raise not_found("Affiliation")

        if body.decision == "end":
            if affiliation.status != "active":
                raise conflict("Only an active affiliation can be ended")
            affiliation.status = "ended"
        else:
            if affiliation.status != "pending":
                raise conflict(f"Affiliation is already {affiliation.status}")
            counterparty = is_facility_side if affiliation.initiated_by == "provider" else is_provider_side
            if not counterparty:
                raise forbidden("Only the other party can approve or decline this affiliation")
            if body.decision == "approve":
                facility: Facility = await get_facility(db, principal.tenant_id, affiliation.facility_id)
                if provider.verification_status != "verified":
                    raise unprocessable("Provider must be verified before an affiliation becomes active")
                if facility.verification_status != "verified":
                    raise unprocessable("Facility must be verified before an affiliation becomes active")
                affiliation.status = "active"
            else:
                affiliation.status = "declined"
        affiliation.decided_by = principal.user_id
        affiliation.decided_at = utcnow()
        await _stage(db, affiliation, principal)
        await db.commit()
        await db.refresh(affiliation)
        return affiliation_schema(affiliation)

    async def for_provider(self, db: AsyncSession, principal: Principal, provider_id: str) -> list[schemas.Affiliation]:
        provider = await get_manageable_provider(db, principal, provider_id)
        rows = await db.scalars(select(Affiliation).where(Affiliation.provider_id == provider.id).order_by(Affiliation.created_at))
        return [affiliation_schema(a) for a in rows]

    async def for_facility(self, db: AsyncSession, principal: Principal, facility_id: str) -> list[schemas.Affiliation]:
        facility = await get_facility(db, principal.tenant_id, facility_id)
        if not (is_facility_staff(principal) or await facility_role(db, principal, facility.id) is not None):
            raise not_found("Facility")
        rows = await db.scalars(select(Affiliation).where(Affiliation.facility_id == facility.id).order_by(Affiliation.created_at))
        return [affiliation_schema(a) for a in rows]


async def active_affiliation(db: AsyncSession, provider: Provider, branch_id: str) -> Affiliation | None:
    return await db.scalar(
        select(Affiliation).where(
            Affiliation.provider_id == provider.id, Affiliation.branch_id == branch_id, Affiliation.status == "active"
        )
    )


async def can_manage_practice(db: AsyncSession, principal: Principal, provider: Provider, facility_id: str, roles: tuple[str, ...]) -> bool:
    """Owner of the provider, platform staff, or a facility member with ``roles`` where the provider practises."""
    if owns_provider(principal, provider) or is_provider_staff(principal):
        return True
    return await facility_role(db, principal, facility_id) in roles


affiliation_service = AffiliationService()
