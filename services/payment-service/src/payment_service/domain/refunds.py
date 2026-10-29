"""Refunds and the cancellation refund policy.

Guards against over-refunding at three levels: the row lock on the payment while the amount is reserved,
the application check (``remaining``), and the database CHECK
``amount_refunded + amount_refund_pending <= amount_captured``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from payment_service.config import settings
from payment_service.domain import invoices as invoice_docs
from payment_service.domain.access import conflict, not_found, processor_unavailable, unprocessable
from payment_service.domain.ledger import post_refund
from payment_service.domain.money import apply_bps
from payment_service.domain.payments import lock_payment, request_hash
from payment_service.domain.state import CAPTURED_FAMILY
from payment_service.events.publisher import event_publisher, money
from payment_service.infra.gateways import get_gateway
from payment_service.infra.gateways.base import GatewayError, GatewayRefund, GatewayRejected
from payment_service.infra.models import AppointmentView, Invoice, Payment, Refund


def remaining(payment: Payment) -> int:
    return payment.amount_captured_minor - payment.amount_refunded_minor - payment.amount_refund_pending_minor


def evaluate_policy(payment: Payment, appointment: AppointmentView | None, cancelled_at: datetime | None) -> dict[str, Any]:
    """Refund policy hook for booking cancellations (window configurable; full / partial / none)."""
    window = settings.refund_full_window_hours
    base = {"payment_id": payment.id, "window_hours": window, "scheduled_at": appointment.scheduled_at.isoformat() if appointment else None}
    if payment.status not in CAPTURED_FAMILY:
        return {**base, "refundable_minor": 0, "refund_percent": 0, "rule": "not_captured"}
    left = remaining(payment)
    if left <= 0:
        return {**base, "refundable_minor": 0, "refund_percent": 0, "rule": "nothing_left"}
    if appointment is None:
        return {**base, "refundable_minor": left, "refund_percent": 100, "rule": "no_schedule"}
    at = cancelled_at or datetime.now(UTC)
    hours_before = (appointment.scheduled_at - at).total_seconds() / 3600
    if hours_before >= window:
        return {**base, "refundable_minor": left, "refund_percent": 100, "rule": "full_before_window"}
    if hours_before > 0:
        pct = settings.refund_partial_percent
        return {
            **base,
            "refundable_minor": min(left, apply_bps(payment.amount_captured_minor, pct * 100)),
            "refund_percent": pct,
            "rule": "partial_inside_window",
        }
    return {**base, "refundable_minor": 0, "refund_percent": 0, "rule": "none_after_start"}


async def policy_for(db: AsyncSession, payment: Payment, cancelled_at: datetime | None) -> dict[str, Any]:
    appointment = await db.get(AppointmentView, payment.subject_id) if payment.subject_type == "appointment" else None
    return evaluate_policy(payment, appointment, cancelled_at)


async def create_refund(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal | None,
    *,
    tenant_id: str,
    payment_id: str,
    body: dict[str, Any],
    key: str,
) -> Refund:
    digest = request_hash(body)
    async with sessions() as db, db.begin():
        payment = await lock_payment(db, payment_id)
        if payment is None or payment.tenant_id != tenant_id:
            raise not_found("Payment")
        refund = await db.scalar(select(Refund).where(Refund.payment_id == payment_id, Refund.idempotency_key == key))
        if refund is not None:
            if refund.request_hash != digest:
                raise conflict("Idempotency-Key reused with a different request", code="idempotency_conflict")
            if refund.status != "pending" or refund.processor_refund_id:
                return refund
        else:
            if payment.status not in CAPTURED_FAMILY:
                raise conflict(f"Only captured payments can be refunded (status {payment.status}); void instead")
            left = remaining(payment)
            if body.get("apply_policy"):
                cancelled_at = body.get("cancelled_at")
                decision = await policy_for(db, payment, cancelled_at)
                amount = min(decision["refundable_minor"], left)
                if amount <= 0:
                    raise unprocessable(f"Refund policy allows nothing ({decision['rule']})", "apply_policy")
            else:
                amount = int(body.get("amount_minor") or left)
            if amount <= 0 or amount > left:
                raise unprocessable(f"Refund exceeds the refundable balance ({left})", "amount_minor")
            payment.amount_refund_pending_minor += amount
            refund = Refund(
                id=str(ULID()),
                tenant_id=payment.tenant_id,
                payment_id=payment.id,
                amount_minor=amount,
                currency=payment.currency,
                reason=body["reason"],
                note=body.get("note"),
                status="pending",
                idempotency_key=key,
                request_hash=digest,
                requested_by=principal.user_id if principal else "system",
            )
            db.add(refund)
            try:
                await db.flush()
            except IntegrityError:
                raise conflict("Refund exceeds the refundable balance or duplicates a concurrent request") from None
        processor_payment_id = payment.processor_payment_id
    try:
        gr = await get_gateway().create_refund(
            processor_payment_id,
            amount_minor=refund.amount_minor,
            reason=refund.reason,
            metadata={"healuxa_refund_id": refund.id, "healuxa_payment_id": payment_id},
            idempotency_key=f"hx-re-{refund.id}",
        )
    except GatewayError:
        raise processor_unavailable() from None
    except GatewayRejected as exc:
        async with sessions() as db, db.begin():
            payment = await lock_payment(db, payment_id)
            locked = await db.scalar(select(Refund).where(Refund.id == refund.id).with_for_update())
            if locked.status == "pending":
                locked.status = "failed"
                locked.failure_reason = exc.code or "rejected"
                payment.amount_refund_pending_minor -= locked.amount_minor
        raise unprocessable(f"Processor rejected the refund: {exc.code or 'rejected'}") from None
    async with sessions() as db, db.begin():
        payment = await lock_payment(db, payment_id)
        locked = await db.scalar(select(Refund).where(Refund.id == refund.id).with_for_update())
        await apply_gateway_refund(db, payment, locked, gr)
        return locked


async def apply_gateway_refund(db: AsyncSession, payment: Payment, refund: Refund, gr: GatewayRefund) -> bool:
    """Apply processor refund state to locked payment + refund rows. Monotonic: settled refunds stay settled."""
    if not refund.processor_refund_id:
        refund.processor_refund_id = gr.id
    if refund.status != "pending" or gr.status == "pending":
        return False
    now = datetime.now(UTC)
    payment.amount_refund_pending_minor -= refund.amount_minor
    refund.updated_at = now
    if gr.status != "succeeded":
        refund.status = gr.status
        refund.failure_reason = gr.failure_reason
        await db.flush()
        return True
    refund.status = "succeeded"
    refund.succeeded_at = now
    payment.amount_refunded_minor += refund.amount_minor
    payment.status = "refunded" if payment.amount_refunded_minor >= payment.amount_captured_minor else "partially_refunded"
    payment.version += 1
    payment.updated_at = now
    await db.flush()
    lines = await post_refund(db, payment, refund_id=refund.id, amount_minor=refund.amount_minor, occurred_at=now)
    credit_note = await invoice_docs.issue(db, payment=payment, kind="credit_note", lines=lines, issued_at=now, refund_id=refund.id)
    await event_publisher.publish(
        db=db,
        event_type="payment.refunded",
        tenant_id=payment.tenant_id,
        payload={
            "payment_id": payment.id,
            "refund_id": refund.id,
            "user_id": payment.user_id,
            "amount": money(refund.amount_minor, payment.currency),
            "total_refunded": money(payment.amount_refunded_minor, payment.currency),
            "fully_refunded": payment.status == "refunded",
            "reason": refund.reason,
            "subject_type": payment.subject_type,
            "subject_id": payment.subject_id,
            "credit_note_id": credit_note.id,
            "refunded_at": now.isoformat(),
        },
    )
    return True


async def record_external_refund(db: AsyncSession, payment: Payment, gr: GatewayRefund) -> Refund | None:
    """A refund made outside Healuxa (e.g. processor dashboard): record it so the ledger stays complete."""
    if gr.amount_minor <= 0 or gr.amount_minor > remaining(payment):
        return None
    payment.amount_refund_pending_minor += gr.amount_minor
    refund = Refund(
        id=str(ULID()),
        tenant_id=payment.tenant_id,
        payment_id=payment.id,
        amount_minor=gr.amount_minor,
        currency=payment.currency,
        reason="processor_initiated",
        status="pending",
        processor_refund_id=gr.id,
        idempotency_key=f"processor:{gr.id}",
        request_hash="-",
        requested_by="processor",
    )
    db.add(refund)
    await db.flush()
    return refund


async def refund_view(db: AsyncSession, refund: Refund) -> dict[str, Any]:
    credit_note_id = await db.scalar(select(Invoice.id).where(Invoice.refund_id == refund.id))
    return {
        "id": refund.id,
        "payment_id": refund.payment_id,
        "amount": money(refund.amount_minor, refund.currency),
        "reason": refund.reason,
        "note": refund.note,
        "status": refund.status,
        "credit_note_id": credit_note_id,
        "created_at": refund.created_at.isoformat() if refund.created_at else None,
    }
