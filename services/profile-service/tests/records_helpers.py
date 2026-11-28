"""Shared fixtures for records tests: a fake organisation directory, principals, files, uploads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from httpx import AsyncClient, Response
from ulid import ULID

from profile_service.api.deps import principal_headers
from profile_service.clients.organisations import Actor, ActorFacility, ActorProvider, DirectoryUnavailable, Grantee
from profile_service.infra.mongo import get_database

CUSTOMER_PERMS = "profiles:read,profiles:write,records:manage"
PRACTICE_PERMS = "profiles:read,profiles:write,records:manage,records:read_shared"
ADMIN_PERMS = (
    "profiles:read,profiles:write,records:manage,records:read_shared,providers:verify,facilities:verify,"
    "appointments:manage"
)

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << >>\n%%EOF\n" + b"Haemoglobin 13.9 g/dL" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64

REPO = Path(__file__).resolve().parents[3]
EVENT_SCHEMAS = REPO / "packages/event-contracts/schemas"


def new_id() -> str:
    return str(ULID())


def customer(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=CUSTOMER_PERMS, tenant_id=tenant_id)


def practice(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=PRACTICE_PERMS, tenant_id=tenant_id)


def platform_admin(user_id: str) -> dict[str, str]:
    return principal_headers(user_id, permissions=ADMIN_PERMS)


class FakeDirectory:
    """In-memory provider-service: who owns which practitioner profile, who staffs which facility."""

    def __init__(self) -> None:
        self.providers: dict[str, dict[str, Any]] = {}
        self.facilities: dict[str, dict[str, Any]] = {}
        self.down = False
        self.actor_calls = 0

    def add_provider(self, owner: str, *, tenant_id: str = "healuxa-dubai", status: str = "active", name: str = "Dr. Sara Haddad") -> str:
        pid = new_id()
        self.providers[pid] = {"owner": owner, "tenant": tenant_id, "status": status, "name": name}
        return pid

    def add_facility(self, *, tenant_id: str = "healuxa-dubai", status: str = "active", name: str = "Marina Clinic") -> str:
        fid = new_id()
        self.facilities[fid] = {"staff": {}, "tenant": tenant_id, "status": status, "name": name}
        return fid

    def add_staff(self, facility_id: str, user_id: str, role: str = "scheduler") -> None:
        self.facilities[facility_id]["staff"][user_id] = role

    def remove_staff(self, facility_id: str, user_id: str) -> None:
        self.facilities[facility_id]["staff"].pop(user_id, None)

    async def actor(self, tenant_id: str, user_id: str) -> Actor:
        self.actor_calls += 1
        if self.down:
            raise DirectoryUnavailable("down")
        return Actor(
            user_id=user_id,
            providers=[
                ActorProvider(id=pid, status=p["status"], verification_status="verified")
                for pid, p in self.providers.items()
                if p["owner"] == user_id and p["tenant"] == tenant_id
            ],
            facilities=[
                ActorFacility(id=fid, role=f["staff"][user_id], status=f["status"], verification_status="verified")
                for fid, f in self.facilities.items()
                if user_id in f["staff"] and f["tenant"] == tenant_id
            ],
        )

    async def grantee(self, tenant_id: str, grantee_type: str, grantee_id: str) -> Grantee | None:
        if self.down:
            raise DirectoryUnavailable("down")
        source = self.providers if grantee_type == "provider" else self.facilities
        org = source.get(grantee_id)
        if org is None or org["tenant"] != tenant_id:
            return None
        return Grantee(type=grantee_type, id=grantee_id, name=org["name"], status=org["status"], verification_status="verified")


async def ok(response: Response, status: int = 200) -> Any:
    assert response.status_code == status, f"{response.status_code}: {response.text}"
    return response.json() if response.content and response.headers.get("content-type", "").startswith("application/json") else response


async def upload(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    data: bytes = PDF,
    filename: str = "blood-test.pdf",
    content_type: str = "application/pdf",
    title: str = "Blood panel March",
    record_type: str = "lab_result",
    extra: dict[str, str] | None = None,
) -> Response:
    form = {"title": title, "type": record_type, **(extra or {})}
    return await client.post("/v1/records", headers=headers, data=form, files={"file": (filename, data, content_type)})


async def uploaded(client: AsyncClient, headers: dict[str, str], **kwargs) -> dict:
    return await ok(await upload(client, headers, **kwargs), 201)


async def grant(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    grantee_type: str,
    grantee_id: str,
    record_ids: list[str],
    purpose: str = "consultation",
    **extra: Any,
) -> Response:
    return await client.post(
        "/v1/record-grants",
        headers=headers,
        json={"grantee_type": grantee_type, "grantee_id": grantee_id, "record_ids": record_ids, "purpose": purpose, **extra},
    )


async def access_log(user_id: str) -> list[dict]:
    return await get_database()["record_access_log"].find({"owner_user_id": user_id}).sort("_id", 1).to_list()


async def outbox(event_type: str) -> list[dict]:
    docs = await get_database()["outbox_events"].find({"body.type": event_type}).sort("created_at", 1).to_list()
    return [d["body"] for d in docs]


def event_validator(def_name: str):
    """jsonschema validator for one payload $def, resolving common.schema.json refs."""
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    common = json.loads((EVENT_SCHEMAS / "common.schema.json").read_text())
    profile = json.loads((EVENT_SCHEMAS / "profile.schema.json").read_text())
    registry = Registry().with_resources(
        [
            ("common.schema.json", Resource.from_contents(common)),
            (common["$id"], Resource.from_contents(common)),
            (profile["$id"], Resource.from_contents(profile)),
        ]
    )
    schema = {"$schema": profile["$schema"], "$id": profile["$id"], "$ref": f"#/$defs/{def_name}", "$defs": profile["$defs"]}
    return Draft202012Validator(schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER)
