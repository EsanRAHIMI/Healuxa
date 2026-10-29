from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from healuxa_py_common.middleware.auth import Principal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.api.deps import get_db, require_permission
from payment_service.domain.access import is_finance, not_found, unprocessable
from payment_service.domain.ledger import payment_balance
from payment_service.domain.reconciliation import import_settlements, reconciliation_report, settlement_report
from payment_service.domain.webhooks import handle_webhook
from payment_service.events.publisher import money
from payment_service.infra.db import SessionLocal
from payment_service.infra.models import Dispute, LedgerEntry, LedgerJournal, PayeeMember, Payment

router = APIRouter(prefix="/v1")


class PayeeMemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payee_type: Literal["provider", "facility"]
    payee_id: str = Field(min_length=10, max_length=36)
    user_id: str = Field(min_length=10, max_length=36)


class ImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_: datetime = Field(alias="from")
    to: datetime


@router.post("/payments/webhooks/{gateway}", status_code=204)
async def payment_webhook(
    gateway: str,
    request: Request,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> Response:
    raw = await request.body()  # verified byte-for-byte before any JSON parsing
    await handle_webhook(SessionLocal, gateway, raw, stripe_signature)
    return Response(status_code=204)


@router.get("/payments/disputes")
async def list_disputes(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:manage"))],
    status: str | None = None,
) -> dict:
    query = select(Dispute).where(Dispute.tenant_id == principal.tenant_id)
    if status:
        query = query.where(Dispute.status == status)
    rows = await db.scalars(query.order_by(Dispute.created_at.desc()))
    return {
        "data": [
            {
                "id": d.id,
                "payment_id": d.payment_id,
                "amount": money(d.amount_minor, d.currency),
                "reason": d.reason,
                "status": d.status,
                "evidence_due_by": d.evidence_due_by.isoformat() if d.evidence_due_by else None,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
            for d in rows
        ]
    }


@router.post("/payments/payees/members", status_code=201)
async def add_payee_member(
    body: PayeeMemberIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:manage"))],
) -> dict:
    db.add(PayeeMember(tenant_id=principal.tenant_id, created_by=principal.user_id, **body.model_dump()))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    return body.model_dump()


@router.get("/payments/settlements/report")
async def get_settlement_report(
    payee_type: Literal["provider", "facility"],
    payee_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("payments:read"))],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> dict:
    if not is_finance(principal):
        member = await db.scalar(
            select(PayeeMember.id).where(
                PayeeMember.tenant_id == principal.tenant_id,
                PayeeMember.payee_type == payee_type,
                PayeeMember.payee_id == payee_id,
                PayeeMember.user_id == principal.user_id,
            )
        )
        if member is None:
            raise not_found("Payee")
    return await settlement_report(db, principal.tenant_id, payee_type, payee_id, start, to)


@router.post("/payments/settlements/import")
async def import_settlement_transactions(
    body: ImportIn,
    principal: Annotated[Principal, Depends(require_permission("finance:reconcile"))],
) -> dict:
    if body.to <= body.from_:
        raise unprocessable("'to' must be after 'from'", "to")
    return await import_settlements(SessionLocal, principal.tenant_id, body.from_, body.to)


@router.get("/payments/reconciliation")
async def get_reconciliation_report(
    start: Annotated[datetime, Query(alias="from")],
    to: datetime,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("finance:reconcile"))],
) -> dict:
    return await reconciliation_report(db, principal.tenant_id, start, to)


@router.get("/payments/{payment_id}/ledger")
async def get_payment_ledger(
    payment_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("finance:reconcile"))],
) -> dict:
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.tenant_id != principal.tenant_id:
        raise not_found("Payment")
    rows = await db.execute(
        select(LedgerEntry, LedgerJournal.kind)
        .join(LedgerJournal, LedgerJournal.id == LedgerEntry.journal_id)
        .where(LedgerEntry.payment_id == payment_id)
        .order_by(LedgerEntry.id)
    )
    data = [
        {
            "journal_id": e.journal_id,
            "kind": kind,
            "account": e.account,
            "line_code": e.line_code,
            "payee_type": e.payee_type,
            "payee_id": e.payee_id,
            "debit_minor": e.debit_minor,
            "credit_minor": e.credit_minor,
            "currency": e.currency,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e, kind in rows
    ]
    return {"balanced": await payment_balance(db, payment_id) == 0, "data": data}
