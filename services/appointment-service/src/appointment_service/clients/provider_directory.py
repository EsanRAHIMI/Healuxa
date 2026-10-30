"""Read access to provider-service — the single source of availability facts.

Design: synchronous HTTP with short timeouts, authenticated with a service token from identity-service
(client-credentials). Anything other than a clean answer raises ``ProviderUnavailable`` and the API
returns 503: the booking engine never invents availability. ``ProviderDirectory`` is a protocol so tests
(and a future event-fed read model) can supply another implementation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, date, datetime
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ProviderUnavailable(Exception):
    """provider-service (or the token issuer) could not give a trustworthy answer."""


class Offering(BaseModel):
    id: str
    provider_id: str
    facility_id: str
    branch_id: str
    name: str
    category: str
    duration_minutes: int
    buffer_minutes: int
    mode: str
    status: str
    price_type: str
    professional_fee_minor: int | None = None
    facility_fee_minor: int | None = None
    currency: str

    @property
    def price_minor(self) -> int | None:
        if self.price_type == "on_request":
            return None
        return (self.professional_fee_minor or 0) + (self.facility_fee_minor or 0)


class ProviderRef(BaseModel):
    id: str
    user_id: str
    status: str
    verification_status: str


class FacilityRef(BaseModel):
    id: str
    status: str
    verification_status: str


class BranchRef(BaseModel):
    id: str
    facility_id: str
    timezone: str
    status: str


class HoursWindowIn(BaseModel):
    weekday: int
    start_minute: int
    end_minute: int


class RuleIn(BaseModel):
    id: str
    weekday: int
    start_minute: int
    end_minute: int
    effective_from: date
    effective_until: date | None = None


class ExceptionIn(BaseModel):
    id: str
    branch_id: str | None = None
    starts_at: datetime
    ends_at: datetime
    reason: str


class SchedulingContext(BaseModel):
    offering: Offering
    provider: ProviderRef
    facility: FacilityRef
    branch: BranchRef
    affiliation_active: bool
    bookable: bool
    operating_hours: list[HoursWindowIn]
    availability_rules: list[RuleIn]
    exceptions: list[ExceptionIn]


class FacilityRole(BaseModel):
    facility_id: str
    role: str


class SchedulingActor(BaseModel):
    user_id: str
    provider_ids: list[str] = []
    facility_roles: list[FacilityRole] = []


class ProviderDirectory(Protocol):
    async def scheduling_context(
        self, tenant_id: str, service_id: str, window_start: datetime, window_end: datetime
    ) -> SchedulingContext | None:
        """Facts for one offering, or None when it does not exist in that tenant."""

    async def actor(self, tenant_id: str, user_id: str) -> SchedulingActor:
        """Providers the user owns and the facility roles they hold."""


class ServiceTokenSource:
    """Client-credentials service token from identity-service, cached until shortly before expiry."""

    def __init__(self, *, client: httpx.AsyncClient, token_url: str, client_id: str, client_secret: str) -> None:
        self._client = client
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._token = None

    async def token(self) -> str:
        async with self._lock:
            if self._token is not None and time.monotonic() < self._expires_at:
                return self._token
            try:
                response = await self._client.post(
                    self._token_url,
                    headers={"X-Service-Client-Id": self._client_id, "X-Service-Client-Secret": self._client_secret},
                )
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"service token request failed: {exc!r}") from exc
            if response.status_code != 200:
                raise ProviderUnavailable(f"service token request returned {response.status_code}")
            try:
                body = response.json()
                token, ttl = body["access_token"], int(body.get("expires_in", 300))
            except (ValueError, KeyError, TypeError) as exc:
                raise ProviderUnavailable("malformed service token response") from exc
            self._token = token
            self._expires_at = time.monotonic() + max(ttl - 30, 1)
            return token


class HttpProviderDirectory:
    def __init__(self, *, client: httpx.AsyncClient, base_url: str, tokens: ServiceTokenSource) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._tokens = tokens

    async def _get(self, path: str, params: dict[str, str]) -> httpx.Response | None:
        for attempt in range(2):
            token = await self._tokens.token()
            try:
                response = await self._client.get(
                    self._base_url + path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
            except httpx.HTTPError as exc:
                logger.warning("provider-service request failed: %r", exc)
                raise ProviderUnavailable(f"provider-service unreachable: {exc!r}") from exc
            if response.status_code == 401 and attempt == 0:
                # Token expired or rotated: fetch a fresh one once.
                self._tokens.invalidate()
                continue
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                logger.warning("provider-service %s answered %s", path, response.status_code)
                raise ProviderUnavailable(f"provider-service answered {response.status_code}")
            return response
        raise ProviderUnavailable("provider-service rejected the service token")

    async def scheduling_context(
        self, tenant_id: str, service_id: str, window_start: datetime, window_end: datetime
    ) -> SchedulingContext | None:
        response = await self._get(
            f"/v1/internal/scheduling/services/{service_id}",
            {
                "tenant_id": tenant_id,
                "from": window_start.astimezone(UTC).isoformat(),
                "to": window_end.astimezone(UTC).isoformat(),
            },
        )
        if response is None:
            return None
        try:
            return SchedulingContext.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ProviderUnavailable("malformed scheduling context") from exc

    async def actor(self, tenant_id: str, user_id: str) -> SchedulingActor:
        response = await self._get(f"/v1/internal/scheduling/actors/{user_id}", {"tenant_id": tenant_id})
        if response is None:
            return SchedulingActor(user_id=user_id)
        try:
            return SchedulingActor.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ProviderUnavailable("malformed scheduling actor") from exc
