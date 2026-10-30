"""Settlement import (processor balance transactions + payouts) and reconciliation against our ledger."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payment_service.domain.access import processor_unavailable
from payment_service.domain.ledger import Posting, post_journal
from payment_service.infra.gateways import get_gateway
from payment_service.infra.gateways.base import GatewayBalanceTransaction, GatewayError
from payment_service.infra.models import BalanceTransaction, LedgerEntry, LedgerJournal, Payment, Refund

CHARGE_TYPES = {"charge", "payment"}
REFUND_TYPES = {"refund", "payment_refund"}


async def import_settlements(sessions: async_sessionmaker[AsyncSession], tenant_id: str, start: datetime, end: datetime) -> dict[str, int]:
    gateway = get_gateway()
    try:
        txns = await gateway.list_balance_transactions(created_gte=start, created_lt=end)
        payout_of: dict[str, str] = {}
        for txn in txns:
            if txn.type == "payout" and txn.source_id:
                payout_of[txn.id] = txn.source_id
                for member in await gateway.list_payout_transactions(txn.source_id):
                    payout_of[member.id] = txn.source_id
    except GatewayError:
        raise processor_unavailable() from None
    imported = skipped = payouts = 0
    async with sessions() as db, db.begin():
        for txn in txns:
            inserted = await db.scalar(
                insert(BalanceTransaction)
                .values(
                    tenant_id=tenant_id,
                    processor=gateway.name,
                    processor_txn_id=txn.id,
                    type=txn.type,
                    source_id=txn.source_id,
                    payout_id=payout_of.get(txn.id),
                    amount_minor=txn.amount_minor,
                    fee_minor=txn.fee_minor,
                    net_minor=txn.net_minor,
                    currency=txn.currency,
                    created=txn.created,
                )
                .on_conflict_do_nothing(constraint="uq_balance_transactions_id")
                .returning(BalanceTransaction.id)
            )
            if inserted is None:
                skipped += 1
            else:
                imported += 1
            await _post_settlement_journals(db, tenant_id, txn)
            if txn.type == "payout":
                payouts += 1
        # Transactions imported earlier may only now be known to belong to a payout.
        for txn_id, payout_id in payout_of.items():
            await db.execute(
                update(BalanceTransaction)
                .where(BalanceTransaction.processor_txn_id == txn_id, BalanceTransaction.payout_id.is_(None))
                .values(payout_id=payout_id)
            )
    return {"imported": imported, "skipped": skipped, "payouts": payouts}


async def _post_settlement_journals(db: AsyncSession, tenant_id: str, txn: GatewayBalanceTransaction) -> None:
    if txn.type in CHARGE_TYPES and txn.fee_minor > 0:
        payment_id = await db.scalar(select(Payment.id).where(Payment.processor_charge_id == txn.source_id, Payment.tenant_id == tenant_id))
        await post_journal(
            db,
            tenant_id=tenant_id,
            key=f"fee:{txn.id}",
            kind="processor_fee",
            currency=txn.currency,
            occurred_at=txn.created,
            payment_id=payment_id,
            postings=[Posting("processor_fees", debit=txn.fee_minor), Posting("processor_clearing", credit=txn.fee_minor)],
        )
    elif txn.type == "payout" and txn.amount_minor < 0:
        await post_journal(
            db,
            tenant_id=tenant_id,
            key=f"payout:{txn.id}",
            kind="payout",
            currency=txn.currency,
            occurred_at=txn.created,
            postings=[Posting("bank", debit=-txn.amount_minor), Posting("processor_clearing", credit=-txn.amount_minor)],
        )


def _flag(kind: str, *, payment_id: str | None = None, ref: str | None = None, expected: int | None = None, actual: int | None = None) -> dict[str, Any]:
    return {"kind": kind, "payment_id": payment_id, "processor_ref": ref, "expected_minor": expected, "actual_minor": actual}


async def reconciliation_report(db: AsyncSession, tenant_id: str, start: datetime, end: datetime) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    matched = 0
    txns = list(
        await db.scalars(
            select(BalanceTransaction).where(
                BalanceTransaction.tenant_id == tenant_id, BalanceTransaction.created >= start, BalanceTransaction.created < end
            )
        )
    )
    payments = list(
        await db.scalars(
            select(Payment).where(Payment.tenant_id == tenant_id, Payment.captured_at >= start, Payment.captured_at < end)
        )
    )
    by_charge = {p.processor_charge_id: p for p in payments if p.processor_charge_id}
    seen_charges: set[str] = set()
    totals: dict[str, int] = defaultdict(int)

    for txn in txns:
        if txn.type in CHARGE_TYPES:
            totals["processor_charges_minor"] += txn.amount_minor
            totals["processor_fees_minor"] += txn.fee_minor
            payment = by_charge.get(txn.source_id) or await db.scalar(
                select(Payment).where(Payment.processor_charge_id == txn.source_id, Payment.tenant_id == tenant_id)
            )
            if payment is None:
                mismatches.append(_flag("unknown_processor_transaction", ref=txn.processor_txn_id, actual=txn.amount_minor))
                continue
            seen_charges.add(txn.source_id)
            if txn.currency != payment.currency:
                mismatches.append(_flag("currency_mismatch", payment_id=payment.id, ref=txn.processor_txn_id))
            elif txn.amount_minor != payment.amount_captured_minor:
                mismatches.append(
                    _flag("amount_mismatch", payment_id=payment.id, ref=txn.processor_txn_id, expected=payment.amount_captured_minor, actual=txn.amount_minor)
                )
            else:
                matched += 1
        elif txn.type in REFUND_TYPES:
            totals["processor_refunds_minor"] += -txn.amount_minor
            refund = await db.scalar(select(Refund).where(Refund.processor_refund_id == txn.source_id, Refund.tenant_id == tenant_id))
            if refund is None:
                mismatches.append(_flag("unknown_processor_transaction", ref=txn.processor_txn_id, actual=txn.amount_minor))
            elif refund.status != "succeeded" or -txn.amount_minor != refund.amount_minor:
                mismatches.append(
                    _flag("refund_mismatch", payment_id=refund.payment_id, ref=txn.processor_txn_id, expected=refund.amount_minor, actual=-txn.amount_minor)
                )
            else:
                matched += 1
        elif txn.type == "payout":
            totals["payouts_minor"] += -txn.amount_minor
            members_net = await db.scalar(
                select(func.coalesce(func.sum(BalanceTransaction.net_minor), 0)).where(
                    BalanceTransaction.tenant_id == tenant_id,
                    BalanceTransaction.payout_id == txn.source_id,
                    BalanceTransaction.type != "payout",
                )
            )
            if int(members_net) != -txn.amount_minor:
                mismatches.append(_flag("payout_mismatch", ref=txn.source_id, expected=int(members_net), actual=-txn.amount_minor))
            else:
                matched += 1

    for payment in payments:
        totals["captured_minor"] += payment.amount_captured_minor
        if payment.processor_charge_id not in seen_charges:
            mismatches.append(_flag("missing_processor_transaction", payment_id=payment.id, ref=payment.processor_charge_id, expected=payment.amount_captured_minor))
        balance = await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.debit_minor), 0), func.coalesce(func.sum(LedgerEntry.credit_minor), 0)).where(
                LedgerEntry.payment_id == payment.id
            )
        )
        debit, credit = balance.one()
        if int(debit) != int(credit):
            mismatches.append(_flag("ledger_unbalanced", payment_id=payment.id, expected=int(debit), actual=int(credit)))
        clearing = await db.scalar(
            select(func.coalesce(func.sum(LedgerEntry.debit_minor), 0))
            .join(LedgerJournal, LedgerJournal.id == LedgerEntry.journal_id)
            .where(LedgerJournal.payment_id == payment.id, LedgerJournal.kind == "capture", LedgerEntry.account == "processor_clearing")
        )
        if int(clearing) != payment.amount_captured_minor or payment.amount_captured_minor != payment.amount_minor:
            mismatches.append(_flag("ledger_capture_mismatch", payment_id=payment.id, expected=payment.amount_minor, actual=int(clearing)))

    refunds = await db.scalars(
        select(Refund).where(Refund.tenant_id == tenant_id, Refund.status == "succeeded", Refund.succeeded_at >= start, Refund.succeeded_at < end)
    )
    refund_sources = {t.source_id for t in txns if t.type in REFUND_TYPES}
    for refund in refunds:
        totals["refunded_minor"] += refund.amount_minor
        if refund.processor_refund_id not in refund_sources:
            mismatches.append(_flag("missing_processor_transaction", payment_id=refund.payment_id, ref=refund.processor_refund_id, expected=refund.amount_minor))
    return {"from": start.isoformat(), "to": end.isoformat(), "matched": matched, "totals": dict(totals), "mismatches": mismatches}


async def settlement_report(
    db: AsyncSession, tenant_id: str, payee_type: str, payee_id: str, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    account = {"provider": "provider_revenue", "facility": "facility_revenue"}[payee_type]
    query = select(LedgerEntry).where(
        LedgerEntry.tenant_id == tenant_id,
        LedgerEntry.payee_type == payee_type,
        LedgerEntry.payee_id == payee_id,
        LedgerEntry.account == account,
    )
    if start:
        query = query.where(LedgerEntry.occurred_at >= start)
    if end:
        query = query.where(LedgerEntry.occurred_at < end)
    entries = list(await db.scalars(query.order_by(LedgerEntry.occurred_at, LedgerEntry.id)))
    gross = sum(e.credit_minor for e in entries)
    refunded = sum(e.debit_minor for e in entries)
    currency = entries[0].currency if entries else "AED"
    return {
        "payee_type": payee_type,
        "payee_id": payee_id,
        "currency": currency,
        "gross_minor": gross,
        "refunded_minor": refunded,
        "net_minor": gross - refunded,
        # Revenue lines only — no customer identifiers are exposed to providers/facilities.
        "lines": [
            {
                "payment_id": e.payment_id,
                "kind": e.kind,
                "line_code": e.line_code,
                "amount_minor": e.credit_minor - e.debit_minor,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in entries
        ],
    }
