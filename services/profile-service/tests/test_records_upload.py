"""Records: upload validation, encryption at rest, owner-only management, deletion, idempotency."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from profile_service.api.records import get_cipher
from profile_service.config import settings
from profile_service.infra.crypto import DecryptionError, RecordCipher
from profile_service.infra.mongo import get_database
from profile_service.main import app
from records_helpers import JPEG, PDF, PNG, access_log, customer, new_id, ok, platform_admin, upload, uploaded

pytestmark = pytest.mark.mongo


async def test_upload_list_download_roundtrip(client: AsyncClient, directory) -> None:
    owner = new_id()
    record = await uploaded(
        client,
        customer(owner),
        extra={"document_date": "2026-03-02", "note": "Fasting sample"},
    )
    assert record["type"] == "lab_result" and record["title"] == "Blood panel March"
    assert record["document_date"] == "2026-03-02" and record["note"] == "Fasting sample"
    assert record["content_type"] == "application/pdf" and record["size_bytes"] == len(PDF)
    assert record["file_name"] == "blood-test.pdf" and record["shares"] == []

    listing = await ok(await client.get("/v1/records", headers=customer(owner)))
    assert [r["id"] for r in listing["data"]] == [record["id"]]
    assert listing["usage"]["record_count"] == 1 and listing["usage"]["total_bytes"] == len(PDF)

    download = await client.get(f"/v1/records/{record['id']}/content", headers=customer(owner))
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["content-disposition"].startswith('attachment; filename="blood-test.pdf"')
    assert download.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in download.headers["cache-control"]
    assert [e["action"] for e in await access_log(owner)] == ["download"]


@pytest.mark.parametrize(
    ("data", "filename", "content_type", "code"),
    [
        (b"MZ\x90\x00 this is an executable", "lab.pdf", "application/pdf", "unsupported_type"),
        (b"<html><script>alert(1)</script></html>", "report.pdf", "application/pdf", "unsupported_type"),
        (b"GIF89a" + b"\x00" * 32, "scan.png", "image/png", "unsupported_type"),
        (PNG, "scan.pdf", "image/png", "type_mismatch"),
        (PDF, "report.pdf", "image/png", "type_mismatch"),
        (JPEG, "photo.png", "image/jpeg", "type_mismatch"),
        (b"", "empty.pdf", "application/pdf", "empty"),
    ],
)
async def test_upload_rejects_by_magic_bytes(client: AsyncClient, directory, data, filename, content_type, code) -> None:
    owner = new_id()
    response = await upload(client, customer(owner), data=data, filename=filename, content_type=content_type)
    assert response.status_code == 422, response.text
    assert response.json()["errors"][0]["code"] == code
    assert await get_database()["medical_records"].count_documents({}) == 0
    assert await get_database()["record_files.files"].count_documents({}) == 0


async def test_generic_content_type_is_accepted_when_bytes_are_valid(client: AsyncClient, directory) -> None:
    record = await uploaded(client, customer(new_id()), data=PNG, filename="x-ray", content_type="application/octet-stream")
    assert record["content_type"] == "image/png" and record["file_name"] == "x-ray.png"


async def test_upload_rejects_oversize(client: AsyncClient, directory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "records_max_file_bytes", 1024)
    big = PDF + b"0" * 2048
    response = await upload(client, customer(new_id()), data=big)
    assert response.status_code == 413, response.text
    assert response.json()["errors"][0]["code"] == "too_large"
    # Body far above the cap is refused on Content-Length before it is read.
    huge = await upload(client, customer(new_id()), data=PDF + b"0" * (200 * 1024))
    assert huge.status_code == 413


async def test_upload_validates_fields(client: AsyncClient, directory) -> None:
    owner = customer(new_id())
    bad_type = await upload(client, owner, record_type="x_ray_selfie")
    assert bad_type.status_code == 422 and bad_type.json()["errors"][0]["field"] == "type"
    no_title = await upload(client, owner, title="  ")
    assert no_title.status_code == 422 and no_title.json()["errors"][0]["field"] == "title"
    future = await upload(client, owner, extra={"document_date": "2999-01-01"})
    assert future.status_code == 422 and future.json()["errors"][0]["field"] == "document_date"
    not_multipart = await client.post("/v1/records", headers=owner, json={"title": "x"})
    assert not_multipart.status_code == 422
    no_file = await client.post("/v1/records", headers=owner, data={"title": "x", "type": "other"}, files={"other": ("a", b"b")})
    assert no_file.status_code == 422


async def test_filename_is_sanitised(client: AsyncClient, directory) -> None:
    record = await uploaded(client, customer(new_id()), filename='../../etc/pass"wd\r\nX-Evil: 1;.pdf')
    assert "/" not in record["file_name"] and "\r" not in record["file_name"] and '"' not in record["file_name"]
    assert record["file_name"].endswith(".pdf")
    nameless = await uploaded(client, customer(new_id()), filename="....pdf")
    assert nameless["file_name"] == "document.pdf"


async def test_bytes_are_encrypted_at_rest_and_wrong_key_fails(client: AsyncClient, directory) -> None:
    owner = new_id()
    record = await uploaded(client, customer(owner))
    meta = await get_database()["medical_records"].find_one({"_id": record["id"]})
    assert meta["file"]["key_id"] == "t1"
    chunks = await get_database()["record_files.chunks"].find({}).to_list()
    stored = b"".join(bytes(c["data"]) for c in sorted(chunks, key=lambda c: c["n"]))
    assert stored != PDF
    assert b"Haemoglobin" not in stored and b"%PDF" not in stored
    assert stored.startswith(b"HXR1")
    assert RecordCipher.key_id_of(stored) == "t1"

    right = get_cipher()
    assert right.open(stored, aad=f"{meta['tenant_id']}:{record['id']}".encode()) == PDF
    with pytest.raises(DecryptionError):
        right.open(stored, aad=f"{meta['tenant_id']}:{new_id()}".encode())  # bound to its record
    wrong = RecordCipher.from_settings(key="d3JvbmctcmVjb3Jkcy1rZXktZm9yLXRlc3RzLTMyYiE=", key_id="t1")
    with pytest.raises(DecryptionError):
        wrong.open(stored, aad=f"{meta['tenant_id']}:{record['id']}".encode())

    app.dependency_overrides[get_cipher] = lambda: wrong
    try:
        response = await client.get(f"/v1/records/{record['id']}/content", headers=customer(owner))
    finally:
        app.dependency_overrides.pop(get_cipher, None)
    assert response.status_code == 503
    assert b"Haemoglobin" not in response.content


async def test_key_rotation_keeps_old_files_readable(client: AsyncClient, directory, monkeypatch) -> None:
    owner = new_id()
    old = await uploaded(client, customer(owner))
    old_key = settings.records_encryption_key
    monkeypatch.setattr(settings, "records_encryption_key", "bmV3LWFjdGl2ZS1yZWNvcmRzLWtleS0zMi1ieXRlcyE=")
    monkeypatch.setattr(settings, "records_key_id", "t2")
    monkeypatch.setattr(settings, "records_retired_keys", f"t1:{old_key}")
    new = await uploaded(client, customer(owner), data=PNG, filename="scan.png", content_type="image/png")
    assert (await get_database()["medical_records"].find_one({"_id": new["id"]}))["file"]["key_id"] == "t2"
    assert (await client.get(f"/v1/records/{old['id']}/content", headers=customer(owner))).content == PDF
    assert (await client.get(f"/v1/records/{new['id']}/content", headers=customer(owner))).content == PNG


async def test_records_refused_without_encryption_key(client: AsyncClient, directory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "records_encryption_key", "")
    response = await upload(client, customer(new_id()))
    assert response.status_code == 503
    assert await get_database()["record_files.files"].count_documents({}) == 0


async def test_only_the_owner_manages_a_record(client: AsyncClient, directory) -> None:
    owner, stranger = new_id(), new_id()
    record = await uploaded(client, customer(owner))
    rid = record["id"]
    for method, path, kwargs in (
        ("GET", f"/v1/records/{rid}", {}),
        ("PATCH", f"/v1/records/{rid}", {"json": {"title": "mine now"}}),
        ("DELETE", f"/v1/records/{rid}", {}),
        ("GET", f"/v1/records/{rid}/content", {}),
    ):
        for headers in (customer(stranger), platform_admin(new_id()), customer(owner, tenant_id="other-tenant")):
            response = await client.request(method, path, headers=headers, **kwargs)
            assert response.status_code == 404, (method, path, response.text)
    assert (await ok(await client.get("/v1/records", headers=customer(stranger))))["data"] == []
    still = await ok(await client.get(f"/v1/records/{rid}", headers=customer(owner)))
    assert still["title"] == "Blood panel March"
    # Without the permission at all, the API refuses before any lookup.
    from profile_service.api.deps import principal_headers

    assert (await client.get("/v1/records", headers=principal_headers(owner, permissions="profiles:read"))).status_code == 403
    assert (await client.get("/v1/records")).status_code == 401


async def test_owner_updates_metadata(client: AsyncClient, directory) -> None:
    owner = new_id()
    record = await uploaded(client, customer(owner))
    updated = await ok(
        await client.patch(
            f"/v1/records/{record['id']}",
            headers=customer(owner),
            json={"title": "CBC — March", "type": "other", "note": None, "document_date": "2026-03-01"},
        )
    )
    assert updated["title"] == "CBC — March" and updated["type"] == "other" and updated["document_date"] == "2026-03-01"
    rejected = await client.patch(f"/v1/records/{record['id']}", headers=customer(owner), json={"user_id": "x"})
    assert rejected.status_code == 422


async def test_delete_really_deletes_bytes(client: AsyncClient, directory) -> None:
    owner = new_id()
    record = await uploaded(client, customer(owner))
    assert await get_database()["record_files.chunks"].count_documents({}) >= 1
    response = await client.delete(f"/v1/records/{record['id']}", headers=customer(owner))
    assert response.status_code == 204
    assert await get_database()["medical_records"].count_documents({}) == 0
    assert await get_database()["record_files.files"].count_documents({}) == 0
    assert await get_database()["record_files.chunks"].count_documents({}) == 0
    assert await get_database()["record_blob_gc"].count_documents({}) == 0
    assert (await client.get(f"/v1/records/{record['id']}/content", headers=customer(owner))).status_code == 404
    assert [e["action"] for e in await access_log(owner)] == ["delete"]


async def test_pending_byte_deletion_is_retried(client: AsyncClient, directory) -> None:
    from profile_service.domain.records import purge_pending_blobs
    from profile_service.infra.storage import GridFSRecordStore

    store = GridFSRecordStore(get_database())
    await store.put("healuxa-dubai/orphan/1", b"HXR1sealed")
    await get_database()["record_blob_gc"].insert_one({"_id": "healuxa-dubai/orphan/1"})
    assert await purge_pending_blobs(store) == 1
    assert await get_database()["record_files.files"].count_documents({}) == 0
    assert await get_database()["record_blob_gc"].count_documents({}) == 0


async def test_soft_limits_per_user(client: AsyncClient, directory, monkeypatch) -> None:
    owner = customer(new_id())
    monkeypatch.setattr(settings, "records_max_per_user", 2)
    await uploaded(client, owner)
    await uploaded(client, owner)
    third = await upload(client, owner)
    assert third.status_code == 422 and third.json()["errors"][0]["code"] == "record_limit"
    monkeypatch.setattr(settings, "records_max_per_user", 50)
    monkeypatch.setattr(settings, "records_max_total_bytes_per_user", len(PDF) * 2 + 10)
    full = await upload(client, owner)
    assert full.status_code == 422 and full.json()["errors"][0]["code"] == "storage_limit"


async def test_upload_idempotency(client: AsyncClient, directory) -> None:
    owner = customer(new_id())
    keyed = {**owner, "Idempotency-Key": "upload-key-0001"}
    first = await uploaded(client, keyed)
    again = await uploaded(client, keyed)
    assert again["id"] == first["id"]
    assert await get_database()["medical_records"].count_documents({}) == 1
    assert await get_database()["record_files.files"].count_documents({}) == 1
    different = await upload(client, keyed, title="Another document")
    assert different.status_code == 409 and different.json()["code"] == "idempotency_conflict"
