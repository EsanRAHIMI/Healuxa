"""Medical records API: customer-owned documents, consent grants, access log, shared-with-me reads."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal

from profile_service.api.deps import resolve_principal
from profile_service.api.multipart import FORM_OVERHEAD_BYTES, parse_multipart, read_bounded_body
from profile_service.clients.organisations import HttpOrganisationDirectory, OrganisationDirectory, ServiceTokenSource
from profile_service.config import settings
from profile_service.domain import record_schemas as schemas
from profile_service.domain.client_info import client_info
from profile_service.domain.files import invalid_file
from profile_service.domain.records import (
    MANAGE_PERMISSION,
    READ_SHARED_PERMISSION,
    RecordsService,
    Upload,
    unavailable,
    unprocessable,
)
from profile_service.infra.crypto import EncryptionUnavailable, RecordCipher
from profile_service.infra.mongo import get_database
from profile_service.infra.storage import GridFSRecordStore, RecordStore

router = APIRouter(tags=["records"])

_directory: HttpOrganisationDirectory | None = None
_http: httpx.AsyncClient | None = None


def get_directory() -> OrganisationDirectory:
    """provider-service client (one shared connection pool); tests override this dependency."""
    global _directory, _http
    if _directory is None:
        _http = httpx.AsyncClient(timeout=settings.provider_timeout_seconds)
        _directory = HttpOrganisationDirectory(
            client=_http,
            base_url=settings.provider_service_url,
            tokens=ServiceTokenSource(
                client=_http,
                token_url=settings.identity_service_token_url,
                client_id=settings.service_auth_client_id or "",
                client_secret=settings.service_auth_client_secret or "",
            ),
        )
    return _directory


async def close_directory() -> None:
    global _directory, _http
    http, _http, _directory = _http, None, None
    if http is not None:
        await http.aclose()


def get_store() -> RecordStore:
    return GridFSRecordStore(get_database())


def get_cipher() -> RecordCipher:
    try:
        return RecordCipher.from_settings(
            key=settings.records_encryption_key,
            key_id=settings.records_key_id,
            retired_keys=settings.records_retired_keys,
        )
    except EncryptionUnavailable as exc:
        # Never store or serve records without encryption configured.
        raise unavailable("Records are not available right now") from exc


def get_records_service(
    store: RecordStore = Depends(get_store),
    cipher: RecordCipher = Depends(get_cipher),
    directory: OrganisationDirectory = Depends(get_directory),
) -> RecordsService:
    return RecordsService(store=store, cipher=cipher, directory=directory)


def _require(*permissions: str):
    def dependency(principal: Principal = Depends(resolve_principal)) -> Principal:
        if not any(p in principal.permissions for p in permissions):
            raise ApiError(
                status=403, code="forbidden", title="Forbidden", detail="Missing permission: " + " or ".join(permissions)
            )
        return principal

    return dependency


Owner = Annotated[Principal, Depends(_require(MANAGE_PERMISSION))]
SharedReader = Annotated[Principal, Depends(_require(READ_SHARED_PERMISSION))]
AnyReader = Annotated[Principal, Depends(_require(MANAGE_PERMISSION, READ_SHARED_PERMISSION))]
Service = Annotated[RecordsService, Depends(get_records_service)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
RecordId = Annotated[str, Query(min_length=10, max_length=36)]


def _field(form_fields: dict[str, str], name: str, *, required: bool, max_length: int) -> str | None:
    value = (form_fields.get(name) or "").strip()
    if not value:
        if required:
            raise unprocessable(f"{name} is required", name, "required")
        return None
    if len(value) > max_length:
        raise unprocessable(f"{name} can be at most {max_length} characters", name, "too_long")
    return value


@router.post("/v1/records", status_code=201, operation_id="uploadRecord")
async def upload_record(
    request: Request, principal: Owner, service: Service, response: Response, idempotency_key: IdempotencyKey = None
) -> schemas.Record:
    body = await read_bounded_body(request, settings.records_max_file_bytes + FORM_OVERHEAD_BYTES)
    form = parse_multipart(request.headers.get("content-type"), body)
    part = form.files.get("file")
    if part is None:
        raise invalid_file("required", "A file is required")
    title = _field(form.fields, "title", required=True, max_length=160)
    record_type = _field(form.fields, "type", required=True, max_length=40)
    if record_type not in schemas.RECORD_TYPES:
        raise unprocessable("Unknown record type", "type")
    note = _field(form.fields, "note", required=False, max_length=1000)
    raw_date = _field(form.fields, "document_date", required=False, max_length=10)
    document_date: date | None = None
    if raw_date:
        try:
            document_date = date.fromisoformat(raw_date)
        except ValueError:
            raise unprocessable("document_date must be YYYY-MM-DD", "document_date") from None
        if document_date > date.today() or document_date.year < 1900:
            raise unprocessable("document_date must be a past date", "document_date")
    record = await service.upload(
        principal,
        Upload(
            data=bytes(part.data),
            filename=part.filename,
            content_type=part.content_type,
            title=title or "",
            type=record_type,
            document_date=document_date,
            note=note,
        ),
        idempotency_key=idempotency_key,
    )
    response.headers["Location"] = f"/v1/records/{record.id}"
    return record


@router.get("/v1/records", operation_id="listRecords")
async def list_records(principal: Owner, service: Service) -> schemas.RecordList:
    return await service.list_records(principal)


@router.get("/v1/records/{record_id}", operation_id="getRecord")
async def get_record(principal: Owner, service: Service, record_id: str) -> schemas.Record:
    return await service.get_record(principal, record_id)


@router.patch("/v1/records/{record_id}", operation_id="updateRecord")
async def update_record(principal: Owner, service: Service, record_id: str, body: schemas.RecordUpdate) -> schemas.Record:
    return await service.update_record(principal, record_id, body)


@router.delete("/v1/records/{record_id}", status_code=204, operation_id="deleteRecord")
async def delete_record(request: Request, principal: Owner, service: Service, record_id: str) -> Response:
    await service.delete_record(principal, record_id, client_info(request))
    return Response(status_code=204)


@router.get("/v1/records/{record_id}/content", operation_id="downloadRecord")
async def download_record(request: Request, principal: AnyReader, service: Service, record_id: str) -> Response:
    """The owner, or a grantee with an active grant. Always an attachment, never rendered inline."""
    content = await service.download(principal, record_id, client_info(request))
    ascii_name = content.file_name.encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    return Response(
        content=content.data,
        media_type=content.content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(content.file_name)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post("/v1/record-grants", status_code=201, operation_id="createRecordGrant")
async def create_grant(
    request: Request,
    principal: Owner,
    service: Service,
    body: schemas.GrantCreate,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> schemas.Grant:
    grant = await service.create_grant(principal, body, client_info(request), idempotency_key=idempotency_key)
    response.headers["Location"] = f"/v1/record-grants/{grant.id}"
    return grant


@router.get("/v1/record-grants", operation_id="listRecordGrants")
async def list_grants(
    principal: Owner,
    service: Service,
    record_id: Annotated[str | None, Query(min_length=10, max_length=36)] = None,
    status: schemas.GrantStatus | None = None,
) -> schemas.GrantList:
    return await service.list_grants(principal, record_id=record_id, status=status)


@router.post("/v1/record-grants/{grant_id}/revoke", operation_id="revokeRecordGrant")
async def revoke_grant(
    request: Request, principal: Owner, service: Service, grant_id: str, body: schemas.GrantRevoke | None = None
) -> schemas.Grant:
    return await service.revoke_grant(principal, grant_id, body, client_info(request))


@router.get("/v1/record-access-log", operation_id="listRecordAccessLog")
async def access_log(
    principal: Owner,
    service: Service,
    record_id: Annotated[str | None, Query(min_length=10, max_length=36)] = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Annotated[str | None, Query(max_length=36)] = None,
) -> schemas.AccessLogPage:
    return await service.access_log(principal, record_id=record_id, limit=limit, cursor=cursor)


@router.get("/v1/shared-records", operation_id="listSharedRecords")
async def list_shared(
    principal: SharedReader,
    service: Service,
    grantee_type: Literal["provider", "facility"],
    grantee_id: RecordId,
) -> schemas.SharedGrantList:
    return await service.list_shared(principal, grantee_type, grantee_id)


@router.get("/v1/shared-records/{grant_id}", operation_id="getSharedRecords")
async def view_shared(request: Request, principal: SharedReader, service: Service, grant_id: str) -> schemas.SharedGrantDetail:
    return await service.view_shared(principal, grant_id, client_info(request))

