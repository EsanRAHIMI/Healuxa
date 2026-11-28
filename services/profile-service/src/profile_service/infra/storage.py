"""Byte storage for record files behind a small port.

``RecordStore`` only ever sees sealed (encrypted) blobs addressed by an opaque key, so replacing the
GridFS implementation with an S3-compatible one is a constructor change: no caller knows where bytes
live, and nothing here is publicly addressable.
"""

from __future__ import annotations

from typing import Protocol

from gridfs import AsyncGridFSBucket
from gridfs.errors import NoFile
from pymongo.asynchronous.database import AsyncDatabase

BUCKET_NAME = "record_files"


class BlobNotFound(LookupError):
    pass


class RecordStore(Protocol):
    async def put(self, key: str, blob: bytes) -> None:
        """Store a sealed blob under ``key`` (keys are never reused)."""

    async def get(self, key: str) -> bytes:
        """Return the sealed blob, or raise ``BlobNotFound``."""

    async def delete(self, key: str) -> None:
        """Remove the blob; deleting a missing key is a no-op (idempotent)."""


class GridFSRecordStore:
    """MongoDB GridFS: chunks live in ``record_files.chunks`` of the service's own database."""

    def __init__(self, database: AsyncDatabase) -> None:
        self._bucket = AsyncGridFSBucket(database, bucket_name=BUCKET_NAME)

    async def put(self, key: str, blob: bytes) -> None:
        await self._bucket.upload_from_stream_with_id(key, key, blob)

    async def get(self, key: str) -> bytes:
        try:
            stream = await self._bucket.open_download_stream(key)
        except NoFile as exc:
            raise BlobNotFound(key) from exc
        return await stream.read()

    async def delete(self, key: str) -> None:
        try:
            await self._bucket.delete(key)
        except NoFile:
            return
