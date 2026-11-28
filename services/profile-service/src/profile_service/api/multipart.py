"""Bounded, in-memory multipart parsing for record uploads.

Starlette's form parser spools file parts to a temporary file on disk, which would put an unencrypted
medical document on the container filesystem. Record uploads are small (hard cap, default 10 MB), so
the request is read into memory under a strict byte limit and parsed there; nothing is written to
disk before encryption.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request
from healuxa_py_common.errors import ApiError
from python_multipart.multipart import MultipartParser, parse_options_header

from profile_service.domain.files import invalid_file

# Room for the text fields and multipart framing on top of the file itself.
FORM_OVERHEAD_BYTES = 64 * 1024
MAX_PARTS = 12
MAX_FIELD_BYTES = 8 * 1024


@dataclass
class Part:
    name: str = ""
    filename: str | None = None
    content_type: str | None = None
    data: bytearray = field(default_factory=bytearray)


@dataclass
class ParsedForm:
    fields: dict[str, str]
    files: dict[str, Part]


def _bad_request(detail: str) -> ApiError:
    return ApiError(status=422, code="unprocessable", title="Unprocessable", detail=detail)


async def read_bounded_body(request: Request, max_bytes: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > max_bytes:
                raise invalid_file("too_large", "The upload is too large", status=413)
        except ValueError:
            raise _bad_request("Invalid Content-Length") from None
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:  # chunked uploads have no declared length; stop reading at the cap
            raise invalid_file("too_large", "The upload is too large", status=413)
    return bytes(body)


def parse_multipart(content_type_header: str | None, body: bytes) -> ParsedForm:
    content_type, options = parse_options_header(content_type_header or "")
    boundary = options.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary:
        raise _bad_request("Expected multipart/form-data")

    parts: list[Part] = []
    state: dict[str, bytearray] = {"field": bytearray(), "value": bytearray()}
    headers: list[tuple[bytes, bytes]] = []

    def on_part_begin() -> None:
        if len(parts) >= MAX_PARTS:
            raise _bad_request("Too many form parts")
        parts.append(Part())
        headers.clear()

    def on_header_field(data: bytes, start: int, end: int) -> None:
        state["field"].extend(data[start:end])

    def on_header_value(data: bytes, start: int, end: int) -> None:
        state["value"].extend(data[start:end])

    def on_header_end() -> None:
        headers.append((bytes(state["field"]).lower(), bytes(state["value"])))
        state["field"], state["value"] = bytearray(), bytearray()

    def on_headers_finished() -> None:
        part = parts[-1]
        for name, value in headers:
            if name == b"content-disposition":
                _, params = parse_options_header(value)
                part.name = params.get(b"name", b"").decode("utf-8", "replace")
                if b"filename" in params:
                    part.filename = params[b"filename"].decode("utf-8", "replace")
            elif name == b"content-type":
                part.content_type = value.decode("latin-1")

    def on_part_data(data: bytes, start: int, end: int) -> None:
        part = parts[-1]
        part.data.extend(data[start:end])
        if part.filename is None and len(part.data) > MAX_FIELD_BYTES:
            raise _bad_request("A form field is too long")

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
        },
    )
    try:
        parser.write(body)
        parser.finalize()
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 — any parser error is a malformed request
        raise _bad_request("Malformed multipart body") from exc

    form = ParsedForm(fields={}, files={})
    for part in parts:
        if not part.name:
            continue
        if part.filename is None:
            try:
                form.fields[part.name] = bytes(part.data).decode("utf-8")
            except UnicodeDecodeError:
                raise _bad_request("Form fields must be UTF-8") from None
        elif part.name in form.files:
            raise _bad_request("Only one file per upload")
        else:
            form.files[part.name] = part
    return form
