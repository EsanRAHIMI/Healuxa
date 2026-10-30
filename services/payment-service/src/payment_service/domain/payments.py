"""Payment lifecycle: create (idempotent), apply processor state, capture, void, refresh.

State only moves on processor truth — a verified webhook or a server-side API response/retrieval.
Processor calls are made outside database transactions; rows are locked (SELECT ... FOR UPDATE) while
state is applied, so webhooks, API commands and event consumers can race safely.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from payment_service.config import settings
from payment_service.domain import invoices as invoice_docs
from payment_service.domain.access import (
    can_see_payment,
    conflict,
    not_found,
    processor_unavailable,
    unprocessable,
)
from payment_service.domain.ledger import post_capture
from payment_service.domain.state import CAPTURED_FAMILY, should_apply
from payment_service.events.publisher import event_publisher, money
from payment_service.infra.gateways import get_gateway
from payment_service.infra.gateways.base import GatewayError, GatewayPayment, GatewayRejected
from payment_service.infra.gateways.stripe import interval_for
from payment_service.infra.models import IdempotencyRecord, Invoice, MembershipView, Payment, ProcessorCustomer, Quote

logger = logging.getLogger(__name__)

CONFIRMABLE = {"pending", "failed"}


def request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


async def lock_payment(db: AsyncSession, payment_id: str) -> Payment | None:
    return await db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())


async def lock_by_processor_id(db: AsyncSession, processor: str, processor_payment_id: str) -> Payment | None:
    return await db.scalar(
        select(Payment).where(Payment.processor == processor, Payment.processor_payment_id == processor_payment_id).with_for_update()
    )


def _base_payload(payment: Payment) -> dict[str, Any]:
    return {
        "payment_id": payment.id,
        "user_id": payment.user_id,
        "amount": money(payment.amount_minor, payment.currency),
        "gateway": "stripe",
        "subject_type": payment.subject_type,
        "subject_id": payment.subject_id,
    }


async def apply_gateway_payment(db: AsyncSession, payment: Payment, gp: GatewayPayment, *, event_at: datetime | None) -> bool:
    """Apply processor-reported state to a locked payment. Returns True if the status changed."""
    payment.processor_status = gp.raw_status
    if gp.charge_id and not payment.processor_charge_id:
        payment.processor_charge_id = gp.charge_id
    target = gp.status
    current = payment.status
    if current in CAPTURED_FAMILY and target == "succeeded":
        return False
    if not should_apply(current, target, event_at=event_at, last_event_at=payment.last_event_at):
        if current != target:
            logger.info("ignored out-of-order/illegal processor status %s -> %s for %s", current, target, payment.id)
        return False
    now = datetime.now(UTC)
    payment.status = target
    payment.version += 1
    payment.updated_at = now
    if event_at and (payment.last_event_at is None or event_at > payment.last_event_at):
        payment.last_event_at = event_at
    if target == "authorized":
        payment.amount_authorized_minor = gp.amount_capturable_minor or payment.amount_minor
        payment.authorized_at = now
        await event_publisher.publish(
            db=db,
            event_type="payment.authorized",
            tenant_id=payment.tenant_id,
            payload={**_base_payload(payment), "quote_id": payment.quote_id, "provider_id": payment.provider_id,
                     "facility_id": payment.facility_id, "authorized_at": now.isoformat()},
        )
    elif target == "succeeded":
        await _on_captured(db, payment, gp.amount_received_minor or payment.amount_minor, now)
    elif target == "failed":
        payment.failure_code = gp.failure_code or "payment_failed"
        await event_publisher.publish(
            db=db,
            event_type="payment.failed",
            tenant_id=payment.tenant_id,
            payload={**_base_payload(payment), "subscription_id": _subscription_id(payment), "failure_code": payment.failure_code,
                     "failed_at": now.isoformat()},
        )
    elif target == "canceled":
        payment.canceled_at = now
        await event_publisher.publish(
            db=db,
            event_type="payment.canceled",
            tenant_id=payment.tenant_id,
            payload={**_base_payload(payment), "reason": payment.cancel_reason, "canceled_at": now.isoformat()},
        )
    await db.flush()
    return True


def _subscription_id(payment: Payment) -> str | None:
    return payment.subject_id if payment.subject_type == "membership" else None


async def _on_captured(db: AsyncSession, payment: Payment, amount_received: int, now: datetime) -> None:
    payment.amount_captured_minor = amount_received
    payment.amount_authorized_minor = max(payment.amount_authorized_minor, amount_received)
    payment.captured_at = now
    await post_capture(db, payment, occurred_at=now)
    invoice = await invoice_docs.issue(db, payment=payment, kind="invoice", lines=payment.lines, issued_at=now)
    await event_publisher.publish(
        db=db,
        event_type="payment.succeeded",
        tenant_id=payment.tenant_id,
        payload={
            "payment_id": payment.id,
            "user_id": payment.user_id,
            "subscription_id": _subscription_id(payment),
            "invoice_id": invoice.id,
            "amount": money(amount_received, payment.currency),
            "gateway": "stripe",
            "purpose": payment.subject_type,
            "subject_type": payment.subject_type,
            "subject_id": payment.subject_id,
            "quote_id": payment.quote_id,
            "provider_id": payment.provider_id,
            "facility_id": payment.facility_id,
            "capture_method": payment.capture_method,
            "billing_reason": payment.billing_reason,
            "billing_period_end": payment.billing_period_end.isoformat() if payment.billing_period_end else None,
            "captured_at": now.isoformat(),
        },
    )
    platform = sum(int(line["net_minor"]) for line in payment.lines if line["code"] == "platform_fee")
    if payment.provider_id and platform:
        gross = sum(int(line["net_minor"]) for line in payment.lines if line["payee_type"] in {"provider", "facility"})
        await event_publisher.publish(
            db=db,
            event_type="commission.computed",
            tenant_id=payment.tenant_id,
            payload={
                "commission_id": str(ULID()),
                "provider_id": payment.provider_id,
                "payment_id": payment.id,
                "appointment_id": payment.subject_id if payment.subject_type == "appointment" else None,
                "gross": money(gross, payment.currency),
                "amount": money(platform, payment.currency),
                "rate": round(platform / gross, 4) if gross else 0,
                "computed_at": now.isoformat(),
            },
        )


# ── create ────────────────────────────────────────────────────────────────────


def _capture_method(quote: Quote, requested: str | None) -> str:
    if quote.subject_type == "membership":
        if requested == "manual":
            raise unprocessable("Memberships are always charged automatically", "capture_method")
        return "automatic"
    if requested:
        return requested
    return settings.appointment_capture_method if quote.subject_type == "appointment" else "automatic"


async def create_payment(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, *, quote_id: str, capture_method: str | None, key: str
) -> tuple[Payment, str | None]:
    digest = request_hash({"quote_id": quote_id, "capture_method": capture_method})
    async with sessions() as db, db.begin():
        record = await db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == principal.tenant_id,
                IdempotencyRecord.user_id == principal.user_id,
                IdempotencyRecord.operation == "create_payment",
                IdempotencyRecord.key == key,
            )
        )
        if record is not None:
            if record.request_hash != digest:
                raise conflict("Idempotency-Key reused with a different request", code="idempotency_conflict")
            payment = await db.get(Payment, record.resource_id)
            completed = record.completed
        else:
            quote = await db.scalar(
                select(Quote).where(Quote.id == quote_id, Quote.tenant_id == principal.tenant_id).with_for_update()
            )
            if quote is None or quote.user_id != principal.user_id:
                raise not_found("Quote")
            if quote.expires_at <= datetime.now(UTC):
                raise unprocessable("Quote expired; request a new quote", "quote_id")
            if await db.scalar(select(Payment.id).where(Payment.quote_id == quote.id)):
                raise conflict("A payment already exists for this quote")
            method = _capture_method(quote, capture_method)
            payment = Payment(
                id=str(ULID()),
                tenant_id=quote.tenant_id,
                user_id=quote.user_id,
                quote_id=quote.id,
                subject_type=quote.subject_type,
                subject_id=quote.subject_id,
                provider_id=quote.provider_id,
                facility_id=quote.facility_id,
                currency=quote.currency,
                lines=quote.lines,
                amount_minor=quote.total_minor,
                capture_method=method,
                status="pending",
                processor=get_gateway().name,
                billing_reason="subscription_create" if quote.subject_type == "membership" else "one_off",
            )
            db.add(payment)
            db.add(
                IdempotencyRecord(
                    tenant_id=principal.tenant_id,
                    user_id=principal.user_id,
                    operation="create_payment",
                    key=key,
                    request_hash=digest,
                    resource_id=payment.id,
                )
            )
            try:
                await db.flush()
            except IntegrityError:
                raise conflict("A concurrent request with this Idempotency-Key or quote is in progress") from None
            completed = False

    if completed and payment.processor_payment_id:
        secret = None
        if payment.status in CONFIRMABLE:
            try:
                secret = (await get_gateway().retrieve_payment(payment.processor_payment_id)).client_secret
            except GatewayError:
                secret = None
        return payment, secret

    gp = await _open_at_processor(sessions, payment)
    async with sessions() as db, db.begin():
        locked = await lock_payment(db, payment.id)
        assert locked is not None
        locked.processor_payment_id = gp.id
        await apply_gateway_payment(db, locked, gp, event_at=None)
        record = await db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == principal.tenant_id,
                IdempotencyRecord.user_id == principal.user_id,
                IdempotencyRecord.operation == "create_payment",
                IdempotencyRecord.key == key,
            )
        )
        if record is not None:
            record.completed = True
        payment = locked
    return payment, gp.client_secret


async def _open_at_processor(sessions: async_sessionmaker[AsyncSession], payment: Payment) -> GatewayPayment:
    gateway = get_gateway()
    try:
        if payment.subject_type == "membership":
            return await _open_membership(sessions, payment)
        return await gateway.create_payment(
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            capture_method=payment.capture_method,
            metadata={"healuxa_payment_id": payment.id, "healuxa_tenant": payment.tenant_id, "healuxa_subject": payment.subject_type},
            description=f"Healuxa payment {payment.id}",
            idempotency_key=f"hx-pay-{payment.id}",
        )
    except GatewayError:
        raise processor_unavailable() from None
    except GatewayRejected as exc:
        raise unprocessable(f"Processor rejected the payment: {exc.code or 'rejected'}") from None


async def _open_membership(sessions: async_sessionmaker[AsyncSession], payment: Payment) -> GatewayPayment:
    gateway = get_gateway()
    async with sessions() as db:
        membership = await db.get(MembershipView, payment.subject_id)
        customer = await db.scalar(
            select(ProcessorCustomer.processor_customer_id).where(
                ProcessorCustomer.tenant_id == payment.tenant_id,
                ProcessorCustomer.user_id == payment.user_id,
                ProcessorCustomer.processor == gateway.name,
            )
        )
    if membership is None:
        raise not_found("Subscription")
    if customer is None:
        customer = await gateway.create_customer(reference=payment.user_id, idempotency_key=f"hx-cus-{payment.tenant_id}-{payment.user_id}")
        async with sessions() as db, db.begin():
            db.add(ProcessorCustomer(tenant_id=payment.tenant_id, user_id=payment.user_id, processor=gateway.name, processor_customer_id=customer))
            try:
                await db.flush()
            except IntegrityError:
                pass
    interval, count = interval_for(membership.billing_cycle)
    sub = await gateway.create_subscription(
        customer_id=customer,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        interval=interval,
        interval_count=count,
        product_name=f"Healuxa membership {membership.plan_id}",
        metadata={"healuxa_subscription_id": membership.subscription_id, "healuxa_payment_id": payment.id, "healuxa_tenant": payment.tenant_id},
        idempotency_key=f"hx-sub-{payment.id}",
    )
    if sub.latest_payment is None:
        raise GatewayError("subscription has no first payment")
    async with sessions() as db, db.begin():
        locked = await db.scalar(select(MembershipView).where(MembershipView.subscription_id == membership.subscription_id).with_for_update())
        locked.processor_subscription_id = sub.id
        locked.processor_item_id = sub.item_id
        locked.processor_status = sub.status
        locked.lines = payment.lines
        p = await lock_payment(db, payment.id)
        p.processor_subscription_id = sub.id
    return sub.latest_payment


# ── commands ──────────────────────────────────────────────────────────────────


async def capture(sessions: async_sessionmaker[AsyncSession], payment_id: str, *, tenant_id: str | None = None) -> Payment:
    async with sessions() as db:
        payment = await db.get(Payment, payment_id)
    if payment is None or (tenant_id and payment.tenant_id != tenant_id):
        raise not_found("Payment")
    if payment.status in CAPTURED_FAMILY:
        return payment
    if payment.status != "authorized" or not payment.processor_payment_id:
        raise conflict(f"Only authorized payments can be captured (status {payment.status})")
    try:
        gp = await get_gateway().capture_payment(payment.processor_payment_id, idempotency_key=f"hx-cap-{payment.id}")
    except GatewayError:
        raise processor_unavailable() from None
    except GatewayRejected as exc:
        raise conflict(f"Processor refused capture: {exc.code or 'rejected'}") from None
    async with sessions() as db, db.begin():
        locked = await lock_payment(db, payment_id)
        await apply_gateway_payment(db, locked, gp, event_at=None)
        return locked


async def cancel(sessions: async_sessionmaker[AsyncSession], payment_id: str, *, reason: str | None, tenant_id: str | None = None) -> Payment:
    async with sessions() as db:
        payment = await db.get(Payment, payment_id)
    if payment is None or (tenant_id and payment.tenant_id != tenant_id):
        raise not_found("Payment")
    if payment.status == "canceled":
        return payment
    if payment.status in CAPTURED_FAMILY:
        raise conflict("Captured payments are refunded, not canceled")
    if not payment.processor_payment_id:
        raise conflict("Payment was never opened at the processor")
    try:
        gp = await get_gateway().cancel_payment(payment.processor_payment_id, reason=reason, idempotency_key=f"hx-void-{payment.id}")
    except GatewayError:
        raise processor_unavailable() from None
    except GatewayRejected as exc:
        raise conflict(f"Processor refused cancellation: {exc.code or 'rejected'}") from None
    async with sessions() as db, db.begin():
        locked = await lock_payment(db, payment_id)
        locked.cancel_reason = reason
        await apply_gateway_payment(db, locked, gp, event_at=None)
        return locked


async def refresh(sessions: async_sessionmaker[AsyncSession], payment: Payment) -> tuple[Payment, str | None]:
    if not payment.processor_payment_id:
        return payment, None
    try:
        gp = await get_gateway().retrieve_payment(payment.processor_payment_id)
    except GatewayError:
        raise processor_unavailable() from None
    async with sessions() as db, db.begin():
        locked = await lock_payment(db, payment.id)
        await apply_gateway_payment(db, locked, gp, event_at=None)
    return locked, gp.client_secret if locked.status in CONFIRMABLE else None


# ── reads ─────────────────────────────────────────────────────────────────────


async def get_visible(db: AsyncSession, principal: Principal, payment_id: str) -> Payment:
    payment = await db.get(Payment, payment_id)
    if payment is None or not can_see_payment(principal, tenant_id=payment.tenant_id, user_id=payment.user_id):
        raise not_found("Payment")
    return payment


async def payment_view(db: AsyncSession, payment: Payment, *, client_secret: str | None = None) -> dict[str, Any]:
    invoice_id = await db.scalar(select(Invoice.id).where(Invoice.payment_id == payment.id, Invoice.kind == "invoice"))
    iso = lambda v: v.isoformat() if v else None  # noqa: E731
    return {
        "id": payment.id,
        "user_id": payment.user_id,
        "quote_id": payment.quote_id,
        "subject_type": payment.subject_type,
        "subject_id": payment.subject_id,
        "amount": money(payment.amount_minor, payment.currency),
        "amount_authorized_minor": payment.amount_authorized_minor,
        "amount_captured_minor": payment.amount_captured_minor,
        "amount_refunded_minor": payment.amount_refunded_minor,
        "status": payment.status,
        "capture_method": payment.capture_method,
        "gateway": "stripe",
        "client_secret": client_secret,
        "failure_code": payment.failure_code,
        "lines": payment.lines,
        "invoice_id": invoice_id,
        "created_at": iso(payment.created_at),
        "authorized_at": iso(payment.authorized_at),
        "captured_at": iso(payment.captured_at),
        "canceled_at": iso(payment.canceled_at),
    }
