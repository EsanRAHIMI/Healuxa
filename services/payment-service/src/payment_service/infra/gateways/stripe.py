"""Stripe adapter (UAE-supported, AED) behind the PaymentGateway port.

Talks to the Stripe REST API with httpx (form-encoded, pinned ``Stripe-Version``, ``Idempotency-Key`` on
every mutating call) — no SDK, so request building is unit-testable without network. Webhooks are
verified with Stripe's documented ``Stripe-Signature`` scheme: HMAC-SHA256 over ``"{t}.{raw_body}"``
keyed with the endpoint signing secret, compared in constant time against every ``v1`` value, with a
timestamp tolerance against replay.

Healuxa never sends or receives card data here: customers enter cards in Stripe's hosted fields
(Payment Element) using the PaymentIntent ``client_secret``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from payment_service.infra.gateways.base import (
    GatewayBalanceTransaction,
    GatewayDispute,
    GatewayError,
    GatewayEvent,
    GatewayInvoice,
    GatewayPayment,
    GatewayRefund,
    GatewayRejected,
    GatewaySubscription,
    WebhookVerificationError,
)

SIGNATURE_SCHEME = "v1"

# ── Request encoding ──────────────────────────────────────────────────────────


def encode_form(params: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten nested params into Stripe's bracket notation (``a[b][0][c]=v``); drops None values."""
    pairs: list[tuple[str, str]] = []

    def walk(prefix: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                walk(f"{prefix}[{key}]" if prefix else str(key), item)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                walk(f"{prefix}[{index}]", item)
        elif isinstance(value, bool):
            pairs.append((prefix, "true" if value else "false"))
        else:
            pairs.append((prefix, str(value)))

    walk("", params)
    return pairs


# ── Webhook signatures ────────────────────────────────────────────────────────


def compute_signature(secret: str, payload: bytes, timestamp: int) -> str:
    signed = f"{timestamp}.".encode() + payload
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def signature_header(secret: str, payload: bytes, timestamp: int | None = None) -> str:
    """Build a ``Stripe-Signature`` header value (used by tests and the sandbox simulator)."""
    ts = int(time.time()) if timestamp is None else timestamp
    return f"t={ts},{SIGNATURE_SCHEME}={compute_signature(secret, payload, ts)}"


def verify_signature(payload: bytes, header: str | None, secret: str, *, tolerance: int, now: float | None = None) -> None:
    if not secret:
        raise WebhookVerificationError("webhook signing secret is not configured")
    if not header:
        raise WebhookVerificationError("missing Stripe-Signature header")
    timestamp: int | None = None
    candidates: list[str] = []
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                raise WebhookVerificationError("malformed timestamp") from None
        elif key == SIGNATURE_SCHEME and value:
            candidates.append(value)
    if timestamp is None or not candidates:
        raise WebhookVerificationError("no timestamp or v1 signature in header")
    expected = compute_signature(secret, payload, timestamp)
    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise WebhookVerificationError("signature mismatch")
    current = time.time() if now is None else now
    if timestamp < current - tolerance or timestamp > current + tolerance:
        raise WebhookVerificationError("timestamp outside tolerance (possible replay)")


# ── Object translation (Stripe → domain) ─────────────────────────────────────


def _ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), UTC)


def _id(value: Any) -> str | None:
    """Stripe fields may hold an id or an expanded object."""
    if isinstance(value, dict):
        return value.get("id")
    return value or None


_PI_STATUS = {
    "requires_payment_method": "pending",
    "requires_confirmation": "pending",
    "requires_action": "pending",
    "processing": "processing",
    "requires_capture": "authorized",
    "succeeded": "succeeded",
    "canceled": "canceled",
}


def payment_from_stripe(obj: dict[str, Any]) -> GatewayPayment:
    raw = obj.get("status") or "requires_payment_method"
    error = obj.get("last_payment_error") or {}
    status = _PI_STATUS.get(raw, "pending")
    if raw == "requires_payment_method" and error:
        status = "failed"
    return GatewayPayment(
        id=obj["id"],
        status=status,  # type: ignore[arg-type]
        raw_status=raw,
        amount_minor=int(obj.get("amount") or 0),
        amount_capturable_minor=int(obj.get("amount_capturable") or 0),
        amount_received_minor=int(obj.get("amount_received") or 0),
        currency=str(obj.get("currency") or "").upper(),
        client_secret=obj.get("client_secret"),
        charge_id=_id(obj.get("latest_charge")),
        failure_code=(error.get("decline_code") or error.get("code")) if error else None,
        invoice_id=_id(obj.get("invoice")),
        metadata=dict(obj.get("metadata") or {}),
    )


_REFUND_STATUS = {"pending": "pending", "requires_action": "pending", "succeeded": "succeeded", "failed": "failed", "canceled": "canceled"}


def refund_from_stripe(obj: dict[str, Any]) -> GatewayRefund:
    return GatewayRefund(
        id=obj["id"],
        payment_id=_id(obj.get("payment_intent")),
        status=_REFUND_STATUS.get(obj.get("status") or "pending", "pending"),  # type: ignore[arg-type]
        amount_minor=int(obj.get("amount") or 0),
        currency=str(obj.get("currency") or "").upper(),
        failure_reason=obj.get("failure_reason"),
        metadata=dict(obj.get("metadata") or {}),
    )


def dispute_from_stripe(obj: dict[str, Any]) -> GatewayDispute:
    evidence = obj.get("evidence_details") or {}
    return GatewayDispute(
        id=obj["id"],
        payment_id=_id(obj.get("payment_intent")),
        charge_id=_id(obj.get("charge")),
        status=obj.get("status") or "needs_response",
        reason=obj.get("reason"),
        amount_minor=int(obj.get("amount") or 0),
        currency=str(obj.get("currency") or "").upper(),
        evidence_due_by=_ts(evidence.get("due_by")),
    )


def invoice_from_stripe(obj: dict[str, Any]) -> GatewayInvoice:
    lines = ((obj.get("lines") or {}).get("data")) or []
    period_end = _ts((lines[0].get("period") or {}).get("end")) if lines else None
    error = ((obj.get("payment_intent") or {}) if isinstance(obj.get("payment_intent"), dict) else {}).get("last_payment_error") or {}
    return GatewayInvoice(
        id=obj["id"],
        subscription_id=_id(obj.get("subscription")),
        payment_id=_id(obj.get("payment_intent")),
        charge_id=_id(obj.get("charge")),
        amount_paid_minor=int(obj.get("amount_paid") or 0),
        amount_due_minor=int(obj.get("amount_due") or 0),
        currency=str(obj.get("currency") or "").upper(),
        billing_reason=obj.get("billing_reason"),
        period_end=period_end or _ts(obj.get("period_end")),
        failure_code=error.get("decline_code") or error.get("code") or None,
    )


def subscription_from_stripe(obj: dict[str, Any]) -> GatewaySubscription:
    items = ((obj.get("items") or {}).get("data")) or []
    latest_invoice = obj.get("latest_invoice")
    latest_payment = None
    if isinstance(latest_invoice, dict) and isinstance(latest_invoice.get("payment_intent"), dict):
        latest_payment = payment_from_stripe(latest_invoice["payment_intent"])
    return GatewaySubscription(
        id=obj["id"],
        status=obj.get("status") or "incomplete",
        item_id=items[0].get("id") if items else None,
        cancel_at_period_end=bool(obj.get("cancel_at_period_end")),
        current_period_end=_ts(obj.get("current_period_end")),
        latest_payment=latest_payment,
        metadata=dict(obj.get("metadata") or {}),
    )


def balance_transaction_from_stripe(obj: dict[str, Any], *, payout_id: str | None = None) -> GatewayBalanceTransaction:
    return GatewayBalanceTransaction(
        id=obj["id"],
        type=obj.get("type") or "unknown",
        source_id=_id(obj.get("source")),
        amount_minor=int(obj.get("amount") or 0),
        fee_minor=int(obj.get("fee") or 0),
        net_minor=int(obj.get("net") or 0),
        currency=str(obj.get("currency") or "").upper(),
        created=_ts(obj.get("created")) or datetime.now(UTC),
        payout_id=payout_id,
    )


DISPUTE_EVENTS = {
    "charge.dispute.created",
    "charge.dispute.updated",
    "charge.dispute.closed",
    "charge.dispute.funds_withdrawn",
    "charge.dispute.funds_reinstated",
}
REFUND_EVENTS = {"refund.created", "refund.updated", "refund.failed", "charge.refund.updated"}
SUBSCRIPTION_EVENTS = {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}


class StripeWebhookTranslator:
    name = "stripe"

    def __init__(self, *, secret: str, tolerance: int) -> None:
        self._secret = secret
        self._tolerance = tolerance

    def verify(self, payload: bytes, signature_header: str | None, *, now: float | None = None) -> dict[str, Any]:
        verify_signature(payload, signature_header, self._secret, tolerance=self._tolerance, now=now)
        try:
            event = json.loads(payload)
        except ValueError:
            raise WebhookVerificationError("body is not JSON") from None
        if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
            raise WebhookVerificationError("not a Stripe event")
        return event

    def translate(self, event: dict[str, Any]) -> GatewayEvent:
        event_type = event["type"]
        obj = ((event.get("data") or {}).get("object")) or {}
        base = {
            "id": event["id"],
            "type": event_type,
            "created": _ts(event.get("created")) or datetime.now(UTC),
            "livemode": bool(event.get("livemode")),
        }
        if event_type.startswith("payment_intent.") and obj.get("object", "payment_intent") == "payment_intent":
            return GatewayEvent(kind="payment", payment=payment_from_stripe(obj), **base)
        if event_type in REFUND_EVENTS:
            return GatewayEvent(kind="refund", refund=refund_from_stripe(obj), **base)
        if event_type in DISPUTE_EVENTS:
            return GatewayEvent(
                kind="dispute",
                dispute=dispute_from_stripe(obj),
                funds_withdrawn=event_type == "charge.dispute.funds_withdrawn",
                funds_reinstated=event_type == "charge.dispute.funds_reinstated",
                **base,
            )
        if event_type == "invoice.paid":
            return GatewayEvent(kind="invoice_paid", invoice=invoice_from_stripe(obj), **base)
        if event_type == "invoice.payment_failed":
            return GatewayEvent(kind="invoice_failed", invoice=invoice_from_stripe(obj), **base)
        if event_type in SUBSCRIPTION_EVENTS:
            return GatewayEvent(kind="subscription", subscription=subscription_from_stripe(obj), **base)
        return GatewayEvent(kind="ignored", **base)


# ── API client ────────────────────────────────────────────────────────────────

_INTERVALS = {"monthly": ("month", 1), "quarterly": ("month", 3), "annual": ("year", 1)}


def interval_for(billing_cycle: str) -> tuple[str, int]:
    return _INTERVALS[billing_cycle]


class StripeGateway:
    name = "stripe"

    def __init__(
        self,
        *,
        secret_key: str,
        api_base: str = "https://api.stripe.com",
        api_version: str = "2024-06-20",
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not secret_key:
            raise ValueError("STRIPE_SECRET_KEY is required for the Stripe gateway")
        self._secret_key = secret_key
        self._api_base = api_base.rstrip("/")
        self._api_version = api_version
        self._timeout = timeout
        self._transport = transport

    def _headers(self, idempotency_key: str | None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._secret_key}",
            "Stripe-Version": self._api_version,
            "User-Agent": "healuxa-payment-service",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        query: Iterable[tuple[str, str]] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                headers = self._headers(idempotency_key)
                content = None
                if data is not None:
                    content = urlencode(encode_form(data)).encode()
                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                response = await client.request(
                    method,
                    f"{self._api_base}{path}",
                    content=content,
                    params=list(query) if query is not None else None,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise GatewayError(f"stripe unreachable: {type(exc).__name__}") from None
        if response.status_code >= 500 or response.status_code == 429:
            raise GatewayError(f"stripe returned {response.status_code}")
        body = response.json() if response.content else {}
        if response.status_code >= 400:
            error = body.get("error") or {}
            raise GatewayRejected(error.get("message") or f"stripe returned {response.status_code}", code=error.get("code"))
        return body

    async def create_customer(self, *, reference: str, idempotency_key: str) -> str:
        body = await self._request("POST", "/v1/customers", data={"metadata": {"healuxa_user_id": reference}}, idempotency_key=idempotency_key)
        return body["id"]

    async def create_payment(
        self, *, amount_minor: int, currency: str, capture_method: str, metadata: dict[str, str], description: str, idempotency_key: str
    ) -> GatewayPayment:
        body = await self._request(
            "POST",
            "/v1/payment_intents",
            data={
                "amount": amount_minor,
                "currency": currency.lower(),
                "capture_method": capture_method,
                "automatic_payment_methods": {"enabled": True},
                "description": description,
                "metadata": metadata,
            },
            idempotency_key=idempotency_key,
        )
        return payment_from_stripe(body)

    async def retrieve_payment(self, payment_id: str) -> GatewayPayment:
        return payment_from_stripe(await self._request("GET", f"/v1/payment_intents/{quote(payment_id)}"))

    async def capture_payment(self, payment_id: str, *, idempotency_key: str) -> GatewayPayment:
        body = await self._request("POST", f"/v1/payment_intents/{quote(payment_id)}/capture", data={}, idempotency_key=idempotency_key)
        return payment_from_stripe(body)

    async def cancel_payment(self, payment_id: str, *, reason: str | None, idempotency_key: str) -> GatewayPayment:
        stripe_reason = reason if reason in {"duplicate", "fraudulent", "requested_by_customer", "abandoned"} else None
        body = await self._request(
            "POST",
            f"/v1/payment_intents/{quote(payment_id)}/cancel",
            data={"cancellation_reason": stripe_reason},
            idempotency_key=idempotency_key,
        )
        return payment_from_stripe(body)

    async def create_refund(
        self, payment_id: str, *, amount_minor: int, reason: str, metadata: dict[str, str], idempotency_key: str
    ) -> GatewayRefund:
        stripe_reason = reason if reason in {"duplicate", "fraudulent", "requested_by_customer"} else "requested_by_customer"
        body = await self._request(
            "POST",
            "/v1/refunds",
            data={"payment_intent": payment_id, "amount": amount_minor, "reason": stripe_reason, "metadata": metadata},
            idempotency_key=idempotency_key,
        )
        return refund_from_stripe(body)

    async def _create_price(
        self, *, amount_minor: int, currency: str, interval: str, interval_count: int, product_name: str, idempotency_key: str
    ) -> str:
        body = await self._request(
            "POST",
            "/v1/prices",
            data={
                "currency": currency.lower(),
                "unit_amount": amount_minor,
                "recurring": {"interval": interval, "interval_count": interval_count},
                "product_data": {"name": product_name},
            },
            idempotency_key=idempotency_key,
        )
        return body["id"]

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
    ) -> GatewaySubscription:
        price_id = await self._create_price(
            amount_minor=amount_minor,
            currency=currency,
            interval=interval,
            interval_count=interval_count,
            product_name=product_name,
            idempotency_key=f"{idempotency_key}:price",
        )
        body = await self._request(
            "POST",
            "/v1/subscriptions",
            data={
                "customer": customer_id,
                "items": [{"price": price_id}],
                "payment_behavior": "default_incomplete",
                "payment_settings": {"save_default_payment_method": "on_subscription"},
                "expand": ["latest_invoice.payment_intent"],
                "metadata": metadata,
            },
            idempotency_key=idempotency_key,
        )
        return subscription_from_stripe(body)

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
    ) -> GatewaySubscription:
        data: dict[str, Any] = {}
        if cancel_at_period_end is not None:
            data["cancel_at_period_end"] = cancel_at_period_end
        if amount_minor is not None:
            if not (item_id and currency and interval and interval_count and product_name):
                raise ValueError("re-pricing needs item_id, currency, interval, interval_count and product_name")
            price_id = await self._create_price(
                amount_minor=amount_minor,
                currency=currency,
                interval=interval,
                interval_count=interval_count,
                product_name=product_name,
                idempotency_key=f"{idempotency_key}:price",
            )
            data["items"] = [{"id": item_id, "price": price_id}]
            data["proration_behavior"] = "create_prorations"
        body = await self._request("POST", f"/v1/subscriptions/{quote(subscription_id)}", data=data, idempotency_key=idempotency_key)
        return subscription_from_stripe(body)

    async def _list(self, query: list[tuple[str, str]], *, payout_id: str | None = None) -> list[GatewayBalanceTransaction]:
        results: list[GatewayBalanceTransaction] = []
        starting_after: str | None = None
        for _ in range(1000):  # hard stop: 100k rows per import window
            page_query = [*query, ("limit", "100")]
            if starting_after:
                page_query.append(("starting_after", starting_after))
            body = await self._request("GET", "/v1/balance_transactions", query=page_query)
            data = body.get("data") or []
            results.extend(balance_transaction_from_stripe(item, payout_id=payout_id) for item in data)
            if not body.get("has_more") or not data:
                break
            starting_after = data[-1]["id"]
        return results

    async def list_balance_transactions(self, *, created_gte: datetime, created_lt: datetime) -> list[GatewayBalanceTransaction]:
        return await self._list(
            [("created[gte]", str(int(created_gte.timestamp()))), ("created[lt]", str(int(created_lt.timestamp())))]
        )

    async def list_payout_transactions(self, payout_id: str) -> list[GatewayBalanceTransaction]:
        return await self._list([("payout", payout_id)], payout_id=payout_id)
