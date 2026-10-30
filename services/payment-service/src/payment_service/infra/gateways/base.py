"""PaymentGateway port (DDD §7.3 ACL): processor-neutral types the domain works with.

No processor object ever crosses into the domain; adapters translate to these dataclasses. None of them
can hold card data — processors keep PAN/CVC; we only see ids, amounts and statuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

# Normalised payment states (rank used by the state machine lives in domain/state.py).
GatewayPaymentStatus = Literal["pending", "processing", "authorized", "succeeded", "failed", "canceled"]


class GatewayError(Exception):
    """The processor could not be reached or answered unexpectedly (retryable)."""


class GatewayRejected(Exception):
    """The processor refused the request (not retryable as-is), e.g. invalid state."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class WebhookVerificationError(Exception):
    pass


@dataclass(frozen=True)
class GatewayPayment:
    id: str
    status: GatewayPaymentStatus
    raw_status: str
    amount_minor: int
    amount_capturable_minor: int
    amount_received_minor: int
    currency: str
    client_secret: str | None = None
    charge_id: str | None = None
    failure_code: str | None = None
    invoice_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayRefund:
    id: str
    payment_id: str | None
    status: Literal["pending", "succeeded", "failed", "canceled"]
    amount_minor: int
    currency: str
    failure_reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayDispute:
    id: str
    payment_id: str | None
    charge_id: str | None
    status: str
    reason: str | None
    amount_minor: int
    currency: str
    evidence_due_by: datetime | None


@dataclass(frozen=True)
class GatewaySubscription:
    id: str
    status: str
    item_id: str | None
    cancel_at_period_end: bool
    current_period_end: datetime | None
    latest_payment: GatewayPayment | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayInvoice:
    id: str
    subscription_id: str | None
    payment_id: str | None
    charge_id: str | None
    amount_paid_minor: int
    amount_due_minor: int
    currency: str
    billing_reason: str | None
    period_end: datetime | None
    failure_code: str | None = None


@dataclass(frozen=True)
class GatewayBalanceTransaction:
    id: str
    type: str
    source_id: str | None
    amount_minor: int
    fee_minor: int
    net_minor: int
    currency: str
    created: datetime
    payout_id: str | None = None


@dataclass(frozen=True)
class GatewayEvent:
    """A verified processor event translated for the domain."""

    id: str
    type: str
    created: datetime
    livemode: bool
    kind: Literal["payment", "refund", "dispute", "invoice_paid", "invoice_failed", "subscription", "ignored"]
    payment: GatewayPayment | None = None
    refund: GatewayRefund | None = None
    dispute: GatewayDispute | None = None
    invoice: GatewayInvoice | None = None
    subscription: GatewaySubscription | None = None
    funds_withdrawn: bool = False
    funds_reinstated: bool = False


class PaymentGateway(Protocol):
    name: str

    async def create_customer(self, *, reference: str, idempotency_key: str) -> str: ...

    async def create_payment(
        self,
        *,
        amount_minor: int,
        currency: str,
        capture_method: str,
        metadata: dict[str, str],
        description: str,
        idempotency_key: str,
    ) -> GatewayPayment: ...

    async def retrieve_payment(self, payment_id: str) -> GatewayPayment: ...

    async def capture_payment(self, payment_id: str, *, idempotency_key: str) -> GatewayPayment: ...

    async def cancel_payment(self, payment_id: str, *, reason: str | None, idempotency_key: str) -> GatewayPayment: ...

    async def create_refund(
        self, payment_id: str, *, amount_minor: int, reason: str, metadata: dict[str, str], idempotency_key: str
    ) -> GatewayRefund: ...

    async def create_subscription(
        self,
        *,
        customer_id: str,
        amount_minor: int,
        currency: str,
        interval: str,
        interval_count: int,
        product_name: str,
        metadata: dict[str, str],
        idempotency_key: str,
    ) -> GatewaySubscription: ...

    async def update_subscription(
        self,
        subscription_id: str,
        *,
        idempotency_key: str,
        cancel_at_period_end: bool | None = None,
        item_id: str | None = None,
        amount_minor: int | None = None,
        currency: str | None = None,
        interval: str | None = None,
        interval_count: int | None = None,
        product_name: str | None = None,
    ) -> GatewaySubscription: ...

    async def list_balance_transactions(
        self, *, created_gte: datetime, created_lt: datetime
    ) -> list[GatewayBalanceTransaction]: ...

    async def list_payout_transactions(self, payout_id: str) -> list[GatewayBalanceTransaction]: ...


class WebhookTranslator(Protocol):
    name: str

    def verify(self, payload: bytes, signature_header: str | None, *, now: float | None = None) -> dict[str, Any]: ...

    def translate(self, event: dict[str, Any]) -> GatewayEvent: ...
