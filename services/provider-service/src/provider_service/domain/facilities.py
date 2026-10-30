"""Facilities (clinics, hospitals), branches, opening hours and facility staff roles."""

from __future__ import annotations

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, delete, func, or_, select
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
    not_found,
    require_facility_role,
)
from provider_service.domain.pagination import decode_cursor, encode_cursor
from provider_service.domain.providers import utcnow
from provider_service.domain.schemas import from_minutes, to_minutes
from provider_service.events.publisher import event_publisher
from provider_service.infra.models import Affiliation, Branch, Facility, FacilityStaff, OperatingHoursWindow

ADMIN = ("facility_admin",)


def is_public(facility: Facility) -> bool:
    return facility.status == "active" and facility.verification_status == "verified"


def facility_schema(facility: Facility, *, private: bool) -> schemas.Facility:
    return schemas.Facility(
        id=facility.id,
        type=facility.type,
        name=facility.name,
        description=facility.description or {},
        license_authority=facility.license_authority if private else None,
        license_number=facility.license_number if private else None,
        website=facility.website,
        phone=facility.phone,
        status=facility.status,
        verification_status=facility.verification_status,
        created_at=facility.created_at,
    )


def branch_schema(branch: Branch) -> schemas.Branch:
    return schemas.Branch(
        id=branch.id,
        facility_id=branch.facility_id,
        name=branch.name,
        address_line=branch.address_line,
        city=branch.city,
        emirate=branch.emirate,
        country=branch.country,
        timezone=branch.timezone,
        latitude=branch.latitude,
        longitude=branch.longitude,
        phone=branch.phone,
        status=branch.status,
    )


async def get_facility(db: AsyncSession, tenant_id: str, facility_id: str, *, for_update: bool = False) -> Facility:
    stmt = select(Facility).where(Facility.id == facility_id, Facility.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    facility = await db.scalar(stmt)
    if facility is None:
        raise not_found("Facility")
    return facility


async def get_branch(db: AsyncSession, tenant_id: str, branch_id: str) -> Branch:
    branch = await db.scalar(select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id))
    if branch is None:
        raise not_found("Branch")
    return branch


async def _visible_facility(db: AsyncSession, principal: Principal | None, tenant_id: str, facility_id: str) -> tuple[Facility, bool]:
    facility = await get_facility(db, tenant_id, facility_id)
    private = is_facility_staff(principal) or await facility_role(db, principal, facility.id) is not None
    if not private and not is_public(facility):
        raise not_found("Facility")
    return facility, private


async def _stage_facility_event(db: AsyncSession, facility: Facility, principal: Principal) -> None:
    await event_publisher.publish(
        db=db,
        event_type="catalog.facility_status_changed",
        tenant_id=facility.tenant_id,
        payload={
            "facility_id": facility.id,
            "status": facility.status,
            "verification_status": facility.verification_status,
            "changed_at": utcnow().isoformat(),
        },
        actor=actor_of(principal),
    )


async def _stage_staff_event(db: AsyncSession, facility: Facility, principal: Principal, *, user_id: str, role: str | None, change: str) -> None:
    """Membership change signal: keeps notification recipients for this facility current."""
    await event_publisher.publish(
        db=db,
        event_type="catalog.facility_staff_changed",
        tenant_id=facility.tenant_id,
        payload={"facility_id": facility.id, "user_id": user_id, "role": role, "change": change, "changed_at": utcnow().isoformat()},
        actor=actor_of(principal),
    )


class FacilityService:
    async def create(
        self, db: AsyncSession, principal: Principal, body: schemas.FacilityInput, *, idempotency_key: str | None
    ) -> tuple[schemas.Facility, bool]:
        if idempotency_key:
            existing = await db.scalar(
                select(Facility).where(
                    Facility.tenant_id == principal.tenant_id,
                    Facility.created_by == principal.user_id,
                    Facility.creation_key == idempotency_key,
                )
            )
            if existing is not None:
                return facility_schema(existing, private=True), False
        facility = Facility(
            id=str(ULID()),
            tenant_id=principal.tenant_id,
            type=body.type,
            name=body.name.strip(),
            description=body.description or {},
            license_authority=body.license_authority.strip().upper(),
            license_number=body.license_number.strip(),
            website=body.website,
            phone=body.phone,
            status="pending",
            verification_status="under_review",
            created_by=principal.user_id,
            creation_key=idempotency_key,
        )
        db.add(facility)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise conflict("A facility with this license is already registered") from exc
        db.add(FacilityStaff(facility_id=facility.id, user_id=principal.user_id, role="facility_admin"))
        await _stage_facility_event(db, facility, principal)
        await _stage_staff_event(db, facility, principal, user_id=principal.user_id, role="facility_admin", change="added")
        await db.commit()
        await db.refresh(facility)
        return facility_schema(facility, private=True), True

    async def mine(self, db: AsyncSession, principal: Principal) -> list[schemas.Facility]:
        """Facilities where the caller holds any staff role (facility portal home), newest first."""
        rows = await db.scalars(
            select(Facility)
            .join(FacilityStaff, FacilityStaff.facility_id == Facility.id)
            .where(Facility.tenant_id == principal.tenant_id, FacilityStaff.user_id == principal.user_id)
            .order_by(Facility.created_at.desc())
            .limit(200)
        )
        return [facility_schema(f, private=True) for f in rows]

    async def get(self, db: AsyncSession, principal: Principal | None, tenant_id: str, facility_id: str) -> schemas.Facility:
        facility, private = await _visible_facility(db, principal, tenant_id, facility_id)
        return facility_schema(facility, private=private)

    async def update(
        self, db: AsyncSession, principal: Principal, facility_id: str, body: schemas.FacilityPatch
    ) -> schemas.Facility:
        facility = await get_facility(db, principal.tenant_id, facility_id, for_update=True)
        await require_facility_role(db, principal, facility.id, ADMIN)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(facility, field, value if field != "description" else (value or {}))
        facility.updated_at = utcnow()
        await db.commit()
        await db.refresh(facility)
        return facility_schema(facility, private=True)

    async def review(
        self, db: AsyncSession, principal: Principal, facility_id: str, body: schemas.ReviewDecision
    ) -> schemas.Facility:
        if not is_facility_staff(principal):
            raise forbidden("Only platform staff can review facilities")
        facility = await get_facility(db, principal.tenant_id, facility_id, for_update=True)
        if facility.verification_status in ("verified", "rejected"):
            raise conflict(f"Facility was already {facility.verification_status}")
        if body.decision == "verify":
            facility.verification_status = "verified"
            facility.status = "active"
        else:
            facility.verification_status = "rejected"
        facility.review_note = body.note
        facility.updated_at = utcnow()
        await _stage_facility_event(db, facility, principal)
        await db.commit()
        await db.refresh(facility)
        return facility_schema(facility, private=True)

    async def search(
        self, db: AsyncSession, tenant_id: str, *, type_: str | None, city: str | None, limit: int, cursor: str | None
    ) -> tuple[list[schemas.Facility], str | None, bool]:
        stmt = select(Facility).where(
            Facility.tenant_id == tenant_id, Facility.status == "active", Facility.verification_status == "verified"
        )
        if type_:
            stmt = stmt.where(Facility.type == type_)
        if city:
            stmt = stmt.where(
                select(Branch.id)
                .where(Branch.facility_id == Facility.id, func.lower(Branch.city) == city.strip().lower())
                .exists()
            )
        if cursor:
            created_at, last_id = decode_cursor(cursor)
            stmt = stmt.where(
                or_(Facility.created_at > created_at, and_(Facility.created_at == created_at, Facility.id > last_id))
            )
        rows = list((await db.scalars(stmt.order_by(Facility.created_at, Facility.id).limit(limit + 1))).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more else None
        return [facility_schema(f, private=False) for f in rows], next_cursor, has_more

    # ── Branches & hours ────────────────────────────────────────────────────────────────────

    async def list_branches(self, db: AsyncSession, principal: Principal | None, tenant_id: str, facility_id: str) -> list[schemas.Branch]:
        facility, _ = await _visible_facility(db, principal, tenant_id, facility_id)
        rows = await db.scalars(select(Branch).where(Branch.facility_id == facility.id).order_by(Branch.created_at))
        return [branch_schema(b) for b in rows]

    async def create_branch(
        self, db: AsyncSession, principal: Principal, facility_id: str, body: schemas.BranchInput
    ) -> schemas.Branch:
        facility = await get_facility(db, principal.tenant_id, facility_id)
        await require_facility_role(db, principal, facility.id, ADMIN)
        branch = Branch(id=str(ULID()), tenant_id=facility.tenant_id, facility_id=facility.id, **body.model_dump())
        db.add(branch)
        await db.commit()
        await db.refresh(branch)
        return branch_schema(branch)

    async def get_hours(self, db: AsyncSession, principal: Principal | None, tenant_id: str, branch_id: str) -> schemas.OperatingHours:
        branch = await get_branch(db, tenant_id, branch_id)
        await _visible_facility(db, principal, tenant_id, branch.facility_id)
        return await self._hours(db, branch)

    async def _hours(self, db: AsyncSession, branch: Branch) -> schemas.OperatingHours:
        rows = await db.scalars(
            select(OperatingHoursWindow)
            .where(OperatingHoursWindow.branch_id == branch.id)
            .order_by(OperatingHoursWindow.weekday, OperatingHoursWindow.start_minute)
        )
        return schemas.OperatingHours(
            branch_id=branch.id,
            timezone=branch.timezone,
            windows=[
                schemas.TimeWindow(weekday=w.weekday, start=from_minutes(w.start_minute), end=from_minutes(w.end_minute))
                for w in rows
            ],
        )

    async def replace_hours(
        self, db: AsyncSession, principal: Principal, branch_id: str, body: schemas.OperatingHoursInput
    ) -> schemas.OperatingHours:
        branch = await get_branch(db, principal.tenant_id, branch_id)
        await require_facility_role(db, principal, branch.facility_id, ADMIN)
        await db.execute(delete(OperatingHoursWindow).where(OperatingHoursWindow.branch_id == branch.id))
        for window in body.windows:
            db.add(
                OperatingHoursWindow(
                    id=str(ULID()),
                    branch_id=branch.id,
                    weekday=window.weekday,
                    start_minute=to_minutes(window.start),
                    end_minute=to_minutes(window.end),
                )
            )
        # Provider rules are validated against these hours; dependants re-derive slots on this signal.
        provider_ids = (
            await db.scalars(
                select(Affiliation.provider_id).where(Affiliation.branch_id == branch.id, Affiliation.status == "active")
            )
        ).all()
        for provider_id in sorted(set(provider_ids)):
            await event_publisher.publish(
                db=db,
                event_type="catalog.availability_changed",
                tenant_id=branch.tenant_id,
                payload={
                    "provider_id": provider_id,
                    "branch_id": branch.id,
                    "change": "operating_hours_replaced",
                    "changed_at": utcnow().isoformat(),
                },
                actor=actor_of(principal),
            )
        await db.commit()
        return await self._hours(db, branch)

    # ── Staff ───────────────────────────────────────────────────────────────────────────────

    async def list_staff(self, db: AsyncSession, principal: Principal, facility_id: str) -> list[schemas.StaffMember]:
        facility = await get_facility(db, principal.tenant_id, facility_id)
        await require_facility_role(db, principal, facility.id, ADMIN)
        rows = await db.scalars(select(FacilityStaff).where(FacilityStaff.facility_id == facility.id).order_by(FacilityStaff.created_at))
        return [schemas.StaffMember(facility_id=s.facility_id, user_id=s.user_id, role=s.role, created_at=s.created_at) for s in rows]

    async def add_staff(
        self, db: AsyncSession, principal: Principal, facility_id: str, body: schemas.StaffMemberInput
    ) -> schemas.StaffMember:
        facility = await get_facility(db, principal.tenant_id, facility_id)
        await require_facility_role(db, principal, facility.id, ADMIN)
        member = FacilityStaff(facility_id=facility.id, user_id=body.user_id, role=body.role)
        db.add(member)
        try:
            await db.flush()
            await _stage_staff_event(db, facility, principal, user_id=body.user_id, role=body.role, change="added")
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise conflict("User already has a role at this facility") from exc
        await db.refresh(member)
        return schemas.StaffMember(facility_id=member.facility_id, user_id=member.user_id, role=member.role, created_at=member.created_at)

    async def remove_staff(self, db: AsyncSession, principal: Principal, facility_id: str, user_id: str) -> None:
        facility = await get_facility(db, principal.tenant_id, facility_id, for_update=True)
        await require_facility_role(db, principal, facility.id, ADMIN)
        member = await db.get(FacilityStaff, (facility.id, user_id))
        if member is None:
            raise not_found("Staff member")
        if member.role == "facility_admin":
            admins = await db.scalar(
                select(func.count()).select_from(FacilityStaff).where(
                    FacilityStaff.facility_id == facility.id, FacilityStaff.role == "facility_admin"
                )
            )
            if (admins or 0) <= 1:
                raise conflict("A facility must keep at least one facility_admin")
        await db.delete(member)
        await _stage_staff_event(db, facility, principal, user_id=user_id, role=member.role, change="removed")
        await db.commit()


facility_service = FacilityService()
