"""Processor webhook processing (ACL boundary).

1. Verify the signature over the *raw* body and the timestamp tolerance (replay protection).
2. Refuse events whose livemode differs from ours (a test endpoint never accepts live events).
3. Record the processor event id; a duplicate delivery is acknowledged without reprocessing.
4. Apply the translated event in the same transaction, monotonically (state.py), so out-of-order
   deliveries cannot move a payment backwards. A failure rolls back the event record too, so the
   processor's retry is processed again.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from payment_service.config import settings
from payment_service.domain.access import bad_request, not_found
from payment_service.domain.ledger import Posting, post_journal
from payment_service.domain.payments import apply_gateway_payment, lock_by_processor_id
from payment_service.domain.refunds import apply_gateway_refund, record_external_refund
from payment_service.events.publisher import event_publisher, money
from payment_service.infra.gateways import get_webhook_translator
from payment_service.infra.gateways.base import GatewayEvent, GatewayPayment, WebhookVerificationError
from payment_service.infra.models import Dispute, MembershipView, Payment, ProcessorEvent, Refund

logger = logging.getLogger(__name__)

CLOSED_DISPUTE = {"won": "won", "lost": "lost", "warning_closed": "warning_closed"}


async def handle_webhook(sessions: async_sessionmaker[AsyncSession], gateway: str, raw: bytes, signature: str | None) -> str:
    translator = get_webhook_translator(gateway)
    if translator is None:
        raise not_found("Webhook gateway")
    try:
        event = translator.verify(raw, signature)
    except WebhookVerificationError as exc:
        logger.warning("rejected %s webhook: %s", gateway, exc)
        raise bad_request("Invalid webhook signature") from None
    translated = translator.translate(event)
    if translated.livemode != settings.payments_live_mode:
        raise bad_request("Webhook livemode does not match this deployment")
    async with sessions() as db, db.begin():
        recorded = await db.scalar(
            insert(ProcessorEvent)
            .values(
                processor=translator.name,
                event_id=translated.id,
                event_type=translated.type,
                event_created_at=translated.created,
                outcome="processing",
                payload_sha256=hashlib.sha256(raw).hexdigest(),
            )
            .on_conflict_do_nothing(constraint="uq_processor_events_id")
            .returning(ProcessorEvent.id)
        )
        if recorded is None:
            return "duplicate"
        outcome = await dispatch(db, translator.name, translated)
        row = await db.get(ProcessorEvent, recorded)
        row.outcome = outcome
    return outcome


async def dispatch(db: AsyncSession, processor: str, ev: GatewayEvent) -> str:
    if ev.kind == "payment":
        return await _payment(db, processor, ev)
    if ev.kind == "refund":
        return await _refund(db, processor, ev)
    if ev.kind == "dispute":
        return await _dispute(db, processor, ev)
    if ev.kind in {"invoice_paid", "invoice_failed"}:
        return await _invoice(db, processor, ev)
    if ev.kind == "subscription":
        return await _subscription(db, ev)
    return "ignored"


async def _payment(db: AsyncSession, processor: str, ev: GatewayEvent) -> str:
    gp = ev.payment
    payment = await lock_by_processor_id(db, processor, gp.id)
    if payment is None:
        # Subscription invoices' PaymentIntents are handled through invoice.* events.
        return "deferred_to_invoice" if gp.invoice_id else "unknown_object"
    claimed = gp.metadata.get("healuxa_payment_id")
    if claimed and claimed != payment.id:
        logger.error("processor payment %s metadata claims %s but maps to %s", gp.id, claimed, payment.id)
        return "rejected_mismatch"
    changed = await apply_gateway_payment(db, payment, gp, event_at=ev.created)
    return "applied" if changed else "no_change"


async def _refund(db: AsyncSession, processor: str, ev: GatewayEvent) -> str:
    gr = ev.refund
    if not gr.payment_id:
        return "unknown_object"
    payment = await lock_by_processor_id(db, processor, gr.payment_id)
    if payment is None:
        return "unknown_object"
    refund = await db.scalar(
        select(Refund)
        .where(
            Refund.payment_id == payment.id,
            or_(Refund.processor_refund_id == gr.id, Refund.id == (gr.metadata.get("healuxa_refund_id") or "-")),
        )
        .with_for_update()
    )
    if refund is None:
        refund = await record_external_refund(db, payment, gr)
        if refund is None:
            return "rejected_exceeds_capture"
    changed = await apply_gateway_refund(db, payment, refund, gr)
    return "applied" if changed else "no_change"


async def _dispute(db: AsyncSession, processor: str, ev: GatewayEvent) -> str:
    gd = ev.dispute
    payment = None
    if gd.payment_id:
        payment = await lock_by_processor_id(db, processor, gd.payment_id)
    if payment is None and gd.charge_id:
        payment = await db.scalar(select(Payment).where(Payment.processor_charge_id == gd.charge_id).with_for_update())
    if payment is None:
        return "unknown_object"
    dispute = await db.scalar(
        select(Dispute).where(Dispute.processor == processor, Dispute.processor_dispute_id == gd.id).with_for_update()
    )
    now = datetime.now(UTC)
    opened = dispute is None
    if opened:
        dispute = Dispute(
            id=str(ULID()),
            tenant_id=payment.tenant_id,
            payment_id=payment.id,
            processor=processor,
            processor_dispute_id=gd.id,
            amount_minor=gd.amount_minor,
            currency=gd.currency or payment.currency,
            reason=gd.reason,
            status=gd.status,
            evidence_due_by=gd.evidence_due_by,
            last_event_at=ev.created,
        )
        db.add(dispute)
        await db.flush()
        await event_publisher.publish(
            db=db,
            event_type="payment.dispute_opened",
            tenant_id=payment.tenant_id,
            payload={
                "dispute_id": dispute.id,
                "payment_id": payment.id,
                "user_id": payment.user_id,
                "amount": money(gd.amount_minor, dispute.currency),
                "status": gd.status,
                "reason": gd.reason,
                "evidence_due_by": gd.evidence_due_by.isoformat() if gd.evidence_due_by else None,
                "opened_at": now.isoformat(),
            },
        )
    else:
        already_closed = dispute.status in CLOSED_DISPUTE
        newer = dispute.last_event_at is None or ev.created >= dispute.last_event_at
        if newer and not already_closed:
            dispute.status = gd.status
            dispute.evidence_due_by = gd.evidence_due_by or dispute.evidence_due_by
            dispute.last_event_at = ev.created
            dispute.updated_at = now
            if gd.status in CLOSED_DISPUTE:
                await event_publisher.publish(
                    db=db,
                    event_type="payment.dispute_closed",
                    tenant_id=payment.tenant_id,
                    payload={
                        "dispute_id": dispute.id,
                        "payment_id": payment.id,
                        "user_id": payment.user_id,
                        "amount": money(dispute.amount_minor, dispute.currency),
                        "outcome": CLOSED_DISPUTE[gd.status],
                        "closed_at": now.isoformat(),
                    },
                )
    if ev.funds_withdrawn:
        dispute.funds_withdrawn = True
        await post_journal(
            db,
            tenant_id=payment.tenant_id,
            key=f"dispute:{dispute.id}:withdrawn",
            kind="dispute",
            currency=dispute.currency,
            occurred_at=now,
            payment_id=payment.id,
            postings=[Posting("disputes", debit=dispute.amount_minor), Posting("processor_clearing", credit=dispute.amount_minor)],
        )
    if ev.funds_reinstated:
        await post_journal(
            db,
            tenant_id=payment.tenant_id,
            key=f"dispute:{dispute.id}:reinstated",
            kind="dispute_reversal",
            currency=dispute.currency,
            occurred_at=now,
            payment_id=payment.id,
            postings=[Posting("processor_clearing", debit=dispute.amount_minor), Posting("disputes", credit=dispute.amount_minor)],
        )
    await db.flush()
    return "applied"


async def _membership_for(db: AsyncSession, processor_subscription_id: str | None) -> MembershipView | None:
    if not processor_subscription_id:
        return None
    return await db.scalar(
        select(MembershipView).where(MembershipView.processor_subscription_id == processor_subscription_id).with_for_update()
    )


async def _invoice(db: AsyncSession, processor: str, ev: GatewayEvent) -> str:
    inv = ev.invoice
    membership = await _membership_for(db, inv.subscription_id)
    if membership is None or not inv.payment_id:
        return "unknown_object"
    payment = await lock_by_processor_id(db, processor, inv.payment_id)
    if payment is None:
        lines = membership.lines or []
        payment = Payment(
            id=str(ULID()),
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            subject_type="membership",
            subject_id=membership.subscription_id,
            currency=inv.currency or membership.currency,
            lines=lines,
            amount_minor=inv.amount_due_minor or inv.amount_paid_minor,
            capture_method="automatic",
            status="pending",
            processor=processor,
            processor_payment_id=inv.payment_id,
            processor_subscription_id=membership.processor_subscription_id,
            billing_reason="subscription_cycle" if inv.billing_reason == "subscription_cycle" else "subscription_update",
        )
        db.add(payment)
        await db.flush()
    payment.billing_period_end = inv.period_end or payment.billing_period_end
    if ev.kind == "invoice_paid":
        gp = GatewayPayment(
            id=inv.payment_id,
            status="succeeded",
            raw_status="succeeded",
            amount_minor=payment.amount_minor,
            amount_capturable_minor=0,
            amount_received_minor=inv.amount_paid_minor,
            currency=inv.currency,
            charge_id=inv.charge_id,
        )
    else:
        gp = GatewayPayment(
            id=inv.payment_id,
            status="failed",
            raw_status="requires_payment_method",
            amount_minor=payment.amount_minor,
            amount_capturable_minor=0,
            amount_received_minor=0,
            currency=inv.currency,
            failure_code=inv.failure_code or "invoice_payment_failed",
        )
    if inv.period_end and (membership.current_period_end is None or inv.period_end > membership.current_period_end):
        membership.current_period_end = inv.period_end
    changed = await apply_gateway_payment(db, payment, gp, event_at=ev.created)
    return "applied" if changed else "no_change"


async def _subscription(db: AsyncSession, ev: GatewayEvent) -> str:
    gs = ev.subscription
    membership = await _membership_for(db, gs.id)
    if membership is None:
        return "unknown_object"
    if membership.processor_status == "canceled" or (membership.processor_event_at and ev.created < membership.processor_event_at):
        return "no_change"  # terminal or older than what we applied
    membership.processor_status = gs.status
    membership.cancel_at_period_end = gs.cancel_at_period_end
    membership.current_period_end = gs.current_period_end or membership.current_period_end
    membership.processor_event_at = ev.created
    membership.updated_at = datetime.now(UTC)
    await event_publisher.publish(
        db=db,
        event_type="payment.billing_agreement_updated",
        tenant_id=membership.tenant_id,
        payload={
            "subscription_id": membership.subscription_id,
            "user_id": membership.user_id,
            "status": gs.status if gs.status in {"incomplete", "active", "past_due", "unpaid", "canceled", "incomplete_expired", "paused"} else "active",
            "current_period_end": membership.current_period_end.isoformat() if membership.current_period_end else None,
            "cancel_at_period_end": gs.cancel_at_period_end,
            "updated_at": ev.created.isoformat(),
        },
    )
    return "applied"
