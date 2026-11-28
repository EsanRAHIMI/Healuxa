"""Application-layer encryption for record files: AES-256-GCM, one random nonce per file.

The sealed blob is self-describing so any storage backend (GridFS today, S3-compatible later) holds
only opaque bytes and key rotation needs no metadata migration::

    b"HXR1" | len(key_id) (1 byte) | key_id (ascii) | nonce (12 bytes) | ciphertext + GCM tag

The additional authenticated data binds a blob to its tenant and record, so ciphertext copied onto
another record fails authentication instead of decrypting.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"HXR1"
NONCE_BYTES = 12
KEY_BYTES = 32
_KEY_ID = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")


class EncryptionUnavailable(RuntimeError):
    """No usable encryption key is configured (records are refused rather than stored in clear)."""


class DecryptionError(RuntimeError):
    """The blob is malformed, was sealed with an unknown key, or failed authentication."""


def _decode_key(value: str, *, name: str) -> bytes:
    try:
        key = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EncryptionUnavailable(f"{name} is not valid base64") from exc
    if len(key) != KEY_BYTES:
        raise EncryptionUnavailable(f"{name} must decode to exactly {KEY_BYTES} bytes")
    return key


@dataclass(frozen=True)
class RecordCipher:
    """Seals with the active key; opens with the active key or any retired key still configured."""

    active_key_id: str
    keys: dict[str, bytes]

    @classmethod
    def from_settings(cls, *, key: str, key_id: str, retired_keys: str = "") -> RecordCipher:
        if not key.strip():
            raise EncryptionUnavailable("RECORDS_ENCRYPTION_KEY is not configured")
        if not _KEY_ID.match(key_id):
            raise EncryptionUnavailable("RECORDS_KEY_ID must be 1-32 characters of [A-Za-z0-9_.-]")
        keys = {key_id: _decode_key(key, name="RECORDS_ENCRYPTION_KEY")}
        for item in (part.strip() for part in retired_keys.split(",")):
            if not item:
                continue
            retired_id, _, retired_value = item.partition(":")
            if not _KEY_ID.match(retired_id) or retired_id in keys:
                raise EncryptionUnavailable("RECORDS_RETIRED_KEYS entries must be unique '<key_id>:<base64 key>'")
            keys[retired_id] = _decode_key(retired_value, name=f"RECORDS_RETIRED_KEYS[{retired_id}]")
        return cls(active_key_id=key_id, keys=keys)

    def seal(self, plaintext: bytes, *, aad: bytes) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        key_id = self.active_key_id.encode("ascii")
        ciphertext = AESGCM(self.keys[self.active_key_id]).encrypt(nonce, plaintext, aad)
        return MAGIC + bytes([len(key_id)]) + key_id + nonce + ciphertext

    @staticmethod
    def key_id_of(blob: bytes) -> str:
        if len(blob) < len(MAGIC) + 1 or not blob.startswith(MAGIC):
            raise DecryptionError("not a sealed record blob")
        size = blob[len(MAGIC)]
        start = len(MAGIC) + 1
        try:
            return blob[start : start + size].decode("ascii")
        except UnicodeDecodeError as exc:
            raise DecryptionError("not a sealed record blob") from exc

    def open(self, blob: bytes, *, aad: bytes) -> bytes:
        key_id = self.key_id_of(blob)
        key = self.keys.get(key_id)
        if key is None:
            raise DecryptionError(f"record was sealed with key {key_id!r}, which is not configured")
        offset = len(MAGIC) + 1 + len(key_id)
        nonce, ciphertext = blob[offset : offset + NONCE_BYTES], blob[offset + NONCE_BYTES :]
        if len(nonce) != NONCE_BYTES:
            raise DecryptionError("truncated record blob")
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise DecryptionError("record blob failed authentication") from exc
