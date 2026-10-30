"""Membership billing: processor subscriptions owned here, state from webhooks, events for subscription-service."""

from __future__ import annotations

import time

from httpx import AsyncClient

from helpers import customer, new_id, ok, outbox, send_webhook, stripe_event, subscription_event
from payment_service.config import settings


async def _membership(user: str, price: int = 250_000) -> str:
    sub_id = new_id()
    await subscription_event(
        "subscription.created",
        {"subscription_id": sub_id, "user_id": user, "plan_id": "essential-beauty", "price": {"amount_minor": price, "currency": "AED"},
         "billing_cycle": "monthly", "started_at": "2026-10-01T00:00:00Z", "status": "incomplete"},
    )
    return sub_id


async def _subscribe(client: AsyncClient, gateway, user: str) -> tuple[str, dict]:
    sub_id = await _membership(user)
    quote = await ok(await client.post("/v1/payment-quotes", json={"subject_type": "membership", "subject_id": sub_id}, headers=customer(user)), 201)
    assert quote["total"]["amount_minor"] == 262_500 and quote["lines"][0]["category"] == "membership"
    payment = await ok(await client.post("/v1/payments", json={"quote_id": quote["id"]}, headers={**customer(user), "Idempotency-Key": f"m-{new_id()}"}), 201)
    return sub_id, payment


async def test_membership_payment_opens_processor_subscription(client: AsyncClient, gateway) -> None:
    user = new_id()
    sub_id, payment = await _subscribe(client, gateway, user)
    assert payment["client_secret"] and payment["capture_method"] == "automatic"
    calls = [c for c in gateway.calls if c[0] == "create_subscription"]
    assert len(calls) == 1 and calls[0][1]["amount_minor"] == 262_500 and calls[0][1]["interval"] == "month"
    again = await client.post("/v1/payment-quotes", json={"subject_type": "membership", "subject_id": sub_id}, headers=customer(user))
    assert again.status_code == 409  # already has a billing agreement
    assert (await client.post("/v1/payment-quotes", json={"subject_type": "membership", "subject_id": sub_id}, headers=customer(new_id()))).status_code == 404


async def test_invoice_paid_webhook_succeeds_first_and_renewal_payments(client: AsyncClient, gateway) -> None:
    user = new_id()
    sub_id, payment = await _subscribe(client, gateway, user)
    processor_sub = next(iter(gateway.subscriptions.values()))
    first_pi = processor_sub["_first_pi"]
    now = int(time.time())
    invoice = {"id": "in_first", "object": "invoice", "subscription": processor_sub["id"], "payment_intent": first_pi, "charge": "ch_m1",
               "amount_paid": 262_500, "amount_due": 262_500, "currency": "aed", "billing_reason": "subscription_create",
               "lines": {"data": [{"period": {"start": now, "end": now + 30 * 86400}}]}}
    await send_webhook(client, stripe_event("invoice.paid", invoice, created=now))
    paid = await ok(await client.get(f"/v1/payments/{payment['id']}", headers=customer(user)))
    assert paid["status"] == "succeeded" and paid["invoice_id"]
    renewal = {**invoice, "id": "in_renew", "payment_intent": "pi_renewal_1", "charge": "ch_m2", "billing_reason": "subscription_cycle"}
    await send_webhook(client, stripe_event("invoice.paid", renewal, created=now + 10))
    succeeded = [e["payload"] for e in await outbox("payment.succeeded")]
    assert [(p["subscription_id"], p["billing_reason"]) for p in succeeded] == [(sub_id, "subscription_create"), (sub_id, "subscription_cycle")]
    assert all(p["billing_period_end"] for p in succeeded)
    mine = await ok(await client.get("/v1/payments", headers=customer(user)))
    assert len(mine["data"]) == 2


async def test_failed_renewal_reports_payment_failed(client: AsyncClient, gateway) -> None:
    user = new_id()
    sub_id, _ = await _subscribe(client, gateway, user)
    processor_sub = next(iter(gateway.subscriptions.values()))
    invoice = {"id": "in_fail", "subscription": processor_sub["id"], "payment_intent": "pi_renewal_fail", "amount_paid": 0,
               "amount_due": 262_500, "currency": "aed", "billing_reason": "subscription_cycle"}
    await send_webhook(client, stripe_event("invoice.payment_failed", invoice))
    failed = (await outbox("payment.failed"))[0]["payload"]
    assert failed["subscription_id"] == sub_id and failed["subject_type"] == "membership"


async def test_processor_subscription_updates_become_billing_agreement_events(client: AsyncClient, gateway) -> None:
    user = new_id()
    sub_id, _ = await _subscribe(client, gateway, user)
    processor_sub = next(iter(gateway.subscriptions.values()))
    now = int(time.time())
    active = {"id": processor_sub["id"], "object": "subscription", "status": "active", "cancel_at_period_end": False, "current_period_end": now + 86400}
    await send_webhook(client, stripe_event("customer.subscription.updated", active, created=now))
    await send_webhook(client, stripe_event("customer.subscription.deleted", {**active, "status": "canceled"}, created=now + 5))
    await send_webhook(client, stripe_event("customer.subscription.updated", active, created=now + 1))  # late, ignored
    statuses = [e["payload"]["status"] for e in await outbox("payment.billing_agreement_updated")]
    assert statuses == ["active", "canceled"]
    assert all(e["payload"]["subscription_id"] == sub_id for e in await outbox("payment.billing_agreement_updated"))


async def test_cancellation_and_plan_change_reach_the_processor(client: AsyncClient, gateway) -> None:
    user = new_id()
    sub_id, _ = await _subscribe(client, gateway, user)
    await subscription_event("subscription.upgraded", {"subscription_id": sub_id, "user_id": user, "from_plan_id": "essential-beauty",
                                                        "to_plan_id": "longevity-executive", "price": {"amount_minor": 650_000, "currency": "AED"},
                                                        "changed_at": "2026-10-02T00:00:00Z"})
    env = await subscription_event("subscription.cancellation_scheduled", {"subscription_id": sub_id, "user_id": user, "plan_id": "longevity-executive",
                                                                           "requested_at": "2026-10-03T00:00:00Z"})
    from payment_service.domain.consumers import handle_subscription_event
    from payment_service.infra.db import SessionLocal

    await handle_subscription_event(SessionLocal, env)  # redelivery: no second processor call
    updates = [c[1] for c in gateway.calls if c[0] == "update_subscription"]
    assert [u["amount_minor"] for u in updates] == [682_500, None]
    assert [u["cancel_at_period_end"] for u in updates] == [None, True]


async def test_membership_payments_disabled_by_flag(client: AsyncClient, gateway, monkeypatch) -> None:
    user = new_id()
    sub_id = await _membership(user)
    monkeypatch.setattr(settings, "membership_payments_enabled", False)
    response = await client.post("/v1/payment-quotes", json={"subject_type": "membership", "subject_id": sub_id}, headers=customer(user))
    assert response.status_code == 404
