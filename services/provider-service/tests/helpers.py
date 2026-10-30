from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from ulid import ULID

from provider_service.api.deps import principal_headers
from provider_service.infra.db import SessionLocal
from provider_service.infra.models import OUTBOX

USER_PERMS = "providers:onboard,facilities:onboard"
STAFF_PERMS = "providers:onboard,facilities:onboard,providers:verify,facilities:verify"


def new_user() -> str:
    return str(ULID())


def user(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=USER_PERMS, tenant_id=tenant_id)


def staff(*, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(str(ULID()), permissions=STAFF_PERMS, tenant_id=tenant_id)


PROVIDER_BODY = {
    "type": "doctor",
    "display_name": "Dr. Test Practitioner",
    "title": "Consultant Infectious Diseases",
    "bio": {"en": "Infectious diseases specialist.", "ar": "أخصائية أمراض معدية."},
    "specialties": ["Infectious Diseases"],
    "languages": ["en", "ar", "fa"],
}

FACILITY_BODY = {
    "type": "clinic",
    "name": "Test Clinic",
    "license_authority": "dha",
    "license_number": "FAC-12345",
}

BRANCH_BODY = {
    "name": "Jumeirah",
    "address_line": "Jumeirah Beach Road 1",
    "city": "Dubai",
    "emirate": "Dubai",
    "country": "AE",
    "timezone": "Asia/Dubai",
    "latitude": 25.2048,
    "longitude": 55.2708,
}

WEEKDAY_HOURS = {"windows": [{"weekday": d, "start": "09:00", "end": "18:00"} for d in range(0, 5)]}


async def ok(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


async def create_provider(client: AsyncClient, owner: str, **overrides) -> dict:
    return await ok(await client.post("/v1/providers", json={**PROVIDER_BODY, **overrides}, headers=user(owner)), 201)


async def verify_provider(client: AsyncClient, provider_id: str, owner: str, *, activate: bool = True) -> None:
    credential = await ok(
        await client.post(
            f"/v1/providers/{provider_id}/credentials",
            json={
                "kind": "professional_license",
                "issuing_authority": "dha",
                "jurisdiction": "AE-DU",
                "number": f"DHA-{ULID()}",
                "valid_from": str(datetime.now(UTC).date() - timedelta(days=30)),
                "valid_until": str(datetime.now(UTC).date() + timedelta(days=365)),
            },
            headers=user(owner),
        ),
        201,
    )
    reviewer = staff()
    await ok(
        await client.post(
            f"/v1/providers/{provider_id}/credentials/{credential['id']}/review",
            json={"decision": "verify"},
            headers=reviewer,
        )
    )
    if activate:
        await ok(
            await client.post(
                f"/v1/providers/{provider_id}/status",
                json={"status": "active", "reason": "credentials verified"},
                headers=reviewer,
            )
        )


async def create_verified_facility(client: AsyncClient, admin: str, **overrides) -> tuple[dict, dict]:
    facility = await ok(
        await client.post(
            "/v1/facilities",
            json={**FACILITY_BODY, "license_number": f"FAC-{ULID()}", **overrides},
            headers=user(admin),
        ),
        201,
    )
    await ok(await client.post(f"/v1/facilities/{facility['id']}/review", json={"decision": "verify"}, headers=staff()))
    branch = await ok(
        await client.post(f"/v1/facilities/{facility['id']}/branches", json=BRANCH_BODY, headers=user(admin)), 201
    )
    await ok(await client.put(f"/v1/branches/{branch['id']}/operating-hours", json=WEEKDAY_HOURS, headers=user(admin)))
    return facility, branch


async def practice(client: AsyncClient) -> dict:
    """A verified, active provider with an active affiliation at a verified facility's open branch."""
    owner, admin = new_user(), new_user()
    provider = await create_provider(client, owner)
    await verify_provider(client, provider["id"], owner)
    facility, branch = await create_verified_facility(client, admin)
    affiliation = await ok(
        await client.post(
            "/v1/affiliations", json={"provider_id": provider["id"], "branch_id": branch["id"]}, headers=user(owner)
        ),
        201,
    )
    await ok(
        await client.post(
            f"/v1/affiliations/{affiliation['id']}/decision", json={"decision": "approve"}, headers=user(admin)
        )
    )
    return {"owner": owner, "admin": admin, "provider": provider, "facility": facility, "branch": branch, "affiliation": affiliation}


async def outbox_events(event_type: str) -> list[dict]:
    async with SessionLocal() as db:
        rows = await db.execute(select(OUTBOX.c.body).where(OUTBOX.c.event_type == event_type).order_by(OUTBOX.c.created_at))
        return [row.body for row in rows]


def utc(days: int = 0, hours: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(days=days, hours=hours)).isoformat()
