"""Organisation facts from provider-service — who a caller is a practitioner or staff member of.

Providers and facilities are independent organisations and provider-service is their only source of
truth, so shared-record reads ask it on every request (service token, short timeout). Anything other
than a clean answer raises ``DirectoryUnavailable`` and the read is refused: membership is never
assumed and never taken from the caller.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

GranteeType = Literal["provider", "facility"]


class DirectoryUnavailable(Exception):
    """provider-service (or the token issuer) could not give a trustworthy answer."""


class ActorProvider(BaseModel):
    id: str
    status: str
    verification_status: str = ""


class ActorFacility(BaseModel):
    id: str
    role: str
    status: str
    verification_status: str = ""


class Actor(BaseModel):
    user_id: str
    providers: list[ActorProvider] = []
    facilities: list[ActorFacility] = []


class Grantee(BaseModel):
    type: GranteeType
    id: str
    name: str
    status: str
    verification_status: str = ""


class OrganisationDirectory(Protocol):
    async def actor(self, tenant_id: str, user_id: str) -> Actor:
        """Practitioner profiles the user owns and the facilities they currently staff."""

    async def grantee(self, tenant_id: str, grantee_type: GranteeType, grantee_id: str) -> Grantee | None:
        """The organisation, or None when it does not exist in that tenant."""


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
                raise DirectoryUnavailable(f"service token request failed: {exc!r}") from exc
            if response.status_code != 200:
                raise DirectoryUnavailable(f"service token request returned {response.status_code}")
            try:
                body = response.json()
                token, ttl = body["access_token"], int(body.get("expires_in", 300))
            except (ValueError, KeyError, TypeError) as exc:
                raise DirectoryUnavailable("malformed service token response") from exc
            self._token = token
            self._expires_at = time.monotonic() + max(ttl - 30, 1)
            return token


class HttpOrganisationDirectory:
    def __init__(self, *, client: httpx.AsyncClient, base_url: str, tokens: ServiceTokenSource) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._tokens = tokens

    async def _get(self, path: str, tenant_id: str) -> httpx.Response | None:
        for attempt in range(2):
            token = await self._tokens.token()
            try:
                response = await self._client.get(
                    self._base_url + path, params={"tenant_id": tenant_id}, headers={"Authorization": f"Bearer {token}"}
                )
            except httpx.HTTPError as exc:
                logger.warning("provider-service request failed: %r", exc)
                raise DirectoryUnavailable(f"provider-service unreachable: {exc!r}") from exc
            if response.status_code == 401 and attempt == 0:
                self._tokens.invalidate()  # expired or rotated: fetch a fresh token once
                continue
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                logger.warning("provider-service %s answered %s", path, response.status_code)
                raise DirectoryUnavailable(f"provider-service answered {response.status_code}")
            return response
        raise DirectoryUnavailable("provider-service rejected the service token")

    async def actor(self, tenant_id: str, user_id: str) -> Actor:
        response = await self._get(f"/v1/internal/records-access/actors/{user_id}", tenant_id)
        if response is None:
            # An unknown route must never read as "no memberships" by accident of deployment order.
            raise DirectoryUnavailable("provider-service has no records-access endpoint")
        try:
            actor = Actor.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise DirectoryUnavailable("malformed records actor") from exc
        if actor.user_id != user_id:
            raise DirectoryUnavailable("records actor answered for a different user")
        return actor

    async def grantee(self, tenant_id: str, grantee_type: GranteeType, grantee_id: str) -> Grantee | None:
        response = await self._get(f"/v1/internal/records-access/grantees/{grantee_type}/{grantee_id}", tenant_id)
        if response is None:
            return None
        try:
            grantee = Grantee.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise DirectoryUnavailable("malformed records grantee") from exc
        if grantee.id != grantee_id or grantee.type != grantee_type:
            raise DirectoryUnavailable("records grantee answered for a different organisation")
        return grantee
