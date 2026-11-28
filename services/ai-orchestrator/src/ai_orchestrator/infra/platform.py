"""Read access to the verified platform data the assistant is grounded in (plus the concierge hand-off).

Every call is made with the caller's own bearer token (or anonymously for public catalog reads), so
the owning services apply their normal permission and ownership rules. Nothing is cached across
users. Responses are returned raw; projection to the minimum the model needs happens in tools.py.
"""

from __future__ import annotations

from typing import Any

import httpx

from ai_orchestrator.config import settings


class PlatformError(Exception):
    """A platform read failed; ``code`` is safe to show to the model (no payloads, no ids)."""

    def __init__(self, code: str, status: int | None = None) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


def _code_for(status: int) -> str:
    if status == 404:
        return "not_found"
    if status in (401, 403):
        return "not_permitted"
    if status == 422:
        return "invalid_request"
    if status == 429:
        return "busy"
    return "unavailable"


class PlatformClient:
    def __init__(self, *, token: str | None, trace_id: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        headers = {"Accept": "application/json"}
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        self._token = token
        self._client = httpx.AsyncClient(timeout=settings.tool_timeout_seconds, headers=headers, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        auth: bool,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = dict(headers or {})
        if auth:
            if not self._token:
                raise PlatformError("not_permitted")
            request_headers["Authorization"] = f"Bearer {self._token}"
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        try:
            response = await self._client.request(method, url, params=clean, json=json, headers=request_headers)
        except httpx.HTTPError:
            raise PlatformError("unavailable") from None
        if response.status_code >= 400:
            raise PlatformError(_code_for(response.status_code), response.status_code)
        try:
            return response.json()
        except ValueError:
            raise PlatformError("unavailable") from None

    # ── provider-service: public directory and catalog (anonymous → only verified, bookable data) ──
    async def list_services(self, *, category: str | None, provider_id: str | None, facility_id: str | None, limit: int) -> list[dict]:
        body = await self._request(
            "GET",
            f"{settings.provider_api_url}/services",
            auth=False,
            params={"category": category, "provider_id": provider_id, "facility_id": facility_id, "limit": limit},
        )
        return list(body.get("data") or [])

    async def get_service(self, service_id: str) -> dict:
        return await self._request("GET", f"{settings.provider_api_url}/services/{service_id}", auth=False)

    async def search_providers(self, *, specialty: str | None, language: str | None, city: str | None, type_: str | None, limit: int) -> list[dict]:
        body = await self._request(
            "GET",
            f"{settings.provider_api_url}/providers",
            auth=False,
            params={"specialty": specialty, "language": language, "city": city, "type": type_, "limit": limit},
        )
        return list(body.get("data") or [])

    async def get_provider(self, provider_id: str) -> dict:
        return await self._request("GET", f"{settings.provider_api_url}/providers/{provider_id}", auth=False)

    async def search_facilities(self, *, city: str | None, type_: str | None, limit: int) -> list[dict]:
        body = await self._request(
            "GET", f"{settings.provider_api_url}/facilities", auth=False, params={"city": city, "type": type_, "limit": limit}
        )
        return list(body.get("data") or [])

    async def get_facility(self, facility_id: str) -> dict:
        return await self._request("GET", f"{settings.provider_api_url}/facilities/{facility_id}", auth=False)

    # ── appointment-service ──
    async def list_slots(self, service_id: str, *, date_from: str, date_to: str) -> dict:
        return await self._request(
            "GET",
            f"{settings.appointment_api_url}/services/{service_id}/slots",
            auth=False,
            params={"from": date_from, "to": date_to},
        )

    async def list_my_appointments(self, *, user_id: str, date_from: str, limit: int) -> list[dict]:
        body = await self._request(
            "GET",
            f"{settings.appointment_api_url}/appointments",
            auth=True,
            params={"user_id": user_id, "from": date_from, "sort": "scheduled_at", "limit": limit},
        )
        return list(body.get("data") or [])

    # ── transformation-engine ──
    async def get_journey(self, user_id: str) -> dict:
        return await self._request("GET", f"{settings.transformation_api_url}/journeys/{user_id}", auth=True)

    async def get_roadmap(self, journey_id: str) -> dict:
        return await self._request("GET", f"{settings.transformation_api_url}/journeys/{journey_id}/roadmap", auth=True)

    async def get_next_actions(self, journey_id: str) -> list[dict]:
        body = await self._request("GET", f"{settings.transformation_api_url}/journeys/{journey_id}/next-actions", auth=True)
        return list(body or [])

    # ── concierge-service: the only write the assistant can make (hand-off to a human) ──
    async def create_concierge_case(self, *, category: str, language: str, idempotency_key: str) -> dict:
        return await self._request(
            "POST",
            f"{settings.concierge_api_url}/concierge/cases",
            auth=True,
            json={"category": category, "languages": [language], "needs_note": "Requested from the Healuxa assistant."},
            headers={"Idempotency-Key": idempotency_key},
        )

    async def get_concierge_case(self, case_id: str) -> dict:
        return await self._request("GET", f"{settings.concierge_api_url}/concierge/cases/{case_id}", auth=True)
