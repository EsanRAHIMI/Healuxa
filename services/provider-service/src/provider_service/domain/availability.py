"""Weekly availability rules and date-specific exceptions. Slots are derived by appointment-service."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from provider_service.domain import schemas
from provider_service.domain.access import (
    actor_of,
    conflict,
    facility_role,
    forbidden,
    is_provider_staff,
    not_found,
    owns_provider,
    unprocessable,
)
from provider_service.domain.affiliations import active_affiliation, can_manage_practice
from provider_service.domain.facilities import get_branch
from provider_service.domain.providers import get_provider, utcnow
from provider_service.domain.schemas import from_minutes, to_minutes
from provider_service.events.publisher import event_publisher
from provider_service.infra.models import (
    Affiliation,
    AvailabilityException,
    AvailabilityRule,
    Branch,
    OperatingHoursWindow,
    Provider,
)

SCHEDULERS = ("facility_admin", "scheduler")


async def _can_view(db: AsyncSession, principal: Principal, provider: Provider) -> bool:
    if owns_provider(principal, provider) or is_provider_staff(principal):
        return True
    facility_ids = (
        await db.scalars(
            select(Affiliation.facility_id).where(Affiliation.provider_id == provider.id, Affiliation.status == "active")
        )
    ).all()
    for facility_id in set(facility_ids):
        if await facility_role(db, principal, facility_id) is not None:
            return True
    return False


async def _stage(db: AsyncSession, principal: Principal, provider: Provider, branch_id: str | None, change: str) -> None:
    await event_publisher.publish(
        db=db,
        event_type="catalog.availability_changed",
        tenant_id=provider.tenant_id,
        payload={
            "provider_id": provider.id,
            "branch_id": branch_id,
            "change": change,
            "changed_at": utcnow().isoformat(),
        },
        actor=actor_of(principal),
    )


def rule_schema(rule: AvailabilityRule, timezone: str) -> schemas.AvailabilityRule:
    return schemas.AvailabilityRule(
        id=rule.id,
        provider_id=rule.provider_id,
        branch_id=rule.branch_id,
        timezone=timezone,
        weekday=rule.weekday,
        start=from_minutes(rule.start_minute),
        end=from_minutes(rule.end_minute),
        effective_from=rule.effective_from,
        effective_until=rule.effective_until,
    )


def exception_schema(item: AvailabilityException) -> schemas.AvailabilityException:
    return schemas.AvailabilityException(
        id=item.id,
        provider_id=item.provider_id,
        branch_id=item.branch_id,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        reason=item.reason,
    )


def _dates_overlap(a_from: date, a_until: date | None, b_from: date, b_until: date | None) -> bool:
    return (a_until is None or b_from <= a_until) and (b_until is None or a_from <= b_until)


class AvailabilityService:
    async def create_rule(
        self, db: AsyncSession, principal: Principal, provider_id: str, body: schemas.AvailabilityRuleInput
    ) -> schemas.AvailabilityRule:
        # Row lock on the provider serialises rule changes, so concurrent overlapping requests cannot
        # both pass the overlap check below.
        provider = await get_provider(db, principal.tenant_id, provider_id, for_update=True)
        branch = await get_branch(db, principal.tenant_id, body.branch_id)
        if not await can_manage_practice(db, principal, provider, branch.facility_id, SCHEDULERS):
            raise forbidden("Only the provider or the facility's schedulers can manage availability")
        if await active_affiliation(db, provider, branch.id) is None:
            raise unprocessable("Provider has no active affiliation at this branch", "branch_id")

        start, end = to_minutes(body.start), to_minutes(body.end)
        windows = (
            await db.scalars(
                select(OperatingHoursWindow).where(
                    OperatingHoursWindow.branch_id == branch.id, OperatingHoursWindow.weekday == body.weekday
                )
            )
        ).all()
        if not any(w.start_minute <= start and end <= w.end_minute for w in windows):
            raise unprocessable("Rule must fall within the branch's opening hours for that weekday", "start")

        # A practitioner cannot be in two places at once: check every branch, not just this one.
        same_day = (
            await db.scalars(
                select(AvailabilityRule).where(
                    AvailabilityRule.provider_id == provider.id,
                    AvailabilityRule.weekday == body.weekday,
                    AvailabilityRule.start_minute < end,
                    AvailabilityRule.end_minute > start,
                )
            )
        ).all()
        if any(_dates_overlap(r.effective_from, r.effective_until, body.effective_from, body.effective_until) for r in same_day):
            raise conflict("Rule overlaps an existing availability rule for this provider")

        rule = AvailabilityRule(
            id=str(ULID()),
            tenant_id=provider.tenant_id,
            provider_id=provider.id,
            branch_id=branch.id,
            weekday=body.weekday,
            start_minute=start,
            end_minute=end,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
        )
        db.add(rule)
        await _stage(db, principal, provider, branch.id, "rule_added")
        await db.commit()
        await db.refresh(rule)
        return rule_schema(rule, branch.timezone)

    async def list_rules(self, db: AsyncSession, principal: Principal, provider_id: str) -> list[schemas.AvailabilityRule]:
        provider = await get_provider(db, principal.tenant_id, provider_id)
        if not await _can_view(db, principal, provider):
            raise not_found("Provider")
        rows = (
            await db.execute(
                select(AvailabilityRule, Branch.timezone)
                .join(Branch, Branch.id == AvailabilityRule.branch_id)
                .where(AvailabilityRule.provider_id == provider.id)
                .order_by(AvailabilityRule.weekday, AvailabilityRule.start_minute)
            )
        ).all()
        return [rule_schema(rule, tz) for rule, tz in rows]

    async def delete_rule(self, db: AsyncSession, principal: Principal, rule_id: str) -> None:
        rule = await db.scalar(
            select(AvailabilityRule).where(AvailabilityRule.id == rule_id, AvailabilityRule.tenant_id == principal.tenant_id)
        )
        if rule is None:
            raise not_found("Availability rule")
        provider = await get_provider(db, principal.tenant_id, rule.provider_id, for_update=True)
        branch = await get_branch(db, principal.tenant_id, rule.branch_id)
        if not await can_manage_practice(db, principal, provider, branch.facility_id, SCHEDULERS):
            raise not_found("Availability rule")
        await db.delete(rule)
        await _stage(db, principal, provider, branch.id, "rule_removed")
        await db.commit()

    async def create_exception(
        self, db: AsyncSession, principal: Principal, provider_id: str, body: schemas.AvailabilityExceptionInput
    ) -> schemas.AvailabilityException:
        provider = await get_provider(db, principal.tenant_id, provider_id, for_update=True)
        if body.branch_id is not None:
            branch = await get_branch(db, principal.tenant_id, body.branch_id)
            allowed = await can_manage_practice(db, principal, provider, branch.facility_id, SCHEDULERS)
        else:
            allowed = owns_provider(principal, provider) or is_provider_staff(principal)
        if not allowed:
            raise forbidden("Not allowed to manage this provider's availability")
        item = AvailabilityException(
            id=str(ULID()),
            tenant_id=provider.tenant_id,
            provider_id=provider.id,
            branch_id=body.branch_id,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            reason=body.reason,
        )
        db.add(item)
        await _stage(db, principal, provider, body.branch_id, "exception_added")
        await db.commit()
        await db.refresh(item)
        return exception_schema(item)

    async def list_exceptions(
        self, db: AsyncSession, principal: Principal, provider_id: str, *, from_: date | None, to: date | None
    ) -> list[schemas.AvailabilityException]:
        provider = await get_provider(db, principal.tenant_id, provider_id)
        if not await _can_view(db, principal, provider):
            raise not_found("Provider")
        stmt = select(AvailabilityException).where(AvailabilityException.provider_id == provider.id)
        if from_:
            stmt = stmt.where(AvailabilityException.ends_at > datetime.combine(from_, time.min, tzinfo=UTC))
        if to:
            stmt = stmt.where(AvailabilityException.starts_at < datetime.combine(to, time.max, tzinfo=UTC))
        rows = await db.scalars(stmt.order_by(AvailabilityException.starts_at).limit(500))
        return [exception_schema(e) for e in rows]


availability_service = AvailabilityService()
