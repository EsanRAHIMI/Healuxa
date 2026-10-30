"""Full/partial refunds, limits, concurrency guards, policy, credit notes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from helpers import customer, new_id, ok, outbox, paid_appointment, send_webhook, staff, stripe_event
from payment_service.infra.db import SessionLocal
from payment_service.infra.models import Payment


async def refund(client: AsyncClient, payment_id: str, body: dict, *, key: str | None = None, headers: dict | None = None):
    return await client.post(
        f"/v1/payments/{payment_id}/refunds",
        json=body,
        headers={**(headers or staff()), "Idempotency-Key": key or f"refund-{new_id()}"},
    )


async def test_partial_then_full_refund(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    paid = await paid_appointment(client, gateway, catalog, user)
    pid = paid["payment"]["id"]
    first = await ok(await refund(client, pid, {"amount_minor": 20_000, "reason": "service_issue", "note": "late start"}), 201)
    assert first["status"] == "succeeded" and first["credit_note_id"]
    payment = await ok(await client.get(f"/v1/payments/{pid}", headers=customer(user)))
    assert payment["status"] == "partially_refunded" and payment["amount_refunded_minor"] == 20_000
    rest = await ok(await refund(client, pid, {"reason": "requested_by_customer"}), 201)
    assert rest["amount"]["amount_minor"] == 77_175 - 20_000
    payment = await ok(await client.get(f"/v1/payments/{pid}", headers=customer(user)))
    assert payment["status"] == "refunded"
    events = await outbox("payment.refunded")
    assert [e["payload"]["fully_refunded"] for e in events] == [False, True]
    assert events[-1]["payload"]["total_refunded"]["amount_minor"] == 77_175
    listed = await ok(await client.get(f"/v1/payments/{pid}/refunds", headers=customer(user)))
    assert len(listed["data"]) == 2


async def test_refund_cannot_exceed_captured(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    pid = paid["payment"]["id"]
    too_much = await refund(client, pid, {"amount_minor": 77_176, "reason": "goodwill"})
    assert too_much.status_code == 422
    await ok(await refund(client, pid, {"amount_minor": 77_000, "reason": "goodwill"}), 201)
    assert (await refund(client, pid, {"amount_minor": 176, "reason": "goodwill"})).status_code == 422
    await ok(await refund(client, pid, {"amount_minor": 175, "reason": "goodwill"}), 201)
    assert (await refund(client, pid, {"reason": "goodwill"})).status_code == 409  # fully refunded


async def test_uncaptured_payment_cannot_be_refunded(client: AsyncClient, gateway, catalog) -> None:
    from helpers import booked_appointment, create_payment, quote_for

    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"])
    assert (await refund(client, payment["id"], {"amount_minor": 1, "reason": "goodwill"})).status_code == 409


async def test_concurrent_refunds_cannot_overdraw(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    pid = paid["payment"]["id"]
    responses = await asyncio.gather(*[refund(client, pid, {"amount_minor": 30_000, "reason": "goodwill"}) for _ in range(5)])
    codes = sorted(r.status_code for r in responses)
    assert codes.count(201) == 2 and all(c in (409, 422) for c in codes if c != 201)
    payment = await ok(await client.get(f"/v1/payments/{pid}", headers=staff()))
    assert payment["amount_refunded_minor"] == 60_000


async def test_database_constraint_refuses_overdraw_whatever_the_code(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    async with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            await db.execute(update(Payment).where(Payment.id == paid["payment"]["id"]).values(amount_refunded_minor=Payment.amount_captured_minor + 1))
        await db.rollback()


async def test_refund_requires_refund_permission(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    paid = await paid_appointment(client, gateway, catalog, user)
    response = await refund(client, paid["payment"]["id"], {"reason": "goodwill"}, headers=customer(user))
    assert response.status_code == 403
    manage_only = staff(permissions="payments:read,payments:manage")
    assert (await refund(client, paid["payment"]["id"], {"reason": "goodwill"}, headers=manage_only)).status_code == 403


async def test_refund_is_idempotent(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    pid = paid["payment"]["id"]
    a = await ok(await refund(client, pid, {"amount_minor": 1000, "reason": "goodwill"}, key="refund-key-1"), 201)
    b = await ok(await refund(client, pid, {"amount_minor": 1000, "reason": "goodwill"}, key="refund-key-1"), 201)
    assert a["id"] == b["id"] and len(gateway.refunds) == 1
    clash = await refund(client, pid, {"amount_minor": 2000, "reason": "goodwill"}, key="refund-key-1")
    assert clash.status_code == 409


async def test_pending_refund_settles_by_webhook(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    paid = await paid_appointment(client, gateway, catalog, user)
    gateway.refund_outcome = "pending"
    pending = await ok(await refund(client, paid["payment"]["id"], {"amount_minor": 5000, "reason": "goodwill"}), 201)
    assert pending["status"] == "pending" and await outbox("payment.refunded") == []
    re_obj = gateway.refunds[next(iter(gateway.refunds))]
    re_obj["status"] = "succeeded"
    for _ in range(2):  # duplicate delivery
        await send_webhook(client, stripe_event("refund.updated", dict(re_obj)))
    assert len(await outbox("payment.refunded")) == 1
    payment = await ok(await client.get(f"/v1/payments/{paid['payment']['id']}", headers=customer(user)))
    assert payment["amount_refunded_minor"] == 5000


async def test_refund_made_at_processor_is_recorded(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    external = {"id": "re_dashboard_1", "object": "refund", "amount": 7000, "currency": "aed", "payment_intent": paid["pi_id"], "status": "succeeded"}
    await send_webhook(client, stripe_event("refund.created", external))
    refunds = await ok(await client.get(f"/v1/payments/{paid['payment']['id']}/refunds", headers=staff()))
    assert [(r["reason"], r["amount"]["amount_minor"]) for r in refunds["data"]] == [("processor_initiated", 7000)]


async def test_refund_policy_windows(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    paid = await paid_appointment(client, gateway, catalog, user, hours_ahead=48)
    pid = paid["payment"]["id"]
    scheduled = datetime.fromisoformat(paid["appointment"]["scheduled_at"])

    async def policy(at: datetime) -> dict:
        return await ok(await client.get(f"/v1/payments/{pid}/refund-policy", params={"cancelled_at": at.isoformat()}, headers=customer(user)))

    assert (await policy(scheduled - timedelta(hours=30)))["rule"] == "full_before_window"
    partial = await policy(scheduled - timedelta(hours=2))
    assert partial["rule"] == "partial_inside_window" and partial["refundable_minor"] == 38_588  # 50% half-up
    assert (await policy(scheduled + timedelta(minutes=1)))["refundable_minor"] == 0
    applied = await ok(
        await refund(client, pid, {"apply_policy": True, "cancelled_at": (scheduled - timedelta(hours=2)).isoformat(), "reason": "appointment_cancelled"}),
        201,
    )
    assert applied["amount"]["amount_minor"] == 38_588
    late = await refund(client, pid, {"apply_policy": True, "cancelled_at": (scheduled + timedelta(hours=1)).isoformat(), "reason": "appointment_cancelled"})
    assert late.status_code == 422
    assert (await client.get(f"/v1/payments/{pid}/refund-policy", headers=customer(new_id()))).status_code == 404


async def test_policy_for_uncaptured_payment(client: AsyncClient, gateway, catalog) -> None:
    from helpers import booked_appointment, create_payment, quote_for

    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"])
    decision = await ok(await client.get(f"/v1/payments/{payment['id']}/refund-policy", headers=customer(user)))
    assert decision["rule"] == "not_captured" and decision["refundable_minor"] == 0
    assert datetime.now(UTC)  # keep import used
