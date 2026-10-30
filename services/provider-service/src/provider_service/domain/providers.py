"""Provider onboarding, credential verification and lifecycle."""

from __future__ import annotations

from datetime import UTC, date, datetime

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, any_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from provider_service.domain import schemas
from provider_service.domain.access import (
    actor_of,
    conflict,
    forbidden,
    is_provider_staff,
    not_found,
    owns_provider,
    unprocessable,
)
from provider_service.domain.pagination import decode_cursor, encode_cursor
from provider_service.events.publisher import event_publisher
from provider_service.infra.models import Affiliation, Branch, Credential, Provider

LICENSE = "professional_license"
# Fields that identify the practitioner publicly; changing them on a verified profile needs re-review.
IDENTITY_FIELDS = {"display_name", "title"}
# Allowed staff-driven status transitions. Activation has extra verification preconditions.
TRANSITIONS = {
    "pending": {"active", "offboarded"},
    "active": {"suspended", "offboarded"},
    "suspended": {"active", "offboarded"},
    "offboarded": set(),
}


def today() -> date:
    return datetime.now(UTC).date()


def utcnow() -> datetime:
    return datetime.now(UTC)


def _credential_valid_on(credential: Credential, on: date) -> bool:
    return credential.status == "verified" and (credential.valid_until is None or credential.valid_until >= on) and (
        credential.valid_from is None or credential.valid_from <= on
    )


def is_publicly_listed(provider: Provider) -> bool:
    return provider.status == "active" and provider.verification_status == "verified"


async def _credentials(db: AsyncSession, provider_id: str) -> list[Credential]:
    return list(
        (await db.scalars(select(Credential).where(Credential.provider_id == provider_id).order_by(Credential.created_at))).all()
    )


async def to_schema(db: AsyncSession, provider: Provider, *, private: bool) -> schemas.Provider:
    on = today()
    verified = [
        schemas.VerifiedCredentialSummary(kind=c.kind, issuing_authority=c.issuing_authority, valid_until=c.valid_until)
        for c in await _credentials(db, provider.id)
        if _credential_valid_on(c, on)
    ]
    return schemas.Provider(
        id=provider.id,
        type=provider.type,
        display_name=provider.display_name,
        title=provider.title,
        bio=provider.bio or {},
        specialties=list(provider.specialties),
        languages=list(provider.languages),
        quality_score=provider.quality_score,
        success_score=provider.success_score,
        status=provider.status,
        verification_status=provider.verification_status,
        verified_credentials=verified,
        user_id=provider.user_id if private else None,
        version=provider.version,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def credential_schema(credential: Credential) -> schemas.Credential:
    status = credential.status
    if status == "verified" and credential.valid_until is not None and credential.valid_until < today():
        status = "expired"
    return schemas.Credential(
        id=credential.id,
        provider_id=credential.provider_id,
        kind=credential.kind,
        issuing_authority=credential.issuing_authority,
        jurisdiction=credential.jurisdiction,
        number=credential.number,
        valid_from=credential.valid_from,
        valid_until=credential.valid_until,
        document_ref=credential.document_ref,
        status=status,
        review_note=credential.review_note,
        reviewed_at=credential.reviewed_at,
    )


async def get_provider(db: AsyncSession, tenant_id: str, provider_id: str, *, for_update: bool = False) -> Provider:
    stmt = select(Provider).where(Provider.id == provider_id, Provider.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    provider = await db.scalar(stmt)
    if provider is None:
        raise not_found("Provider")
    return provider


async def get_manageable_provider(
    db: AsyncSession, principal: Principal, provider_id: str, *, for_update: bool = False
) -> Provider:
    """Provider the caller may manage (owner or platform staff). Others get 404, never existence leaks."""
    provider = await get_provider(db, principal.tenant_id, provider_id, for_update=for_update)
    if not (owns_provider(principal, provider) or is_provider_staff(principal)):
        raise not_found("Provider")
    return provider


async def _stage_status_event(
    db: AsyncSession, provider: Provider, principal: Principal, *, previous: str | None, reason: str | None
) -> None:
    await event_publisher.publish(
        db=db,
        event_type="catalog.provider_status_changed",
        tenant_id=provider.tenant_id,
        payload={
            "provider_id": provider.id,
            # Owner id lets notification-service route provider notifications without a lookup.
            "owner_user_id": provider.user_id,
            "previous_status": previous,
            "status": provider.status,
            "verification_status": provider.verification_status,
            "reason": reason,
            "changed_at": utcnow().isoformat(),
        },
        actor=actor_of(principal),
    )


class ProviderService:
    async def create(
        self,
        db: AsyncSession,
        principal: Principal,
        body: schemas.ProviderInput,
        *,
        idempotency_key: str | None,
    ) -> tuple[schemas.Provider, bool]:
        """Returns (provider, created). A replay with the same Idempotency-Key returns the original."""
        existing = await db.scalar(
            select(Provider).where(Provider.tenant_id == principal.tenant_id, Provider.user_id == principal.user_id)
        )
        if existing is not None:
            if idempotency_key and existing.creation_key == idempotency_key:
                return await to_schema(db, existing, private=True), False
            raise conflict("This account already has a provider profile")
        provider = Provider(
            id=str(ULID()),
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            type=body.type,
            display_name=body.display_name.strip(),
            title=body.title,
            bio=body.bio or {},
            specialties=sorted({s.strip().lower() for s in body.specialties}),
            languages=sorted({lang.strip().lower() for lang in body.languages}),
            status="pending",
            verification_status="unverified",
            creation_key=idempotency_key,
        )
        db.add(provider)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise conflict("This account already has a provider profile") from exc
        await _stage_status_event(db, provider, principal, previous=None, reason="application_submitted")
        await db.commit()
        await db.refresh(provider)
        return await to_schema(db, provider, private=True), True

    async def get_mine(self, db: AsyncSession, principal: Principal) -> schemas.Provider:
        provider = await db.scalar(
            select(Provider).where(Provider.tenant_id == principal.tenant_id, Provider.user_id == principal.user_id)
        )
        if provider is None:
            raise not_found("Provider")
        return await to_schema(db, provider, private=True)

    async def get(self, db: AsyncSession, principal: Principal | None, tenant_id: str, provider_id: str) -> schemas.Provider:
        provider = await get_provider(db, tenant_id, provider_id)
        private = owns_provider(principal, provider) or is_provider_staff(principal)
        if not private and not is_publicly_listed(provider):
            raise not_found("Provider")
        return await to_schema(db, provider, private=private)

    async def update(
        self,
        db: AsyncSession,
        principal: Principal,
        provider_id: str,
        body: schemas.ProviderPatch,
        *,
        if_match: str | None,
    ) -> schemas.Provider:
        provider = await get_manageable_provider(db, principal, provider_id, for_update=True)
        if if_match is not None and if_match.strip('"') != f"v{provider.version}":
            raise conflict("If-Match does not match current provider version")
        changes = body.model_dump(exclude_unset=True)
        if not changes:
            return await to_schema(db, provider, private=True)
        for field, value in changes.items():
            if field == "specialties":
                value = sorted({s.strip().lower() for s in value})
            elif field == "languages":
                value = sorted({lang.strip().lower() for lang in value})
            elif field == "bio":
                value = value or {}
            setattr(provider, field, value)
        previous_status = provider.status
        if (
            IDENTITY_FIELDS & changes.keys()
            and provider.verification_status == "verified"
            and not is_provider_staff(principal)
        ):
            provider.verification_status = "under_review"
            await _stage_status_event(db, provider, principal, previous=previous_status, reason="identity_changed")
        provider.version += 1
        provider.updated_at = utcnow()
        await db.commit()
        await db.refresh(provider)
        return await to_schema(db, provider, private=True)

    async def change_status(
        self, db: AsyncSession, principal: Principal, provider_id: str, body: schemas.StatusChange
    ) -> schemas.Provider:
        if not is_provider_staff(principal):
            raise forbidden("Only platform staff can change provider status")
        provider = await get_provider(db, principal.tenant_id, provider_id, for_update=True)
        if body.status == provider.status:
            return await to_schema(db, provider, private=True)
        if body.status not in TRANSITIONS[provider.status]:
            raise unprocessable(f"Cannot move a {provider.status} provider to {body.status}", "status")
        if body.status == "active":
            if provider.verification_status != "verified":
                raise unprocessable("Provider must be verified before activation", "status")
            if not any(c.kind == LICENSE and _credential_valid_on(c, today()) for c in await _credentials(db, provider.id)):
                raise unprocessable("Provider has no verified, unexpired professional license", "status")
        previous = provider.status
        provider.status = body.status
        provider.version += 1
        provider.updated_at = utcnow()
        await _stage_status_event(db, provider, principal, previous=previous, reason=body.reason)
        await db.commit()
        await db.refresh(provider)
        return await to_schema(db, provider, private=True)

    async def search(
        self,
        db: AsyncSession,
        tenant_id: str,
        *,
        type_: str | None,
        specialty: str | None,
        language: str | None,
        city: str | None,
        near: tuple[float, float] | None,
        radius_km: float | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[schemas.Provider], str | None, bool]:
        stmt = select(Provider).where(
            Provider.tenant_id == tenant_id, Provider.status == "active", Provider.verification_status == "verified"
        )
        if type_:
            stmt = stmt.where(Provider.type == type_)
        if specialty:
            stmt = stmt.where(specialty.strip().lower() == any_(Provider.specialties))
        if language:
            stmt = stmt.where(language.strip().lower() == any_(Provider.languages))
        if city or near:
            branch_filter = [
                Affiliation.provider_id == Provider.id,
                Affiliation.status == "active",
                Branch.id == Affiliation.branch_id,
                Branch.status == "active",
            ]
            if city:
                branch_filter.append(func.lower(Branch.city) == city.strip().lower())
            if near:
                lat, lng = near
                # Haversine distance in km; branches without coordinates never match a geo search.
                distance = 6371 * func.acos(
                    func.least(
                        1.0,
                        func.cos(func.radians(lat))
                        * func.cos(func.radians(Branch.latitude))
                        * func.cos(func.radians(Branch.longitude) - func.radians(lng))
                        + func.sin(func.radians(lat)) * func.sin(func.radians(Branch.latitude)),
                    )
                )
                branch_filter.append(and_(Branch.latitude.is_not(None), distance <= (radius_km or 10.0)))
            stmt = stmt.where(exists().where(*branch_filter))
        if cursor:
            created_at, last_id = decode_cursor(cursor)
            stmt = stmt.where(
                or_(Provider.created_at > created_at, and_(Provider.created_at == created_at, Provider.id > last_id))
            )
        rows = list((await db.scalars(stmt.order_by(Provider.created_at, Provider.id).limit(limit + 1))).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more else None
        return [await to_schema(db, p, private=False) for p in rows], next_cursor, has_more

    # ── Credentials ─────────────────────────────────────────────────────────────────────────

    async def list_credentials(self, db: AsyncSession, principal: Principal, provider_id: str) -> list[schemas.Credential]:
        provider = await get_manageable_provider(db, principal, provider_id)
        return [credential_schema(c) for c in await _credentials(db, provider.id)]

    async def submit_credential(
        self, db: AsyncSession, principal: Principal, provider_id: str, body: schemas.CredentialInput
    ) -> schemas.Credential:
        provider = await get_manageable_provider(db, principal, provider_id, for_update=True)
        if provider.status == "offboarded":
            raise unprocessable("Offboarded providers cannot submit credentials")
        credential = Credential(
            id=str(ULID()),
            tenant_id=provider.tenant_id,
            provider_id=provider.id,
            kind=body.kind,
            issuing_authority=body.issuing_authority.strip().upper(),
            jurisdiction=body.jurisdiction,
            number=body.number.strip(),
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            document_ref=body.document_ref,
            status="submitted",
        )
        db.add(credential)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise conflict("This credential was already submitted") from exc
        if provider.verification_status in ("unverified", "rejected"):
            previous = provider.status
            provider.verification_status = "under_review"
            provider.updated_at = utcnow()
            await _stage_status_event(db, provider, principal, previous=previous, reason="credential_submitted")
        await db.commit()
        await db.refresh(credential)
        return credential_schema(credential)

    async def review_credential(
        self,
        db: AsyncSession,
        principal: Principal,
        provider_id: str,
        credential_id: str,
        body: schemas.ReviewDecision,
    ) -> schemas.Credential:
        if not is_provider_staff(principal):
            raise forbidden("Only platform staff can review credentials")
        provider = await get_provider(db, principal.tenant_id, provider_id, for_update=True)
        credential = await db.scalar(
            select(Credential).where(Credential.id == credential_id, Credential.provider_id == provider.id)
        )
        if credential is None:
            raise not_found("Credential")
        if credential.status != "submitted":
            raise conflict(f"Credential was already {credential.status}")
        on = today()
        if body.decision == "verify":
            if credential.valid_until is not None and credential.valid_until < on:
                raise unprocessable("An expired credential cannot be verified", "decision")
            credential.status = "verified"
        else:
            credential.status = "rejected"
        credential.review_note = body.note
        credential.reviewed_by = principal.user_id
        credential.reviewed_at = utcnow()

        credentials = await _credentials(db, provider.id)
        licenses = [c for c in credentials if c.kind == LICENSE]
        if any(_credential_valid_on(c, on) for c in licenses):
            derived = "verified"
        elif any(c.status == "submitted" for c in credentials):
            derived = "under_review"
        else:
            derived = "rejected"
        if derived != provider.verification_status:
            previous = provider.status
            provider.verification_status = derived
            provider.updated_at = utcnow()
            await _stage_status_event(db, provider, principal, previous=previous, reason=f"credential_{credential.status}")
        await db.commit()
        await db.refresh(credential)
        return credential_schema(credential)


provider_service = ProviderService()
