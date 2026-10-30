"""Stripe adapter without network: request building (httpx.MockTransport) and webhook signatures."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import httpx
import pytest

from payment_service.infra.gateways.base import GatewayError, GatewayRejected, WebhookVerificationError
from payment_service.infra.gateways.stripe import (
    StripeGateway,
    StripeWebhookTranslator,
    encode_form,
    signature_header,
    verify_signature,
)

SECRET = "whsec_test_unit_secret"
KEY = "sk_test_unit_key_not_real"


class Recorder:
    def __init__(self, responses: list[tuple[int, dict]]) -> None:
        self.requests: list[httpx.Request] = []
        self._responses = list(responses)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self._responses.pop(0)
        return httpx.Response(status, json=body)


def gateway(recorder: Recorder) -> StripeGateway:
    return StripeGateway(secret_key=KEY, api_base="https://stripe.test", transport=httpx.MockTransport(recorder))


PI = {"id": "pi_1", "object": "payment_intent", "status": "requires_payment_method", "amount": 77175, "currency": "aed",
      "client_secret": "pi_1_secret_x", "amount_capturable": 0, "amount_received": 0, "metadata": {"healuxa_payment_id": "P1"}}


def test_encode_form_uses_bracket_notation() -> None:
    assert encode_form({"a": 1, "b": {"c": True, "d": None}, "items": [{"price": "p"}], "expand": ["x.y"]}) == [
        ("a", "1"), ("b[c]", "true"), ("items[0][price]", "p"), ("expand[0]", "x.y")
    ]


async def test_create_payment_intent_request_is_built_correctly() -> None:
    rec = Recorder([(200, PI)])
    gp = await gateway(rec).create_payment(
        amount_minor=77175, currency="AED", capture_method="manual", metadata={"healuxa_payment_id": "P1"},
        description="Healuxa payment P1", idempotency_key="hx-pay-P1",
    )
    req = rec.requests[0]
    assert req.method == "POST" and str(req.url) == "https://stripe.test/v1/payment_intents"
    assert req.headers["Authorization"] == f"Bearer {KEY}"
    assert req.headers["Stripe-Version"] == "2024-06-20"
    assert req.headers["Idempotency-Key"] == "hx-pay-P1"
    form = dict(parse_qsl(req.content.decode()))
    assert form == {
        "amount": "77175", "currency": "aed", "capture_method": "manual", "automatic_payment_methods[enabled]": "true",
        "description": "Healuxa payment P1", "metadata[healuxa_payment_id]": "P1",
    }
    assert not any(k.startswith(("card", "payment_method_data")) for k in form)  # never card data
    assert gp.status == "pending" and gp.client_secret == "pi_1_secret_x" and gp.currency == "AED"


async def test_capture_cancel_and_refund_requests() -> None:
    rec = Recorder([
        (200, {**PI, "status": "succeeded", "amount_received": 77175, "latest_charge": "ch_1"}),
        (200, {**PI, "status": "canceled"}),
        (200, {"id": "re_1", "object": "refund", "status": "succeeded", "amount": 100, "currency": "aed", "payment_intent": "pi_1"}),
    ])
    gw = gateway(rec)
    captured = await gw.capture_payment("pi_1", idempotency_key="hx-cap-P1")
    canceled = await gw.cancel_payment("pi_1", reason="provider_declined", idempotency_key="hx-void-P1")
    refund = await gw.create_refund("pi_1", amount_minor=100, reason="appointment_cancelled", metadata={"healuxa_refund_id": "R1"}, idempotency_key="hx-re-R1")
    assert [str(r.url) for r in rec.requests] == [
        "https://stripe.test/v1/payment_intents/pi_1/capture",
        "https://stripe.test/v1/payment_intents/pi_1/cancel",
        "https://stripe.test/v1/refunds",
    ]
    assert dict(parse_qsl(rec.requests[1].content.decode())) == {}  # non-Stripe reason not forwarded
    assert dict(parse_qsl(rec.requests[2].content.decode()))["reason"] == "requested_by_customer"
    assert (captured.status, captured.charge_id, canceled.status, refund.status) == ("succeeded", "ch_1", "canceled", "succeeded")


async def test_subscription_creation_builds_price_then_subscription() -> None:
    rec = Recorder([
        (200, {"id": "price_1"}),
        (200, {"id": "sub_1", "status": "incomplete", "items": {"data": [{"id": "si_1"}]},
               "latest_invoice": {"id": "in_1", "payment_intent": PI}}),
    ])
    sub = await gateway(rec).create_subscription(
        customer_id="cus_1", amount_minor=262_500, currency="AED", interval="month", interval_count=1,
        product_name="Healuxa membership essential", metadata={"healuxa_subscription_id": "S1"}, idempotency_key="hx-sub-P1",
    )
    price_form = dict(parse_qsl(rec.requests[0].content.decode()))
    sub_form = dict(parse_qsl(rec.requests[1].content.decode()))
    assert price_form["recurring[interval]"] == "month" and price_form["unit_amount"] == "262500"
    assert rec.requests[0].headers["Idempotency-Key"] == "hx-sub-P1:price"
    assert sub_form["items[0][price]"] == "price_1" and sub_form["payment_behavior"] == "default_incomplete"
    assert sub_form["expand[0]"] == "latest_invoice.payment_intent"
    assert sub.item_id == "si_1" and sub.latest_payment.id == "pi_1"


async def test_errors_map_to_retryable_and_rejected() -> None:
    gw = gateway(Recorder([(500, {}), (402, {"error": {"code": "card_declined", "message": "declined"}})]))
    with pytest.raises(GatewayError):
        await gw.retrieve_payment("pi_1")
    with pytest.raises(GatewayRejected) as info:
        await gw.retrieve_payment("pi_1")
    assert info.value.code == "card_declined"


async def test_network_failure_is_retryable() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    gw = StripeGateway(secret_key=KEY, transport=httpx.MockTransport(boom))
    with pytest.raises(GatewayError):
        await gw.retrieve_payment("pi_1")


async def test_balance_transactions_are_paginated() -> None:
    from datetime import UTC, datetime

    rec = Recorder([
        (200, {"data": [{"id": "txn_1", "type": "charge", "source": "ch_1", "amount": 100, "fee": 3, "net": 97, "currency": "aed", "created": 1}], "has_more": True}),
        (200, {"data": [{"id": "txn_2", "type": "payout", "source": "po_1", "amount": -97, "fee": 0, "net": -97, "currency": "aed", "created": 2}], "has_more": False}),
    ])
    txns = await gateway(rec).list_balance_transactions(created_gte=datetime(2026, 1, 1, tzinfo=UTC), created_lt=datetime(2026, 2, 1, tzinfo=UTC))
    assert [t.id for t in txns] == ["txn_1", "txn_2"]
    assert ("starting_after", "txn_1") in list(rec.requests[1].url.params.multi_items())


# ── signatures ───────────────────────────────────────────────────────────────


def test_signature_matches_stripe_documented_scheme() -> None:
    payload = b'{"id":"evt_1"}'
    header = signature_header(SECRET, payload, 1_700_000_000)
    expected = hmac.new(SECRET.encode(), b"1700000000." + payload, hashlib.sha256).hexdigest()
    assert header == f"t=1700000000,v1={expected}"
    verify_signature(payload, header, SECRET, tolerance=300, now=1_700_000_100)


def test_any_matching_v1_signature_is_accepted_for_secret_rotation() -> None:
    payload = b"{}"
    good = signature_header(SECRET, payload, 1000).split("v1=")[1]
    verify_signature(payload, f"t=1000,v1=deadbeef,v1={good},v0=ignored", SECRET, tolerance=300, now=1000)


@pytest.mark.parametrize(
    "header",
    [None, "", "t=1000", "v1=abc", "t=abc,v1=abc", "t=1000,v1=" + "0" * 64],
)
def test_malformed_or_wrong_signatures_are_rejected(header) -> None:
    with pytest.raises(WebhookVerificationError):
        verify_signature(b"{}", header, SECRET, tolerance=300, now=1000)


def test_tampered_body_is_rejected() -> None:
    header = signature_header(SECRET, b'{"amount":100}', 1000)
    with pytest.raises(WebhookVerificationError):
        verify_signature(b'{"amount":999}', header, SECRET, tolerance=300, now=1000)


def test_stale_and_future_timestamps_are_rejected() -> None:
    header = signature_header(SECRET, b"{}", 1000)
    with pytest.raises(WebhookVerificationError, match="tolerance"):
        verify_signature(b"{}", header, SECRET, tolerance=300, now=1000 + 301)
    with pytest.raises(WebhookVerificationError, match="tolerance"):
        verify_signature(b"{}", header, SECRET, tolerance=300, now=1000 - 301)


def test_wrong_secret_and_missing_secret_are_rejected() -> None:
    header = signature_header("whsec_other", b"{}", 1000)
    with pytest.raises(WebhookVerificationError):
        verify_signature(b"{}", header, SECRET, tolerance=300, now=1000)
    with pytest.raises(WebhookVerificationError):
        verify_signature(b"{}", header, "", tolerance=300, now=1000)


def test_translator_maps_event_kinds() -> None:
    t = StripeWebhookTranslator(secret=SECRET, tolerance=300)
    now = int(time.time())

    def ev(event_type, obj):
        payload = json.dumps({"id": "evt_x", "type": event_type, "created": now, "livemode": False, "data": {"object": obj}}).encode()
        return t.translate(t.verify(payload, signature_header(SECRET, payload)))

    assert ev("payment_intent.amount_capturable_updated", {**PI, "status": "requires_capture", "amount_capturable": 5}).payment.status == "authorized"
    failed = ev("payment_intent.payment_failed", {**PI, "last_payment_error": {"code": "card_declined", "decline_code": "insufficient_funds"}}).payment
    assert failed.status == "failed" and failed.failure_code == "insufficient_funds"
    assert ev("refund.updated", {"id": "re_1", "status": "succeeded", "amount": 1, "currency": "aed", "payment_intent": "pi_1"}).kind == "refund"
    dispute = ev("charge.dispute.funds_withdrawn", {"id": "dp_1", "status": "needs_response", "amount": 1, "currency": "aed", "charge": "ch_1"})
    assert dispute.kind == "dispute" and dispute.funds_withdrawn
    assert ev("invoice.paid", {"id": "in_1", "subscription": "sub_1", "payment_intent": "pi_1", "amount_paid": 1, "currency": "aed"}).kind == "invoice_paid"
    assert ev("customer.subscription.deleted", {"id": "sub_1", "status": "canceled"}).subscription.status == "canceled"
    assert ev("account.updated", {"id": "acct_1"}).kind == "ignored"
