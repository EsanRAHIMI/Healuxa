"""Provider-agnostic channel driver interface.

A driver turns one rendered notification into one outbound message on its channel. Drivers never
see health data: they get the rendered (non-clinical) title/body and opaque ids. Raise
``TransientDeliveryError`` to be retried with backoff, ``PermanentDeliveryError`` to dead-letter now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class TransientDeliveryError(Exception):
    """Temporary failure (network, rate limit, provider 5xx): retry later."""


class PermanentDeliveryError(Exception):
    """Will never succeed (no address, invalid token, rejected by provider): dead-letter."""


@dataclass(frozen=True)
class OutboundMessage:
    delivery_id: str
    tenant_id: str
    user_id: str
    channel: str
    locale: str
    title: str
    body: str
    # Stable key a real provider can use to deduplicate (event, recipient, channel).
    idempotency_key: str
    device_tokens: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DeliveryResult:
    provider_ref: str | None = None


class ChannelDriver(Protocol):
    channel: str
    name: str
    #: False for the ``disabled`` driver: deliveries are recorded as skipped, never attempted.
    enabled: bool

    async def send(self, message: OutboundMessage) -> DeliveryResult: ...


class ContactResolver(Protocol):
    """Resolves an email address / phone number for a user at send time (never stored here)."""

    async def address(self, tenant_id: str, user_id: str, channel: str) -> str | None: ...


class NoContactResolver:
    """Default: no contact directory is integrated yet, so real email/SMS drivers cannot address anyone."""

    async def address(self, tenant_id: str, user_id: str, channel: str) -> str | None:
        return None
