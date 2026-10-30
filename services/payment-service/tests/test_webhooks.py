"""Stripe webhook endpoint: signatures, replay, duplicates, out-of-order delivery, disputes."""

from __future__ import annotations

import json
import time

from httpx import AsyncClient
from sqlalchemy import func, select

from helpers import (
    booked_appointment,
    create_payment,
    customer,
    last_pi,
    new_id,
    ok,
    outbox,
    paid_appointment,
    quote_for,
    send_webhook,
    staff,
    stripe_event,
)
from payment_service.infra.db import SessionLocal
from payment_service.infra.models import LedgerJournal, ProcessorEvent


async def _pending_payment(client, gateway, catalog, user, capture_method="automatic"):
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"], capture_method=capture_method)
    return payment, last_pi(gateway)


async def _status(client, payment_id, user) -> str:
    return (await ok(await client.get(f"/v1/payments/{payment_id}", headers=customer(user))))["status"]


async def test_valid_signed_event_is_applied(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    response = await send_webhook(client, stripe_event("payment_intent.succeeded", gateway.confirm(pi, "succeeded")))
    assert response.status_code == 204
    assert await _status(client, payment["id"], user) == "succeeded"
    succeeded = await outbox("payment.succeeded")
    assert succeeded[0]["payload"]["subject_type"] == "appointment" and succeeded[0]["payload"]["amount"]["amount_minor"] == 77_175


async def test_invalid_signature_is_rejected_and_not_recorded(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    event = stripe_event("payment_intent.succeeded", gateway.confirm(pi, "succeeded"))
    assert (await send_webhook(client, event, secret="whsec_attacker")).status_code == 400
    assert (await send_webhook(client, event, header="")).status_code == 400
    assert await _status(client, payment["id"], user) == "pending"
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(ProcessorEvent)) == 0


async def test_raw_body_is_what_is_verified(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    _, pi = await _pending_payment(client, gateway, catalog, user)
    event = stripe_event("payment_intent.succeeded", gateway.confirm(pi, "succeeded"))
    body = json.dumps(event).encode()
    from payment_service.infra.gateways.stripe import signature_header
    from helpers import WEBHOOK_SECRET

    header = signature_header(WEBHOOK_SECRET, body)
    reserialised = json.dumps(event, indent=2).encode()  # same JSON, different bytes
    assert (await send_webhook(client, event, raw=reserialised, header=header)).status_code == 400
    assert (await send_webhook(client, event, raw=body, header=header)).status_code == 204


async def test_stale_replayed_signature_is_rejected(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    event = stripe_event("payment_intent.succeeded", gateway.confirm(pi, "succeeded"))
    response = await send_webhook(client, event, timestamp=int(time.time()) - 3600)
    assert response.status_code == 400
    assert await _status(client, payment["id"], user) == "pending"


async def test_duplicate_delivery_is_processed_once(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    event = stripe_event("payment_intent.succeeded", gateway.confirm(pi, "succeeded"))
    for _ in range(3):
        assert (await send_webhook(client, event)).status_code == 204
    assert len(await outbox("payment.succeeded")) == 1 and len(await outbox("payment.invoice_issued")) == 1
    async with SessionLocal() as db:
        journals = await db.scalar(select(func.count()).select_from(LedgerJournal).where(LedgerJournal.payment_id == payment["id"]))
        events = await db.scalar(select(func.count()).select_from(ProcessorEvent))
    assert journals == 1 and events == 1


async def test_same_object_new_event_id_is_still_idempotent(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    obj = gateway.confirm(pi, "succeeded")
    for _ in range(2):  # Stripe may emit distinct events for the same transition
        assert (await send_webhook(client, stripe_event("payment_intent.succeeded", obj))).status_code == 204
    assert len(await outbox("payment.succeeded")) == 1


async def test_out_of_order_failure_after_success_is_ignored(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    failed_obj = gateway.confirm(pi, "failed")
    succeeded_obj = gateway.confirm(pi, "succeeded")
    now = int(time.time())
    await send_webhook(client, stripe_event("payment_intent.succeeded", succeeded_obj, created=now))
    await send_webhook(client, stripe_event("payment_intent.payment_failed", failed_obj, created=now - 10))
    assert await _status(client, payment["id"], user) == "succeeded"
    assert await outbox("payment.failed") == []


async def test_failure_then_retry_success_moves_forward(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    now = int(time.time())
    await send_webhook(client, stripe_event("payment_intent.payment_failed", gateway.confirm(pi, "failed"), created=now))
    assert await _status(client, payment["id"], user) == "failed"
    failed = await outbox("payment.failed")
    assert failed[0]["payload"]["failure_code"] == "insufficient_funds"
    await send_webhook(client, stripe_event("payment_intent.succeeded", gateway.confirm(pi, "succeeded"), created=now + 5))
    assert await _status(client, payment["id"], user) == "succeeded"


async def test_late_authorisation_after_capture_is_ignored(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user, capture_method="manual")
    authorized_obj = gateway.confirm(pi, "authorized")
    await send_webhook(client, stripe_event("payment_intent.amount_capturable_updated", authorized_obj))
    await ok(await client.post(f"/v1/payments/{payment['id']}/capture", headers=staff()))
    await send_webhook(client, stripe_event("payment_intent.amount_capturable_updated", authorized_obj))
    assert await _status(client, payment["id"], user) == "succeeded"
    assert len(await outbox("payment.authorized")) == 1


async def test_livemode_event_is_refused_by_sandbox(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    event = stripe_event("payment_intent.succeeded", gateway.confirm(pi, "succeeded"), livemode=True)
    assert (await send_webhook(client, event)).status_code == 400
    assert await _status(client, payment["id"], user) == "pending"


async def test_unknown_gateway_and_unbuilt_tap_are_404(client: AsyncClient) -> None:
    assert (await client.post("/v1/payments/webhooks/tap_payments", content=b"{}")).status_code == 404
    assert (await client.post("/v1/payments/webhooks/paypal", content=b"{}")).status_code == 404


async def test_unhandled_event_types_and_unknown_objects_are_acknowledged(client: AsyncClient) -> None:
    assert (await send_webhook(client, stripe_event("account.updated", {"id": "acct_1"}))).status_code == 204
    unknown_pi = {"id": "pi_not_ours", "object": "payment_intent", "status": "succeeded", "amount": 1, "currency": "aed"}
    assert (await send_webhook(client, stripe_event("payment_intent.succeeded", unknown_pi))).status_code == 204
    async with SessionLocal() as db:
        outcomes = set(await db.scalars(select(ProcessorEvent.outcome)))
    assert outcomes == {"ignored", "unknown_object"}


async def test_metadata_mismatch_is_rejected(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    payment, pi = await _pending_payment(client, gateway, catalog, user)
    obj = gateway.confirm(pi, "succeeded")
    obj["metadata"]["healuxa_payment_id"] = new_id()
    await send_webhook(client, stripe_event("payment_intent.succeeded", obj))
    assert await _status(client, payment["id"], user) == "pending"


async def test_dispute_lifecycle_is_recorded(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    charge = gateway.stripe_object("payment_intent", paid["pi_id"])["latest_charge"]
    dispute = {"id": "dp_1", "object": "dispute", "amount": 77_175, "currency": "aed", "status": "needs_response",
               "reason": "fraudulent", "charge": charge, "payment_intent": paid["pi_id"], "evidence_details": {"due_by": int(time.time()) + 86400}}
    now = int(time.time())
    await send_webhook(client, stripe_event("charge.dispute.created", dispute, created=now))
    await send_webhook(client, stripe_event("charge.dispute.funds_withdrawn", dispute, created=now + 1))
    await send_webhook(client, stripe_event("charge.dispute.closed", {**dispute, "status": "lost"}, created=now + 3))
    await send_webhook(client, stripe_event("charge.dispute.updated", {**dispute, "status": "under_review"}, created=now + 2))  # late
    listed = await ok(await client.get("/v1/payments/disputes", headers=staff()))
    assert [(d["status"], d["reason"]) for d in listed["data"]] == [("lost", "fraudulent")]
    assert len(await outbox("payment.dispute_opened")) == 1
    assert (await outbox("payment.dispute_closed"))[0]["payload"]["outcome"] == "lost"
    ledger = await ok(await client.get(f"/v1/payments/{paid['payment']['id']}/ledger", headers=staff()))
    assert ledger["balanced"] and any(line["account"] == "disputes" for line in ledger["data"])
    assert (await client.get("/v1/payments/disputes", headers=customer(new_id()))).status_code == 403
