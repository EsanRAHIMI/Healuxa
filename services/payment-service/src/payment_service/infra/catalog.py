"""Read-only port to provider-service's published catalog (OHS ``GET /v1/services/{id}``).

Prices for bookings come from here, server side — never from the client. Only the public offering
view is used, so no credentials are needed and no provider-service database is touched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from payment_service.config import settings


class CatalogUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Offering:
    id: str
    provider_id: str
    facility_id: str | None
    status: str
    price_type: str
    professional_fee_minor: int | None
    facility_fee_minor: int | None
    currency: str


class Catalog(Protocol):
    async def get_offering(self, service_id: str) -> Offering | None: ...


def offering_from_contract(body: dict) -> Offering:
    def minor(money: dict | None) -> int | None:
        return int(money["amount_minor"]) if money else None

    currency = next(
        (m["currency"] for m in (body.get("price"), body.get("professional_fee"), body.get("facility_fee")) if m),
        settings.currency,
    )
    return Offering(
        id=body["id"],
        provider_id=body["provider_id"],
        facility_id=body.get("facility_id"),
        status=body.get("status") or "draft",
        price_type=body.get("price_type") or "on_request",
        professional_fee_minor=minor(body.get("professional_fee")),
        facility_fee_minor=minor(body.get("facility_fee")),
        currency=currency,
    )


class HttpCatalog:
    def __init__(self, base_url: str, *, timeout: float = 5.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def get_offering(self, service_id: str) -> Offering | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.get(f"{self._base_url}/v1/services/{service_id}")
        except httpx.HTTPError:
            raise CatalogUnavailable("provider-service unreachable") from None
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise CatalogUnavailable(f"provider-service returned {response.status_code}")
        return offering_from_contract(response.json())


_catalog: Catalog | None = None


def get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = HttpCatalog(settings.provider_service_url)
    return _catalog


def set_catalog(catalog: Catalog | None) -> None:
    global _catalog
    _catalog = catalog
