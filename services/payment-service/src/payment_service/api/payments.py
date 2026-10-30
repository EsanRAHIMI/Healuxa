"""HTTP surface for customers and payments staff: config, quotes, payments, capture/void, refunds.

Thin layer: validates input (extra fields forbidden, so clients cannot smuggle amounts), applies RBAC via
identity permissions, and delegates to domain/* which owns state, processor calls and events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, Query, Response
from healuxa_py_common.middleware.auth import Principal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.api.deps import get_db, require_permission
from payment_service.config import settings
from payment_service.domain import payments as flow
from payment_service.domain import quotes as quote_flow
from payment_service.domain import refunds as refund_flow
from payment_service.domain.access import bad_request, can_see_payment, is_manager, not_found, unprocessable
from payment_service.infra.db import SessionLocal
from payment_service.infra.models import Payment, Refund

router = APIRouter(prefix="/v1")

IdempotencyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _key(value: str | None) -> str:
    if not value or not 8 <= len(value) <= 128:
        raise bad_request("Idempotency-Key header (8-128 chars) is required", "Idempotency-Key")
    return value


class QuoteLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal["professional_fee", "facility_fee", "platform_fee", "concierge_fee", "third_party_fee"]
    description: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=64)
    net_minor: int = Field(ge=0, le=100_000_000)
    payee_type: Literal["provider", "facility", "healuxa"] | None = None
    payee_id: str | None = Field(default=None, max_length=36)


class CreateQuoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_type: Literal["appointment", "concierge_case", "membership"]
    subject_id: str = Field(min_length=10, max_length=36)
    user_id: str | None = Field(default=None, max_length=36)
    lines: list[QuoteLineIn] | None = Field(default=None, max_length=20)


class CreatePaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote_id: str = Field(min_length=10, max_length=26)
    capture_method: Literal["automatic", "manual"] | None = None


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["requested_by_customer", "provider_declined", "duplicate", "fraudulent", "abandoned"] | None = None


class CreateRefundIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_minor: int | None = Field(default=None, ge=1)
    apply_policy: bool = False
    cancelled_at: datetime | None = None
    reason: Literal[
        "requested_by_customer", "appointment_cancelled", "provider_declined", "duplicate", "fraudulent", "service_issue", "goodwill"
    ]
    note: str | None = Field(default=None, max_length=500)


@router.get("/payments/config")
async def get_payment_config() -> dict:
    return {
        "gateway": settings.payment_gateway,
        "publishable_key": settings.stripe_publishable_key or None,
        "currency": settings.currency,
        "live_mode": settings.payments_live_mode,
        "platform_fee": {"rate_bps": settings.platform_fee_bps, "fixed_minor": settings.platform_fee_fixed_minor, "label": quote_flow.platform_fee_label()},
        "tax": {"name": settings.vat_name, "rates_bps": settings.vat_rates_bps, "status": quote_flow.tax_status()},
        "memberships_enabled": settings.membership_payments_enabled,
    }


@router.post("/payment-quotes", status_code=201)
async def create_payment_quote(
    body: CreateQuoteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:create"))],
) -> dict:
    quote = await quote_flow.create_quote(db, principal, body.model_dump(exclude_none=True))
    await db.commit()
    return quote_flow.quote_view(quote)


@router.get("/payment-quotes/{quote_id}")
async def get_payment_quote(
    quote_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:read"))],
) -> dict:
    quote = await quote_flow.get_quote_for(db, principal, quote_id)
    used = await db.scalar(select(Payment.id).where(Payment.quote_id == quote.id)) is not None
    return quote_flow.quote_view(quote, used=used)


@router.get("/payments")
async def list_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:read"))],
    user_id: str | None = None,
    subject_id: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> dict:
    query = select(Payment).where(Payment.tenant_id == principal.tenant_id)
    if is_manager(principal):
        if user_id:
            query = query.where(Payment.user_id == user_id)
    else:
        query = query.where(Payment.user_id == principal.user_id)
    if subject_id:
        query = query.where(Payment.subject_id == subject_id)
    if status:
        query = query.where(Payment.status == status)
    if cursor:
        query = query.where(Payment.id < cursor)
    rows = list(await db.scalars(query.order_by(Payment.id.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "data": [await flow.payment_view(db, p) for p in rows],
        "page": {"next_cursor": rows[-1].id if has_more else None, "limit": limit, "has_more": has_more},
    }


@router.post("/payments", status_code=201)
async def create_payment(
    body: CreatePaymentIn,
    response: Response,
    principal: Annotated[Principal, Depends(require_permission("payments:create"))],
    idempotency_key: IdempotencyHeader = None,
) -> dict:
    payment, secret = await flow.create_payment(
        SessionLocal, principal, quote_id=body.quote_id, capture_method=body.capture_method, key=_key(idempotency_key)
    )
    response.headers["Location"] = f"/v1/payments/{payment.id}"
    async with SessionLocal() as db:
        return await flow.payment_view(db, payment, client_secret=secret)


@router.get("/payments/{payment_id}")
async def get_payment(
    payment_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:read"))],
) -> dict:
    return await flow.payment_view(db, await flow.get_visible(db, principal, payment_id))


@router.post("/payments/{payment_id}/refresh")
async def refresh_payment(
    payment_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:read"))],
) -> dict:
    payment = await flow.get_visible(db, principal, payment_id)
    payment, secret = await flow.refresh(SessionLocal, payment)
    return await flow.payment_view(db, payment, client_secret=secret if payment.user_id == principal.user_id else None)


@router.post("/payments/{payment_id}/capture")
async def capture_payment(
    payment_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:manage"))],
) -> dict:
    payment = await flow.capture(SessionLocal, payment_id, tenant_id=principal.tenant_id)
    return await flow.payment_view(db, payment)


@router.post("/payments/{payment_id}/cancel")
async def cancel_payment(
    payment_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:manage"))],
    body: Annotated[CancelIn | None, Body()] = None,
) -> dict:
    payment = await flow.cancel(SessionLocal, payment_id, reason=body.reason if body else None, tenant_id=principal.tenant_id)
    return await flow.payment_view(db, payment)


@router.get("/payments/{payment_id}/refunds")
async def list_refunds(
    payment_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:read"))],
) -> dict:
    payment = await flow.get_visible(db, principal, payment_id)
    refunds = await db.scalars(select(Refund).where(Refund.payment_id == payment.id).order_by(Refund.id))
    return {"data": [await refund_flow.refund_view(db, r) for r in refunds]}


@router.post("/payments/{payment_id}/refunds", status_code=201)
async def create_refund(
    payment_id: str,
    body: CreateRefundIn,
    principal: Annotated[Principal, Depends(require_permission("payments:refund"))],
    idempotency_key: IdempotencyHeader = None,
) -> dict:
    if body.amount_minor is not None and body.apply_policy:
        raise unprocessable("Use either amount_minor or apply_policy", "amount_minor")
    refund = await refund_flow.create_refund(
        SessionLocal,
        principal,
        tenant_id=principal.tenant_id,
        payment_id=payment_id,
        body=body.model_dump(exclude_none=True),
        key=_key(idempotency_key),
    )
    async with SessionLocal() as db:
        return await refund_flow.refund_view(db, refund)


@router.get("/payments/{payment_id}/refund-policy")
async def evaluate_refund_policy(
    payment_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:read"))],
    cancelled_at: datetime | None = None,
) -> dict:
    payment = await db.get(Payment, payment_id)
    if payment is None or not can_see_payment(principal, tenant_id=payment.tenant_id, user_id=payment.user_id):
        raise not_found("Payment")
    return await refund_flow.policy_for(db, payment, cancelled_at)
