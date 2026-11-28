"""Medical records: customer-owned documents, consent grants and the append-only access log.

Authorisation model (default deny, checked on every read):

- the **owner** (the customer who uploaded the record) manages it and decides who may read it;
- a **grantee** may read a record only through an *active* grant (not revoked, not expired) naming a
  provider or facility, and only while provider-service confirms — server side, on that request — that
  the caller owns that practitioner profile or currently holds an allowed staff role at that facility;
- nobody else can: there is no platform-staff or admin path in this module.

Every view, download, grant, revocation and refused attempt is written to ``record_access_log``; this
module only ever inserts into that collection (erasure is the single exception, see ``erase_user``).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from healuxa_py_common.errors import ApiError, FieldError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import DuplicateKeyError
from ulid import ULID

from profile_service.clients.organisations import Actor, DirectoryUnavailable, OrganisationDirectory
from profile_service.config import settings
from profile_service.domain import record_schemas as schemas
from profile_service.domain.files import FileKind, invalid_file, sanitise_filename, validate_upload
from profile_service.events.publisher import event_publisher
from profile_service.infra.crypto import DecryptionError, RecordCipher
from profile_service.infra.mongo import get_client, get_database
from profile_service.infra.storage import BlobNotFound, RecordStore

logger = logging.getLogger(__name__)

RECORDS = "medical_records"
GRANTS = "record_grants"
ACCESS_LOG = "record_access_log"
BLOB_GC = "record_blob_gc"
IDEMPOTENCY = "record_idempotency"

MANAGE_PERMISSION = "records:manage"
READ_SHARED_PERMISSION = "records:read_shared"

ClientInfo = dict[str, str | None]


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def not_found(what: str = "Record") -> ApiError:
    return ApiError(status=404, code="not_found", title="Not found", detail=f"{what} not found")


def forbidden(detail: str) -> ApiError:
    return ApiError(status=403, code="forbidden", title="Forbidden", detail=detail)


def unprocessable(detail: str, field: str, code: str = "invalid") -> ApiError:
    return ApiError(
        status=422,
        code="unprocessable",
        title="Unprocessable",
        detail=detail,
        errors=[FieldError(field=field, code=code, message=detail)],
    )


def unavailable(detail: str) -> ApiError:
    return ApiError(status=503, code="service_unavailable", title="Service unavailable", detail=detail)


def _col(name: str):
    return get_database()[name]


def _aad(tenant_id: str, record_id: str) -> bytes:
    return f"{tenant_id}:{record_id}".encode()


def _allowed_facility_roles() -> frozenset[str]:
    return frozenset(r.strip() for r in settings.records_facility_roles.split(",") if r.strip())


def member_organisations(actor: Actor) -> dict[tuple[str, str], str]:
    """Organisations the caller may act for right now, mapped to the capacity they act in."""
    orgs: dict[tuple[str, str], str] = {}
    for provider in actor.providers:
        if provider.status == "active":
            orgs[("provider", provider.id)] = "practitioner"
    roles = _allowed_facility_roles()
    for facility in actor.facilities:
        if facility.status == "active" and facility.role in roles:
            orgs[("facility", facility.id)] = "facility_staff"
    return orgs


def _grant_status(doc: dict[str, Any], now: datetime) -> schemas.GrantStatus:
    if doc.get("revoked_at") is not None:
        return "revoked"
    return "expired" if _aware(doc["expires_at"]) <= now else "active"


def _grant_out(doc: dict[str, Any], now: datetime) -> schemas.Grant:
    return schemas.Grant(
        id=doc["_id"],
        user_id=doc["user_id"],
        grantee_type=doc["grantee_type"],
        grantee_id=doc["grantee_id"],
        grantee_name=doc.get("grantee_name") or "",
        record_ids=list(doc.get("record_ids") or []),
        purpose=doc["purpose"],
        appointment_id=doc.get("appointment_id"),
        status=_grant_status(doc, now),
        created_at=_aware(doc["created_at"]),
        expires_at=_aware(doc["expires_at"]),
        revoked_at=_aware(doc["revoked_at"]) if doc.get("revoked_at") else None,
    )


def _record_out(doc: dict[str, Any], shares: list[schemas.RecordShare]) -> schemas.Record:
    return schemas.Record(
        id=doc["_id"],
        user_id=doc["user_id"],
        title=doc["title"],
        type=doc["type"],
        document_date=date.fromisoformat(doc["document_date"]) if doc.get("document_date") else None,
        note=doc.get("note"),
        file_name=doc["file"]["name"],
        content_type=doc["file"]["content_type"],
        size_bytes=doc["file"]["size"],
        created_at=_aware(doc["created_at"]),
        updated_at=_aware(doc["updated_at"]),
        shares=shares,
    )


def _shared_record_out(doc: dict[str, Any]) -> schemas.SharedRecord:
    return schemas.SharedRecord(
        id=doc["_id"],
        title=doc["title"],
        type=doc["type"],
        document_date=date.fromisoformat(doc["document_date"]) if doc.get("document_date") else None,
        note=doc.get("note"),
        file_name=doc["file"]["name"],
        content_type=doc["file"]["content_type"],
        size_bytes=doc["file"]["size"],
    )


def _shared_grant_fields(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "patient_user_id": doc["user_id"],
        "grantee_type": doc["grantee_type"],
        "grantee_id": doc["grantee_id"],
        "purpose": doc["purpose"],
        "appointment_id": doc.get("appointment_id"),
        "record_count": len(doc.get("record_ids") or []),
        "created_at": _aware(doc["created_at"]),
        "expires_at": _aware(doc["expires_at"]),
    }


@dataclass(frozen=True)
class RecordContent:
    data: bytes
    file_name: str
    content_type: str


@dataclass(frozen=True)
class Upload:
    data: bytes
    filename: str | None
    content_type: str | None
    title: str
    type: str
    document_date: date | None
    note: str | None


class RecordsService:
    def __init__(self, *, store: RecordStore, cipher: RecordCipher, directory: OrganisationDirectory) -> None:
        self._store = store
        self._cipher = cipher
        self._directory = directory

    # ── access log ───────────────────────────────────────────────────────────────────────────

    def _log_entry(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        record_id: str,
        action: str,
        actor_user_id: str,
        actor_kind: str,
        client: ClientInfo,
        grant_id: str | None = None,
        organisation: dict[str, Any] | None = None,
        attempted: str | None = None,
        reason: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        return {
            "_id": str(ULID()),
            "tenant_id": tenant_id,
            "owner_user_id": owner_user_id,
            "record_id": record_id,
            "grant_id": grant_id,
            "action": action,
            "attempted": attempted,
            "reason": reason,
            "actor_user_id": actor_user_id,
            "actor_kind": actor_kind,
            "organisation": organisation,
            "client": {"network": client.get("network"), "agent": client.get("agent")},
            "occurred_at": at or utcnow(),
        }

    async def _append_log(self, entries: list[dict[str, Any]], session: AsyncClientSession | None = None) -> None:
        if entries:
            await _col(ACCESS_LOG).insert_many(entries, session=session)

    async def _log_denied(
        self,
        principal: Principal,
        *,
        owner_user_id: str,
        record_ids: list[str],
        attempted: str,
        reason: str,
        client: ClientInfo,
        grant: dict[str, Any] | None = None,
        actor_kind: str = "other",
    ) -> None:
        organisation = (
            {"type": grant["grantee_type"], "id": grant["grantee_id"], "name": grant.get("grantee_name")} if grant else None
        )
        await self._append_log(
            [
                self._log_entry(
                    tenant_id=principal.tenant_id,
                    owner_user_id=owner_user_id,
                    record_id=record_id,
                    action="denied",
                    attempted=attempted,
                    reason=reason,
                    actor_user_id=principal.user_id,
                    actor_kind=actor_kind,
                    grant_id=grant["_id"] if grant else None,
                    organisation=organisation,
                    client=client,
                )
                for record_id in record_ids
            ]
        )

    # ── idempotency ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _idempotency_id(principal: Principal, scope: str, key: str) -> str:
        return f"{principal.tenant_id}:{principal.user_id}:{scope}:{key}"

    async def _replayed(self, principal: Principal, scope: str, key: str | None, fingerprint: str) -> str | None:
        """Resource id of the original request for this key, if any (409 when the request differs)."""
        if not key:
            return None
        doc = await _col(IDEMPOTENCY).find_one({"_id": self._idempotency_id(principal, scope, key)})
        if doc is None:
            return None
        if doc["fingerprint"] != fingerprint:
            raise ApiError(
                status=409,
                code="idempotency_conflict",
                title="Conflict",
                detail="Idempotency-Key was already used with a different request",
            )
        return doc["resource_id"]

    async def _remember(
        self, principal: Principal, scope: str, key: str | None, fingerprint: str, resource_id: str, session
    ) -> None:
        if not key:
            return
        await _col(IDEMPOTENCY).insert_one(
            {
                "_id": self._idempotency_id(principal, scope, key),
                "tenant_id": principal.tenant_id,
                "user_id": principal.user_id,
                "fingerprint": fingerprint,
                "resource_id": resource_id,
                "created_at": utcnow(),
            },
            session=session,
        )

    # ── owner: records ───────────────────────────────────────────────────────────────────────

    async def _owned(self, principal: Principal, record_id: str) -> dict[str, Any]:
        doc = await _col(RECORDS).find_one(
            {"_id": record_id, "tenant_id": principal.tenant_id, "user_id": principal.user_id}
        )
        if doc is None:
            # Another customer's record is indistinguishable from a missing one.
            raise not_found()
        return doc

    async def _shares_for(self, tenant_id: str, user_id: str, now: datetime) -> dict[str, list[schemas.RecordShare]]:
        shares: dict[str, list[schemas.RecordShare]] = {}
        cursor = _col(GRANTS).find(
            {"tenant_id": tenant_id, "user_id": user_id, "revoked_at": None, "expires_at": {"$gt": now}}
        ).sort("created_at", 1)
        async for grant in cursor:
            share = schemas.RecordShare(
                grant_id=grant["_id"],
                grantee_type=grant["grantee_type"],
                grantee_id=grant["grantee_id"],
                grantee_name=grant.get("grantee_name") or "",
                purpose=grant["purpose"],
                expires_at=_aware(grant["expires_at"]),
            )
            for record_id in grant.get("record_ids") or []:
                shares.setdefault(record_id, []).append(share)
        return shares

    async def _usage(self, tenant_id: str, user_id: str) -> tuple[int, int]:
        rows = await (
            await _col(RECORDS).aggregate(
                [
                    {"$match": {"tenant_id": tenant_id, "user_id": user_id}},
                    {"$group": {"_id": None, "count": {"$sum": 1}, "bytes": {"$sum": "$file.size"}}},
                ]
            )
        ).to_list()
        return (rows[0]["count"], rows[0]["bytes"]) if rows else (0, 0)

    async def list_records(self, principal: Principal) -> schemas.RecordList:
        now = utcnow()
        shares = await self._shares_for(principal.tenant_id, principal.user_id, now)
        docs = (
            await _col(RECORDS)
            .find({"tenant_id": principal.tenant_id, "user_id": principal.user_id})
            .sort([("created_at", -1), ("_id", -1)])
            .to_list()
        )
        count, total = await self._usage(principal.tenant_id, principal.user_id)
        return schemas.RecordList(
            data=[_record_out(d, shares.get(d["_id"], [])) for d in docs],
            usage=schemas.RecordUsage(
                record_count=count,
                total_bytes=total,
                max_records=settings.records_max_per_user,
                max_total_bytes=settings.records_max_total_bytes_per_user,
                max_file_bytes=settings.records_max_file_bytes,
            ),
        )

    async def get_record(self, principal: Principal, record_id: str) -> schemas.Record:
        doc = await self._owned(principal, record_id)
        shares = await self._shares_for(principal.tenant_id, principal.user_id, utcnow())
        return _record_out(doc, shares.get(record_id, []))

    async def upload(self, principal: Principal, upload: Upload, *, idempotency_key: str | None) -> schemas.Record:
        kind: FileKind = validate_upload(
            upload.data,
            claimed_content_type=upload.content_type,
            filename=upload.filename,
            max_bytes=settings.records_max_file_bytes,
        )
        digest = hashlib.sha256(upload.data).hexdigest()
        fingerprint = hashlib.sha256(
            "|".join([digest, upload.title, upload.type, str(upload.document_date), upload.note or ""]).encode()
        ).hexdigest()
        replay = await self._replayed(principal, "upload", idempotency_key, fingerprint)
        if replay is not None:
            return await self.get_record(principal, replay)

        count, total = await self._usage(principal.tenant_id, principal.user_id)
        if count >= settings.records_max_per_user:
            raise invalid_file("record_limit", f"You can keep up to {settings.records_max_per_user} records")
        if total + len(upload.data) > settings.records_max_total_bytes_per_user:
            raise invalid_file("storage_limit", "Your records storage is full")

        record_id = str(ULID())
        storage_key = f"{principal.tenant_id}/{record_id}/{ULID()}"
        sealed = self._cipher.seal(upload.data, aad=_aad(principal.tenant_id, record_id))
        now = utcnow()
        doc = {
            "_id": record_id,
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
            "title": upload.title,
            "type": upload.type,
            "document_date": upload.document_date.isoformat() if upload.document_date else None,
            "note": upload.note or None,
            "file": {
                "name": sanitise_filename(upload.filename, kind),
                "content_type": kind.content_type,
                "size": len(upload.data),
                "sha256": digest,
                "storage_key": storage_key,
                "key_id": self._cipher.active_key_id,
            },
            "created_at": now,
            "updated_at": now,
        }
        # GridFS cannot join a transaction: write the bytes first, then the metadata; a failed
        # metadata write removes the orphaned (and still encrypted) bytes again.
        await self._store.put(storage_key, sealed)
        try:

            async def apply(session: AsyncClientSession) -> None:
                await _col(RECORDS).insert_one(doc, session=session)
                await self._remember(principal, "upload", idempotency_key, fingerprint, record_id, session)

            async with get_client().start_session() as session:
                await session.with_transaction(apply)
        except DuplicateKeyError:
            await self._store.delete(storage_key)
            replay = await self._replayed(principal, "upload", idempotency_key, fingerprint)
            if replay is None:
                raise ApiError(status=409, code="conflict", title="Conflict", detail="Upload conflicted") from None
            return await self.get_record(principal, replay)
        except BaseException:
            await self._store.delete(storage_key)
            raise
        return _record_out(doc, [])

    async def update_record(self, principal: Principal, record_id: str, body: schemas.RecordUpdate) -> schemas.Record:
        await self._owned(principal, record_id)
        changes: dict[str, Any] = {}
        fields = body.model_fields_set
        if "title" in fields:
            if body.title is None:
                raise unprocessable("title cannot be empty", "title")
            changes["title"] = body.title
        if "type" in fields:
            if body.type is None:
                raise unprocessable("type cannot be empty", "type")
            changes["type"] = body.type
        if "document_date" in fields:
            if body.document_date is not None and body.document_date > utcnow().date() + timedelta(days=1):
                raise unprocessable("document_date cannot be in the future", "document_date")
            changes["document_date"] = body.document_date.isoformat() if body.document_date else None
        if "note" in fields:
            changes["note"] = body.note or None
        if changes:
            changes["updated_at"] = utcnow()
            await _col(RECORDS).update_one(
                {"_id": record_id, "tenant_id": principal.tenant_id, "user_id": principal.user_id}, {"$set": changes}
            )
        return await self.get_record(principal, record_id)

    async def delete_record(self, principal: Principal, record_id: str, client: ClientInfo) -> None:
        doc = await self._owned(principal, record_id)
        storage_key = doc["file"]["storage_key"]
        now = utcnow()

        async def apply(session: AsyncClientSession) -> None:
            deleted = await _col(RECORDS).delete_one(
                {"_id": record_id, "tenant_id": principal.tenant_id, "user_id": principal.user_id}, session=session
            )
            if deleted.deleted_count == 0:
                return
            await _col(BLOB_GC).insert_one({"_id": storage_key, "created_at": now}, session=session)
            affected = await (
                _col(GRANTS)
                .find({"tenant_id": principal.tenant_id, "user_id": principal.user_id, "record_ids": record_id}, session=session)
                .to_list()
            )
            for grant in affected:
                await self._remove_from_grant(principal, grant, [record_id], "record_deleted", now, session)
            await self._append_log(
                [
                    self._log_entry(
                        tenant_id=principal.tenant_id,
                        owner_user_id=principal.user_id,
                        record_id=record_id,
                        action="delete",
                        actor_user_id=principal.user_id,
                        actor_kind="owner",
                        client=client,
                        at=now,
                    )
                ],
                session,
            )

        async with get_client().start_session() as session:
            await session.with_transaction(apply)
        await purge_blob(self._store, storage_key)

    # ── owner: grants ────────────────────────────────────────────────────────────────────────

    async def _remove_from_grant(
        self,
        principal: Principal,
        grant: dict[str, Any],
        record_ids: list[str],
        reason: str,
        now: datetime,
        session: AsyncClientSession,
    ) -> dict[str, Any]:
        """Take records out of a grant; an emptied grant is revoked. Stages the revoked event."""
        removed = [r for r in grant.get("record_ids") or [] if r in set(record_ids)]
        remaining = [r for r in grant.get("record_ids") or [] if r not in set(record_ids)]
        if not removed or grant.get("revoked_at") is not None:
            return grant
        update: dict[str, Any] = {
            "$set": {"record_ids": remaining, "updated_at": now},
            "$addToSet": {"removed_record_ids": {"$each": removed}},
        }
        fully = not remaining
        if fully:
            update["$set"].update({"revoked_at": now, "revoked_reason": reason})
        await _col(GRANTS).update_one({"_id": grant["_id"]}, update, session=session)
        await event_publisher.publish(
            event_type="profile.record_grant_revoked",
            tenant_id=principal.tenant_id,
            payload={
                "grant_id": grant["_id"],
                "user_id": grant["user_id"],
                "grantee_type": grant["grantee_type"],
                "grantee_id": grant["grantee_id"],
                "record_ids": removed,
                "fully_revoked": fully,
                "reason": reason,
                "revoked_at": now.isoformat(),
            },
            actor=EventActor(type="user", id=principal.user_id),
            session=session,
        )
        return {
            **grant,
            "record_ids": remaining,
            "removed_record_ids": [*(grant.get("removed_record_ids") or []), *removed],
            "revoked_at": now if fully else None,
        }

    async def create_grant(
        self, principal: Principal, body: schemas.GrantCreate, client: ClientInfo, *, idempotency_key: str | None
    ) -> schemas.Grant:
        days = body.expires_in_days or settings.records_default_grant_days
        if days > settings.records_max_grant_days:
            raise unprocessable(
                f"expires_in_days can be at most {settings.records_max_grant_days}", "expires_in_days"
            )
        fingerprint = hashlib.sha256(
            "|".join(
                [body.grantee_type, body.grantee_id, ",".join(sorted(body.record_ids)), body.purpose, str(days), body.appointment_id or ""]
            ).encode()
        ).hexdigest()
        replay = await self._replayed(principal, "grant", idempotency_key, fingerprint)
        if replay is not None:
            doc = await _col(GRANTS).find_one({"_id": replay, "tenant_id": principal.tenant_id, "user_id": principal.user_id})
            if doc is not None:
                return _grant_out(doc, utcnow())

        owned = await _col(RECORDS).count_documents(
            {"_id": {"$in": body.record_ids}, "tenant_id": principal.tenant_id, "user_id": principal.user_id}
        )
        if owned != len(body.record_ids):
            # Covers records of other customers and other tenants without revealing which exist.
            raise unprocessable("record_ids must all be your own records", "record_ids", "unknown_record")

        try:
            grantee = await self._directory.grantee(principal.tenant_id, body.grantee_type, body.grantee_id)
        except DirectoryUnavailable as exc:
            raise unavailable("The provider directory is unavailable; try again shortly") from exc
        if grantee is None or grantee.status != "active":
            raise unprocessable("This provider or facility cannot receive records", "grantee_id", "unknown_grantee")

        now = utcnow()
        grant_id = str(ULID())
        doc = {
            "_id": grant_id,
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
            "grantee_type": body.grantee_type,
            "grantee_id": body.grantee_id,
            "grantee_name": grantee.name,
            "record_ids": list(body.record_ids),
            "removed_record_ids": [],
            "purpose": body.purpose,
            "appointment_id": body.appointment_id,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(days=days),
            "revoked_at": None,
            "revoked_reason": None,
        }
        organisation = {"type": body.grantee_type, "id": body.grantee_id, "name": grantee.name}

        async def apply(session: AsyncClientSession) -> None:
            # One active grant per (record, organisation): the new grant supersedes older ones.
            older = await (
                _col(GRANTS)
                .find(
                    {
                        "tenant_id": principal.tenant_id,
                        "user_id": principal.user_id,
                        "grantee_type": body.grantee_type,
                        "grantee_id": body.grantee_id,
                        "revoked_at": None,
                        "record_ids": {"$in": body.record_ids},
                    },
                    session=session,
                )
                .to_list()
            )
            for previous in older:
                await self._remove_from_grant(principal, previous, body.record_ids, "superseded", now, session)
            await _col(GRANTS).insert_one(doc, session=session)
            await self._remember(principal, "grant", idempotency_key, fingerprint, grant_id, session)
            await self._append_log(
                [
                    self._log_entry(
                        tenant_id=principal.tenant_id,
                        owner_user_id=principal.user_id,
                        record_id=record_id,
                        action="grant",
                        actor_user_id=principal.user_id,
                        actor_kind="owner",
                        grant_id=grant_id,
                        organisation=organisation,
                        client=client,
                        at=now,
                    )
                    for record_id in body.record_ids
                ],
                session,
            )
            payload: dict[str, Any] = {
                "grant_id": grant_id,
                "user_id": principal.user_id,
                "grantee_type": body.grantee_type,
                "grantee_id": body.grantee_id,
                "record_ids": list(body.record_ids),
                "purpose": body.purpose,
                "expires_at": doc["expires_at"].isoformat(),
                "created_at": now.isoformat(),
            }
            if body.appointment_id:
                payload["appointment_id"] = body.appointment_id
            await event_publisher.publish(
                event_type="profile.record_grant_created",
                tenant_id=principal.tenant_id,
                payload=payload,
                actor=EventActor(type="user", id=principal.user_id),
                session=session,
            )

        try:
            async with get_client().start_session() as session:
                await session.with_transaction(apply)
        except DuplicateKeyError:
            replay = await self._replayed(principal, "grant", idempotency_key, fingerprint)
            existing = await _col(GRANTS).find_one({"_id": replay}) if replay else None
            if existing is None:
                raise ApiError(status=409, code="conflict", title="Conflict", detail="Grant conflicted") from None
            return _grant_out(existing, utcnow())
        return _grant_out(doc, now)

    async def list_grants(self, principal: Principal, *, record_id: str | None, status: str | None) -> schemas.GrantList:
        query: dict[str, Any] = {"tenant_id": principal.tenant_id, "user_id": principal.user_id}
        if record_id:
            query["$or"] = [{"record_ids": record_id}, {"removed_record_ids": record_id}]
        now = utcnow()
        docs = await _col(GRANTS).find(query).sort([("created_at", -1), ("_id", -1)]).to_list()
        grants = [_grant_out(d, now) for d in docs]
        if status:
            grants = [g for g in grants if g.status == status]
        return schemas.GrantList(data=grants)

    async def revoke_grant(
        self, principal: Principal, grant_id: str, body: schemas.GrantRevoke | None, client: ClientInfo
    ) -> schemas.Grant:
        query = {"_id": grant_id, "tenant_id": principal.tenant_id, "user_id": principal.user_id}
        if await _col(GRANTS).find_one(query) is None:
            raise not_found("Grant")
        now = utcnow()

        async def apply(session: AsyncClientSession) -> dict[str, Any]:
            grant = await _col(GRANTS).find_one(query, session=session)
            if grant is None:
                raise not_found("Grant")
            if grant.get("revoked_at") is not None:
                return grant  # already revoked: idempotent
            targets = list(grant.get("record_ids") or [])
            if body is not None and body.record_ids is not None:
                targets = [r for r in targets if r in set(body.record_ids)]
            if not targets:
                return grant
            updated = await self._remove_from_grant(principal, grant, targets, "owner_revoked", now, session)
            await self._append_log(
                [
                    self._log_entry(
                        tenant_id=principal.tenant_id,
                        owner_user_id=principal.user_id,
                        record_id=record_id,
                        action="revoke",
                        actor_user_id=principal.user_id,
                        actor_kind="owner",
                        grant_id=grant_id,
                        organisation={
                            "type": grant["grantee_type"],
                            "id": grant["grantee_id"],
                            "name": grant.get("grantee_name"),
                        },
                        client=client,
                        at=now,
                    )
                    for record_id in targets
                ],
                session,
            )
            return updated

        async with get_client().start_session() as session:
            await session.with_transaction(apply)
        doc = await _col(GRANTS).find_one(query)
        return _grant_out(doc, utcnow())

    async def access_log(
        self, principal: Principal, *, record_id: str | None, limit: int, cursor: str | None
    ) -> schemas.AccessLogPage:
        query: dict[str, Any] = {"tenant_id": principal.tenant_id, "owner_user_id": principal.user_id}
        if record_id:
            query["record_id"] = record_id
        if cursor:
            query["_id"] = {"$lt": cursor}
        docs = await _col(ACCESS_LOG).find(query).sort("_id", -1).limit(limit + 1).to_list()
        has_more = len(docs) > limit
        docs = docs[:limit]
        entries = [
            schemas.AccessLogEntry(
                id=d["_id"],
                record_id=d["record_id"],
                grant_id=d.get("grant_id"),
                action=d["action"],
                attempted=d.get("attempted"),
                reason=d.get("reason"),
                actor=schemas.AccessActor(kind=d.get("actor_kind") or "other", user_id=d.get("actor_user_id")),
                organisation=schemas.AccessOrganisation(**d["organisation"]) if d.get("organisation") else None,
                client=schemas.AccessClient(**(d.get("client") or {"network": None, "agent": None})),
                occurred_at=_aware(d["occurred_at"]),
            )
            for d in docs
        ]
        return schemas.AccessLogPage(
            data=entries,
            page=schemas.PageMeta(next_cursor=docs[-1]["_id"] if has_more and docs else None, limit=limit, has_more=has_more),
        )

    # ── grantee: shared with me ──────────────────────────────────────────────────────────────

    async def _actor_orgs(self, principal: Principal) -> dict[tuple[str, str], str]:
        actor = await self._directory.actor(principal.tenant_id, principal.user_id)
        return member_organisations(actor)

    async def list_shared(self, principal: Principal, grantee_type: str, grantee_id: str) -> schemas.SharedGrantList:
        try:
            orgs = await self._actor_orgs(principal)
        except DirectoryUnavailable as exc:
            raise unavailable("Membership could not be verified; try again shortly") from exc
        if (grantee_type, grantee_id) not in orgs:
            raise forbidden("You are not a current member of this organisation")
        now = utcnow()
        docs = (
            await _col(GRANTS)
            .find(
                {
                    "tenant_id": principal.tenant_id,
                    "grantee_type": grantee_type,
                    "grantee_id": grantee_id,
                    "revoked_at": None,
                    "expires_at": {"$gt": now},
                }
            )
            .sort([("created_at", -1), ("_id", -1)])
            .to_list()
        )
        return schemas.SharedGrantList(data=[schemas.SharedGrant(**_shared_grant_fields(d)) for d in docs])

    async def view_shared(self, principal: Principal, grant_id: str, client: ClientInfo) -> schemas.SharedGrantDetail:
        grant = await _col(GRANTS).find_one({"_id": grant_id, "tenant_id": principal.tenant_id})
        if grant is None or grant["user_id"] == principal.user_id:
            raise not_found("Shared records")
        every_record = [*(grant.get("record_ids") or []), *(grant.get("removed_record_ids") or [])]
        try:
            orgs = await self._actor_orgs(principal)
        except DirectoryUnavailable as exc:
            await self._log_denied(
                principal, owner_user_id=grant["user_id"], record_ids=every_record, attempted="view",
                reason="verification_unavailable", client=client, grant=grant,
            )
            raise unavailable("Membership could not be verified; try again shortly") from exc
        kind = orgs.get((grant["grantee_type"], grant["grantee_id"]))
        if kind is None:
            await self._log_denied(
                principal, owner_user_id=grant["user_id"], record_ids=every_record, attempted="view",
                reason="not_member", client=client,
            )
            raise not_found("Shared records")
        now = utcnow()
        status = _grant_status(grant, now)
        if status != "active":
            await self._log_denied(
                principal, owner_user_id=grant["user_id"], record_ids=every_record, attempted="view",
                reason=f"grant_{status}", client=client, grant=grant, actor_kind=kind,
            )
            raise forbidden("This share is no longer active")

        records = await (
            _col(RECORDS)
            .find({"_id": {"$in": grant["record_ids"]}, "tenant_id": principal.tenant_id, "user_id": grant["user_id"]})
            .sort([("created_at", -1), ("_id", -1)])
            .to_list()
        )
        await self._record_access(principal, grant, [r["_id"] for r in records], "view", kind, client, now)
        return schemas.SharedGrantDetail(**_shared_grant_fields(grant), records=[_shared_record_out(r) for r in records])

    async def _record_access(
        self,
        principal: Principal,
        grant: dict[str, Any],
        record_ids: list[str],
        action: str,
        actor_kind: str,
        client: ClientInfo,
        now: datetime,
    ) -> None:
        """Log entry and ``profile.record_accessed`` commit together, before any content is returned."""
        organisation = {"type": grant["grantee_type"], "id": grant["grantee_id"], "name": grant.get("grantee_name")}

        async def apply(session: AsyncClientSession) -> None:
            await self._append_log(
                [
                    self._log_entry(
                        tenant_id=principal.tenant_id,
                        owner_user_id=grant["user_id"],
                        record_id=record_id,
                        action=action,
                        actor_user_id=principal.user_id,
                        actor_kind=actor_kind,
                        grant_id=grant["_id"],
                        organisation=organisation,
                        client=client,
                        at=now,
                    )
                    for record_id in record_ids
                ],
                session,
            )
            for record_id in record_ids:
                await event_publisher.publish(
                    event_type="profile.record_accessed",
                    tenant_id=principal.tenant_id,
                    payload={
                        "record_id": record_id,
                        "user_id": grant["user_id"],
                        "grant_id": grant["_id"],
                        "accessor_user_id": principal.user_id,
                        "grantee_type": grant["grantee_type"],
                        "grantee_id": grant["grantee_id"],
                        "action": action,
                        "accessed_at": now.isoformat(),
                    },
                    actor=EventActor(type="user", id=principal.user_id),
                    session=session,
                )

        async with get_client().start_session() as session:
            await session.with_transaction(apply)

    async def _authorise_grantee(
        self, principal: Principal, record: dict[str, Any], attempted: str, client: ClientInfo
    ) -> tuple[dict[str, Any], str]:
        """The active grant that lets this caller read ``record`` and the capacity they act in, or a refusal."""
        record_id, owner = record["_id"], record["user_id"]
        if READ_SHARED_PERMISSION not in principal.permissions:
            await self._log_denied(
                principal, owner_user_id=owner, record_ids=[record_id], attempted=attempted,
                reason="missing_permission", client=client,
            )
            raise not_found()
        grants = await (
            _col(GRANTS)
            .find(
                {
                    "tenant_id": principal.tenant_id,
                    "user_id": owner,
                    "$or": [{"record_ids": record_id}, {"removed_record_ids": record_id}],
                }
            )
            .sort("expires_at", -1)
            .to_list()
        )
        if not grants:
            await self._log_denied(
                principal, owner_user_id=owner, record_ids=[record_id], attempted=attempted, reason="no_grant", client=client
            )
            raise not_found()
        try:
            orgs = await self._actor_orgs(principal)
        except DirectoryUnavailable as exc:
            await self._log_denied(
                principal, owner_user_id=owner, record_ids=[record_id], attempted=attempted,
                reason="verification_unavailable", client=client,
            )
            raise unavailable("Membership could not be verified; try again shortly") from exc
        mine = [g for g in grants if (g["grantee_type"], g["grantee_id"]) in orgs]
        now = utcnow()
        for grant in mine:
            if record_id in (grant.get("record_ids") or []) and _grant_status(grant, now) == "active":
                return grant, orgs[(grant["grantee_type"], grant["grantee_id"])]
        if mine:
            latest = mine[0]
            status = _grant_status(latest, now)
            reason = "grant_expired" if status == "expired" else "grant_revoked"
            await self._log_denied(
                principal, owner_user_id=owner, record_ids=[record_id], attempted=attempted, reason=reason,
                client=client, grant=latest, actor_kind=orgs[(latest["grantee_type"], latest["grantee_id"])],
            )
            raise forbidden("You no longer have access to this record")
        # Not a member of any organisation it was shared with: do not confirm the record exists.
        await self._log_denied(
            principal, owner_user_id=owner, record_ids=[record_id], attempted=attempted, reason="not_member", client=client
        )
        raise not_found()

    # ── content ──────────────────────────────────────────────────────────────────────────────

    async def download(self, principal: Principal, record_id: str, client: ClientInfo) -> RecordContent:
        record = await _col(RECORDS).find_one({"_id": record_id, "tenant_id": principal.tenant_id})
        if record is None:
            raise not_found()
        now = utcnow()
        if record["user_id"] == principal.user_id:
            if MANAGE_PERMISSION not in principal.permissions:
                raise forbidden(f"Missing permission: {MANAGE_PERMISSION}")
            await self._append_log(
                [
                    self._log_entry(
                        tenant_id=principal.tenant_id,
                        owner_user_id=principal.user_id,
                        record_id=record_id,
                        action="download",
                        actor_user_id=principal.user_id,
                        actor_kind="owner",
                        client=client,
                        at=now,
                    )
                ]
            )
        else:
            grant, kind = await self._authorise_grantee(principal, record, "download", client)
            await self._record_access(principal, grant, [record_id], "download", kind, client, now)
        try:
            sealed = await self._store.get(record["file"]["storage_key"])
            data = self._cipher.open(sealed, aad=_aad(record["tenant_id"], record_id))
        except BlobNotFound:
            logger.error("record %s has no stored bytes", record_id)
            raise unavailable("This file is temporarily unavailable") from None
        except DecryptionError as exc:
            logger.error("record %s could not be decrypted: %s", record_id, exc)
            raise unavailable("This file is temporarily unavailable") from None
        return RecordContent(data=data, file_name=record["file"]["name"], content_type=record["file"]["content_type"])


async def purge_blob(store: RecordStore, storage_key: str) -> None:
    """Delete the bytes, then the tombstone; a failure leaves the tombstone for the next sweep."""
    try:
        await store.delete(storage_key)
    except Exception:  # noqa: BLE001 — bytes stay scheduled for deletion and are retried
        logger.exception("could not delete record bytes %s; will retry", storage_key)
        return
    await _col(BLOB_GC).delete_one({"_id": storage_key})


async def purge_pending_blobs(store: RecordStore) -> int:
    """Retry byte deletions that did not complete (called on start-up)."""
    pending = await _col(BLOB_GC).find({}).to_list()
    for tombstone in pending:
        await purge_blob(store, tombstone["_id"])
    return len(pending)


async def erase_user(store: RecordStore, tenant_id: str, user_id: str) -> dict[str, int]:
    """Right to erasure: the user's records, file bytes, grants and their access history.

    Entries where the user appears only as the *accessor* of someone else's record stay (that customer
    keeps their history) with the accessor's user id removed. Idempotent.
    """
    owned = {"tenant_id": tenant_id, "user_id": user_id}
    records = await _col(RECORDS).find(owned).to_list()
    for record in records:
        await _col(BLOB_GC).update_one(
            {"_id": record["file"]["storage_key"]}, {"$setOnInsert": {"created_at": utcnow()}}, upsert=True
        )
    deleted_records = (await _col(RECORDS).delete_many(owned)).deleted_count
    for record in records:
        await purge_blob(store, record["file"]["storage_key"])
    deleted_grants = (await _col(GRANTS).delete_many(owned)).deleted_count
    deleted_log = (await _col(ACCESS_LOG).delete_many({"tenant_id": tenant_id, "owner_user_id": user_id})).deleted_count
    anonymised = (
        await _col(ACCESS_LOG).update_many(
            {"tenant_id": tenant_id, "actor_user_id": user_id}, {"$set": {"actor_user_id": None}}
        )
    ).modified_count
    await _col(IDEMPOTENCY).delete_many(owned)
    return {"records": deleted_records, "grants": deleted_grants, "log": deleted_log, "anonymised": anonymised}
