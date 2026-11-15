"""Upload validation: the file's real type comes from its leading bytes, never from what the client says."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from healuxa_py_common.errors import ApiError, FieldError


@dataclass(frozen=True)
class FileKind:
    content_type: str
    extension: str


PDF = FileKind("application/pdf", "pdf")
JPEG = FileKind("image/jpeg", "jpg")
PNG = FileKind("image/png", "png")
ALLOWED_CONTENT_TYPES = {k.content_type: k for k in (PDF, JPEG, PNG)}
_CLAIMED_ALIASES = {"image/jpg": "image/jpeg", "image/pjpeg": "image/jpeg", "application/x-pdf": "application/pdf"}
_EXTENSIONS = {"pdf": PDF, "jpg": JPEG, "jpeg": JPEG, "png": PNG}


def sniff(head: bytes) -> FileKind | None:
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    return None


def invalid_file(code: str, message: str, *, status: int = 422) -> ApiError:
    return ApiError(
        status=status,
        code="validation_error" if status == 413 else "unprocessable",
        title="Payload too large" if status == 413 else "Unprocessable",
        detail=message,
        errors=[FieldError(field="file", code=code, message=message)],
    )


def validate_upload(data: bytes, *, claimed_content_type: str | None, filename: str | None, max_bytes: int) -> FileKind:
    if not data:
        raise invalid_file("empty", "The file is empty")
    if len(data) > max_bytes:
        raise invalid_file("too_large", f"The file is larger than {max_bytes // (1024 * 1024)} MB", status=413)
    kind = sniff(data[:16])
    if kind is None:
        raise invalid_file("unsupported_type", "Only PDF, JPEG and PNG files are accepted")
    claimed = (claimed_content_type or "").split(";")[0].strip().lower()
    claimed = _CLAIMED_ALIASES.get(claimed, claimed)
    # A browser may send a generic type; a specific type that contradicts the bytes is refused.
    if claimed and claimed != "application/octet-stream" and claimed != kind.content_type:
        raise invalid_file("type_mismatch", "The file content does not match its declared type")
    extension = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if extension and _EXTENSIONS.get(extension) is not kind:
        raise invalid_file("type_mismatch", "The file content does not match its extension")
    return kind


_UNSAFE = re.compile(r"[^\w .()\-]+", re.UNICODE)


def sanitise_filename(name: str | None, kind: FileKind) -> str:
    """A display/download name with no path, control or header-breaking characters and a truthful extension."""
    raw = unicodedata.normalize("NFKC", name or "")
    raw = raw.replace("\\", "/").rsplit("/", 1)[-1]
    raw = "".join(ch for ch in raw if unicodedata.category(ch)[0] != "C")
    stem = raw.rsplit(".", 1)[0] if "." in raw else raw
    stem = _UNSAFE.sub("_", stem).strip(" ._")
    stem = re.sub(r"[\s_]{2,}", "_", stem)[:80].strip(" ._")
    return f"{stem or 'document'}.{kind.extension}"
