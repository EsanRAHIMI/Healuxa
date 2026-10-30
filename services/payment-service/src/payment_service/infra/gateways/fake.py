"""Deterministic in-process processor for tests and local development only (refused outside dev/test).

It keeps Stripe-shaped objects in memory and returns them through the same translation functions as
the real Stripe adapter, so the domain and webhook code paths are identical. It honours idempotency
keys like Stripe does and lets tests drive outcomes (authorise, succeed, fail) and inject outages.
No network, no randomness: ids are sequential.
"""

from __future__ import annotations

import copy
import itertools
from datetime import UTC, datetime
from typing import Any

from payment_service.infra.gateways.base import (
    GatewayBalanceTransaction,
    GatewayError,
    GatewayPayment,
    GatewayRefund,
    GatewayRejected,
    GatewaySubscription,
)
from payment_service.infra.gateways.stripe import (
    payment_from_stripe,
    refund_from_stripe,
    subscription_from_stripe,
)

FEE_BPS = 290
FEE_FIXED_MINOR = 100


def fake_fee(amount_minor: int) -> int:
    return (amount_minor * FEE_BPS + 5000) // 10000 + FEE_FIXED_MINOR


class FakeGateway:
    name = "stripe"  # mimics Stripe object shapes so the Stripe webhook translator applies unchanged

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._seq = itertools.count(1)
        self.payment_intents: dict[str, dict[str, Any]] = {}
        self.refunds: dict[str, dict[str, Any]] = {}
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.balance_transactions: list[dict[str, Any]] = []
        self._idempotent: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_next: Exception | None = None
        self.refund_outcome = "succeeded"

    # ── helpers ──────────────────────────────────────────────────────────────
    def _next(self, prefix: str) -> str:
        return f"{prefix}_fake_{next(self._seq):06d}"

    def _maybe_fail(self) -> None:
        if self.fail_next is not None:
            exc, self.fail_next = self.fail_next, None
            raise exc

    def _once(self, key: str, factory):
        if key in self._idempotent:
            return copy.deepcopy(self._idempotent[key])
        result = factory()
        self._idempotent[key] = copy.deepcopy(result)
        return result

    def _pi(self, payment_id: str) -> dict[str, Any]:
        if payment_id not in self.payment_intents:
            raise GatewayRejected(f"No such payment_intent: {payment_id}", code="resource_missing")
        return self.payment_intents[payment_id]

    # ── PaymentGateway ───────────────────────────────────────────────────────
    async def create_customer(self, *, reference: str, idempotency_key: str) -> str:
        self._maybe_fail()
        self.calls.append(("create_customer", {"reference": reference}))
        return self._once(f"cus:{idempotency_key}", lambda: self._next("cus"))

    def _new_pi(self, *, amount_minor: int, currency: str, capture_method: str, metadata: dict[str, str], invoice: str | None = None) -> dict[str, Any]:
        pi_id = self._next("pi")
        obj = {
            "id": pi_id,
            "object": "payment_intent",
            "amount": amount_minor,
            "amount_capturable": 0,
            "amount_received": 0,
            "currency": currency.lower(),
            "capture_method": capture_method,
            "status": "requires_payment_method",
            "client_secret": f"{pi_id}_secret_fake",
            "latest_charge": None,
            "last_payment_error": None,
            "invoice": invoice,
            "metadata": dict(metadata),
        }
        self.payment_intents[pi_id] = obj
        return obj

    async def create_payment(
        self, *, amount_minor: int, currency: str, capture_method: str, metadata: dict[str, str], description: str, idempotency_key: str
    ) -> GatewayPayment:
        self._maybe_fail()
        self.calls.append(("create_payment", {"amount_minor": amount_minor, "capture_method": capture_method, "metadata": metadata}))
        obj = self._once(
            f"pi:{idempotency_key}",
            lambda: self._new_pi(amount_minor=amount_minor, currency=currency, capture_method=capture_method, metadata=metadata),
        )
        return payment_from_stripe(self.payment_intents[obj["id"]])

    async def retrieve_payment(self, payment_id: str) -> GatewayPayment:
        self._maybe_fail()
        return payment_from_stripe(self._pi(payment_id))

    async def capture_payment(self, payment_id: str, *, idempotency_key: str) -> GatewayPayment:
        self._maybe_fail()
        self.calls.append(("capture_payment", {"payment_id": payment_id}))
        pi = self._pi(payment_id)
        if pi["status"] == "succeeded":
            return payment_from_stripe(pi)
        if pi["status"] != "requires_capture":
            raise GatewayRejected("This PaymentIntent could not be captured", code="payment_intent_unexpected_state")
        self._succeed(pi, pi["amount_capturable"])
        return payment_from_stripe(pi)

    async def cancel_payment(self, payment_id: str, *, reason: str | None, idempotency_key: str) -> GatewayPayment:
        self._maybe_fail()
        self.calls.append(("cancel_payment", {"payment_id": payment_id, "reason": reason}))
        pi = self._pi(payment_id)
        if pi["status"] == "canceled":
            return payment_from_stripe(pi)
        if pi["status"] == "succeeded":
            raise GatewayRejected("You cannot cancel this PaymentIntent because it has a status of succeeded.", code="payment_intent_unexpected_state")
        pi.update(status="canceled", amount_capturable=0)
        return payment_from_stripe(pi)

    async def create_refund(
        self, payment_id: str, *, amount_minor: int, reason: str, metadata: dict[str, str], idempotency_key: str
    ) -> GatewayRefund:
        self._maybe_fail()
        self.calls.append(("create_refund", {"payment_id": payment_id, "amount_minor": amount_minor, "reason": reason}))

        def make() -> dict[str, Any]:
            pi = self._pi(payment_id)
            already = sum(r["amount"] for r in self.refunds.values() if r["payment_intent"] == payment_id and r["status"] in {"pending", "succeeded"})
            if pi["status"] != "succeeded" or already + amount_minor > pi["amount_received"]:
                raise GatewayRejected("Refund amount exceeds the charge", code="amount_too_large")
            refund = {
                "id": self._next("re"),
                "object": "refund",
                "amount": amount_minor,
                "currency": pi["currency"],
                "payment_intent": payment_id,
                "charge": pi["latest_charge"],
                "status": self.refund_outcome,
                "metadata": dict(metadata),
                "failure_reason": None,
            }
            self.refunds[refund["id"]] = refund
            if refund["status"] == "succeeded":
                self._balance_txn("refund", refund["id"], -amount_minor, fee=0)
            return refund

        refund = self._once(f"re:{idempotency_key}", make)
        return refund_from_stripe(self.refunds[refund["id"]])

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
        self._maybe_fail()
        self.calls.append(("create_subscription", {"customer_id": customer_id, "amount_minor": amount_minor, "interval": interval, "interval_count": interval_count}))

        def make() -> dict[str, Any]:
            sub_id = self._next("sub")
            invoice_id = self._next("in")
            pi = self._new_pi(amount_minor=amount_minor, currency=currency, capture_method="automatic", metadata={}, invoice=invoice_id)
            sub = {
                "id": sub_id,
                "object": "subscription",
                "customer": customer_id,
                "status": "incomplete",
                "cancel_at_period_end": False,
                "current_period_end": None,
                "items": {"data": [{"id": self._next("si"), "price": {"unit_amount": amount_minor}}]},
                "metadata": dict(metadata),
                "latest_invoice": invoice_id,
                "_first_pi": pi["id"],
            }
            self.subscriptions[sub_id] = sub
            return sub

        sub = self._once(f"sub:{idempotency_key}", make)
        return self._subscription_view(sub["id"])

    def _subscription_view(self, sub_id: str) -> GatewaySubscription:
        sub = copy.deepcopy(self.subscriptions[sub_id])
        sub["latest_invoice"] = {"id": sub["latest_invoice"], "payment_intent": self.payment_intents[sub["_first_pi"]]}
        return subscription_from_stripe(sub)

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
        self._maybe_fail()
        self.calls.append(("update_subscription", {"subscription_id": subscription_id, "cancel_at_period_end": cancel_at_period_end, "amount_minor": amount_minor}))
        if subscription_id not in self.subscriptions:
            raise GatewayRejected(f"No such subscription: {subscription_id}", code="resource_missing")
        sub = self.subscriptions[subscription_id]
        if cancel_at_period_end is not None:
            sub["cancel_at_period_end"] = cancel_at_period_end
        if amount_minor is not None:
            sub["items"]["data"][0]["price"] = {"unit_amount": amount_minor}
        return self._subscription_view(subscription_id)

    async def list_balance_transactions(self, *, created_gte: datetime, created_lt: datetime) -> list[GatewayBalanceTransaction]:
        self._maybe_fail()
        lo, hi = int(created_gte.timestamp()), int(created_lt.timestamp())
        return [self._bt(t) for t in self.balance_transactions if lo <= t["created"] < hi]

    async def list_payout_transactions(self, payout_id: str) -> list[GatewayBalanceTransaction]:
        self._maybe_fail()
        return [self._bt(t, payout_id=payout_id) for t in self.balance_transactions if t.get("payout") == payout_id and t["type"] != "payout"]

    @staticmethod
    def _bt(t: dict[str, Any], payout_id: str | None = None) -> GatewayBalanceTransaction:
        return GatewayBalanceTransaction(
            id=t["id"],
            type=t["type"],
            source_id=t["source"],
            amount_minor=t["amount"],
            fee_minor=t["fee"],
            net_minor=t["net"],
            currency=t["currency"].upper(),
            created=datetime.fromtimestamp(t["created"], UTC),
            payout_id=payout_id,
        )

    # ── test drivers (simulate what the customer / Stripe does) ───────────────
    def _balance_txn(self, txn_type: str, source: str, amount: int, *, fee: int, currency: str = "aed", created: int | None = None) -> dict[str, Any]:
        txn = {
            "id": self._next("txn"),
            "type": txn_type,
            "source": source,
            "amount": amount,
            "fee": fee,
            "net": amount - fee,
            "currency": currency,
            "created": created if created is not None else int(datetime.now(UTC).timestamp()),
            "payout": None,
        }
        self.balance_transactions.append(txn)
        return txn

    def _succeed(self, pi: dict[str, Any], amount: int) -> None:
        charge_id = pi.get("latest_charge") or self._next("ch")
        pi.update(status="succeeded", amount_received=amount, amount_capturable=0, latest_charge=charge_id, last_payment_error=None)
        self._balance_txn("charge", charge_id, amount, fee=fake_fee(amount), currency=pi["currency"])

    def confirm(self, payment_id: str, outcome: str = "succeeded") -> dict[str, Any]:
        """The customer confirms in hosted fields. Returns the Stripe-shaped PaymentIntent."""
        pi = self._pi(payment_id)
        if outcome == "authorized":
            pi.update(status="requires_capture", amount_capturable=pi["amount"], latest_charge=pi.get("latest_charge") or self._next("ch"), last_payment_error=None)
        elif outcome == "succeeded":
            self._succeed(pi, pi["amount"])
        elif outcome == "failed":
            pi.update(status="requires_payment_method", last_payment_error={"code": "card_declined", "decline_code": "insufficient_funds"})
        elif outcome == "processing":
            pi.update(status="processing")
        else:
            raise ValueError(outcome)
        return copy.deepcopy(pi)

    def payout(self, *, created: int | None = None, amount_override: int | None = None) -> dict[str, Any]:
        """Pay out every unpaid non-payout transaction; returns the payout balance transaction."""
        unpaid = [t for t in self.balance_transactions if t["payout"] is None and t["type"] != "payout"]
        total = sum(t["net"] for t in unpaid)
        payout_id = self._next("po")
        for t in unpaid:
            t["payout"] = payout_id
        amount = -(amount_override if amount_override is not None else total)
        txn = self._balance_txn("payout", payout_id, amount, fee=0, created=created)
        txn["payout"] = payout_id
        return txn

    def stripe_object(self, kind: str, object_id: str) -> dict[str, Any]:
        store = {"payment_intent": self.payment_intents, "refund": self.refunds, "subscription": self.subscriptions}[kind]
        return copy.deepcopy(store[object_id])


__all__ = ["FakeGateway", "GatewayError", "fake_fee"]
