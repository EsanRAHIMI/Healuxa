"""Test helpers: a fake provider-service directory, identities, and booking shortcuts.

The frozen clock starts at Monday 2027-03-01 08:00 Asia/Dubai (04:00 UTC). No real patient data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from sqlalchemy import select
from ulid import ULID

from appointment_service.api.deps import principal_headers
from appointment_service.clients.provider_directory import (
    BranchRef,
    ExceptionIn,
    FacilityRef,
    FacilityRole,
    HoursWindowIn,
    Offering,
    ProviderRef,
    ProviderUnavailable,
    RuleIn,
    SchedulingActor,
    SchedulingContext,
)
from appointment_service.config import settings
from appointment_service.infra.db import SessionLocal
from appointment_service.infra.models import OUTBOX

NOW = datetime(2027, 3, 1, 4, 0, tzinfo=UTC)  # Monday 08:00 in Dubai
MONDAY = date(2027, 3, 1)
USER_PERMS = "appointments:create,appointments:read,appointments:write"
MANAGER_PERMS = USER_PERMS + ",appointments:manage"


def new_id() -> str:
    return str(ULID())


def customer(user_id: str | None = None, *, tenant_id: str | None = None, permissions: str = USER_PERMS) -> dict[str, str]:
    return principal_headers(user_id or new_id(), permissions=permissions, tenant_id=tenant_id)


def manager(*, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(new_id(), permissions=MANAGER_PERMS, tenant_id=tenant_id)


def local(day: date, hhmm: str, tz: str = "Asia/Dubai") -> datetime:
    hours, minutes = (int(p) for p in hhmm.split(":"))
    return datetime.combine(day, time(hours, minutes), tzinfo=ZoneInfo(tz)).astimezone(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class Practice:
    tenant_id: str
    service_id: str
    provider_id: str
    facility_id: str
    branch_id: str
    timezone: str
    owner: str
    admin: str
    scheduler: str
    billing: str

    def owner_headers(self) -> dict[str, str]:
        return customer(self.owner, tenant_id=self.tenant_id)

    def admin_headers(self) -> dict[str, str]:
        return customer(self.admin, tenant_id=self.tenant_id)

    def scheduler_headers(self) -> dict[str, str]:
        return customer(self.scheduler, tenant_id=self.tenant_id)

    def billing_headers(self) -> dict[str, str]:
        return customer(self.billing, tenant_id=self.tenant_id)


class FakeDirectory:
    """Stands in for provider-service's internal scheduling API."""

    def __init__(self) -> None:
        self.contexts: dict[tuple[str, str], SchedulingContext] = {}
        self.actors: dict[tuple[str, str], SchedulingActor] = {}
        self.down = False
        self.context_calls = 0

    async def scheduling_context(self, tenant_id, service_id, window_start, window_end):
        self.context_calls += 1
        if self.down:
            raise ProviderUnavailable("simulated outage")
        context = self.contexts.get((tenant_id, service_id))
        return None if context is None else context.model_copy(deep=True)

    async def actor(self, tenant_id, user_id):
        if self.down:
            raise ProviderUnavailable("simulated outage")
        return self.actors.get((tenant_id, user_id), SchedulingActor(user_id=user_id))

    def _grant(self, tenant_id: str, user_id: str, *, provider_id: str | None = None, facility: tuple[str, str] | None = None) -> None:
        actor = self.actors.setdefault((tenant_id, user_id), SchedulingActor(user_id=user_id))
        if provider_id:
            actor.provider_ids.append(provider_id)
        if facility:
            actor.facility_roles.append(FacilityRole(facility_id=facility[0], role=facility[1]))

    def add_practice(
        self,
        *,
        tz: str = "Asia/Dubai",
        duration: int = 30,
        buffer: int = 0,
        rules: list[tuple[int, str, str]] | None = None,
        effective_from: date = date(2027, 1, 1),
        effective_until: date | None = None,
        hours: list[tuple[int, str, str]] | None = None,
        exceptions: list[tuple[datetime, datetime]] | None = None,
        price_minor: int | None = 60000,
        tenant_id: str | None = None,
        provider_id: str | None = None,
        owner: str | None = None,
        bookable: bool = True,
    ) -> Practice:
        tenant_id = tenant_id or settings.tenant_default
        rules = rules if rules is not None else [(d, "09:00", "17:00") for d in range(5)]
        hours = hours if hours is not None else [(d, "08:00", "20:00") for d in range(6)]
        p = Practice(
            tenant_id=tenant_id,
            service_id=new_id(),
            provider_id=provider_id or new_id(),
            facility_id=new_id(),
            branch_id=new_id(),
            timezone=tz,
            owner=owner or new_id(),
            admin=new_id(),
            scheduler=new_id(),
            billing=new_id(),
        )

        def minutes(hhmm: str) -> int:
            h, m = (int(x) for x in hhmm.split(":"))
            return h * 60 + m

        self.contexts[(tenant_id, p.service_id)] = SchedulingContext(
            offering=Offering(
                id=p.service_id,
                provider_id=p.provider_id,
                facility_id=p.facility_id,
                branch_id=p.branch_id,
                name="Initial consultation",
                category="consultation",
                duration_minutes=duration,
                buffer_minutes=buffer,
                mode="in_person",
                status="active" if bookable else "retired",
                price_type="on_request" if price_minor is None else "fixed",
                professional_fee_minor=None if price_minor is None else price_minor - 10000,
                facility_fee_minor=None if price_minor is None else 10000,
                currency="AED",
            ),
            provider=ProviderRef(id=p.provider_id, user_id=p.owner, status="active", verification_status="verified"),
            facility=FacilityRef(id=p.facility_id, status="active", verification_status="verified"),
            branch=BranchRef(id=p.branch_id, facility_id=p.facility_id, timezone=tz, status="active"),
            affiliation_active=True,
            bookable=bookable,
            operating_hours=[HoursWindowIn(weekday=d, start_minute=minutes(s), end_minute=minutes(e)) for d, s, e in hours],
            availability_rules=[
                RuleIn(id=new_id(), weekday=d, start_minute=minutes(s), end_minute=minutes(e), effective_from=effective_from, effective_until=effective_until)
                for d, s, e in rules
            ],
            exceptions=[
                ExceptionIn(id=new_id(), branch_id=None, starts_at=s, ends_at=e, reason="leave") for s, e in (exceptions or [])
            ],
        )
        self._grant(tenant_id, p.owner, provider_id=p.provider_id)
        self._grant(tenant_id, p.admin, facility=(p.facility_id, "facility_admin"))
        self._grant(tenant_id, p.scheduler, facility=(p.facility_id, "scheduler"))
        self._grant(tenant_id, p.billing, facility=(p.facility_id, "billing"))
        return p

    def set_bookable(self, practice: Practice, bookable: bool) -> None:
        self.contexts[(practice.tenant_id, practice.service_id)].bookable = bookable


async def ok(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


TUESDAY = MONDAY + timedelta(days=1)


async def hold(client: AsyncClient, practice: Practice, headers: dict[str, str], start: datetime, **extra) -> dict:
    return await ok(
        await client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(start), **extra}, headers=headers),
        201,
    )


async def transition(client: AsyncClient, appointment_id: str, headers: dict[str, str], name: str, status: int = 200, **extra) -> dict:
    return await ok(
        await client.post(f"/v1/appointments/{appointment_id}/status", json={"transition": name, **extra}, headers=headers), status
    )


async def requested(client: AsyncClient, practice: Practice, headers: dict[str, str], start: datetime) -> dict:
    held = await hold(client, practice, headers, start)
    return await transition(client, held["id"], headers, "submit")


async def confirmed(client: AsyncClient, practice: Practice, headers: dict[str, str], start: datetime) -> dict:
    req = await requested(client, practice, headers, start)
    return await transition(client, req["id"], practice.owner_headers(), "accept")


async def outbox(event_type: str | None = None) -> list[dict]:
    async with SessionLocal() as db:
        stmt = select(OUTBOX.c.body).order_by(OUTBOX.c.created_at, OUTBOX.c.event_id)
        if event_type:
            stmt = stmt.where(OUTBOX.c.event_type == event_type)
        return [row.body for row in await db.execute(stmt)]


# ── event-contract validation ─────────────────────────────────────────────────────────────────────
_SCHEMAS = Path(__file__).resolve().parents[3] / "packages" / "event-contracts" / "schemas"


def _registry() -> Registry:
    registry = Registry()
    for name in ("common.schema.json", "envelope.schema.json", "appointment.schema.json"):
        doc = json.loads((_SCHEMAS / name).read_text())
        resource = Resource.from_contents(doc)
        registry = registry.with_resource(name, resource).with_resource(doc["$id"], resource)
    return registry


def validate_event(envelope: dict) -> None:
    """Envelope and payload must satisfy packages/event-contracts (raises on violation)."""
    registry = _registry()
    envelope_schema = json.loads((_SCHEMAS / "envelope.schema.json").read_text())
    Draft202012Validator(envelope_schema, registry=registry, format_checker=FormatChecker()).validate(envelope)
    definition = envelope["schema_ref"].split("#/$defs/")[1]
    payload_schema = {"$ref": f"appointment.schema.json#/$defs/{definition}"}
    Draft202012Validator(payload_schema, registry=registry, format_checker=FormatChecker()).validate(envelope["payload"])
