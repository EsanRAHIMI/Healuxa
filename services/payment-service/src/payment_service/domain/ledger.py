"""Double-entry ledger. Every journal balances (Σ debit = Σ credit); journals are keyed so a posting
happens at most once whatever the number of webhook deliveries.

Accounts: processor_clearing (funds held at the processor), provider_revenue / facility_revenue /
healuxa_revenue (by payee), vat_payable, processor_fees, disputes, bank (payouts), suspense
(differences to investigate; reconciliation flags them).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from payment_service.domain.money import allocate
from payment_service.infra.models import LedgerEntry, LedgerJournal, Payment

REVENUE_ACCOUNT = {"provider": "provider_revenue", "facility": "facility_revenue", "healuxa": "healuxa_revenue"}


@dataclass(frozen=True)
class Posting:
    account: str
    debit: int = 0
    credit: int = 0
    line_code: str | None = None
    payee_type: str | None = None
    payee_id: str | None = None


class UnbalancedJournal(Exception):
    pass


async def post_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    key: str,
    kind: str,
    currency: str,
    occurred_at: datetime,
    postings: list[Posting],
    payment_id: str | None = None,
    refund_id: str | None = None,
) -> bool:
    """Insert a balanced journal. Returns False if a journal with this key already exists."""
    postings = [p for p in postings if p.debit or p.credit]
    if sum(p.debit for p in postings) != sum(p.credit for p in postings):
        raise UnbalancedJournal(key)
    if any(p.debit < 0 or p.credit < 0 or (p.debit and p.credit) for p in postings):
        raise UnbalancedJournal(f"{key}: invalid posting")
    journal_id = str(ULID())
    inserted = await db.scalar(
        insert(LedgerJournal)
        .values(id=journal_id, tenant_id=tenant_id, key=key, kind=kind, payment_id=payment_id, refund_id=refund_id, occurred_at=occurred_at)
        .on_conflict_do_nothing(index_elements=["key"])
        .returning(LedgerJournal.id)
    )
    if inserted is None:
        return False
    for p in postings:
        db.add(
            LedgerEntry(
                journal_id=journal_id,
                tenant_id=tenant_id,
                payment_id=payment_id,
                kind=kind,
                account=p.account,
                line_code=p.line_code,
                payee_type=p.payee_type,
                payee_id=p.payee_id,
                debit_minor=p.debit,
                credit_minor=p.credit,
                currency=currency,
                occurred_at=occurred_at,
            )
        )
    await db.flush()
    return True


def _buckets(lines: list[dict]) -> list[tuple[tuple, int]]:
    """(account, line_code, payee_type, payee_id) buckets with their captured amounts, net then VAT."""
    out: list[tuple[tuple, int]] = []
    for line in lines:
        payee_type = line["payee_type"]
        out.append(((REVENUE_ACCOUNT[payee_type], line["code"], payee_type, line.get("payee_id")), int(line["net_minor"])))
    for line in lines:
        out.append((("vat_payable", line["code"], None, None), int(line["vat_minor"])))
    return out


async def post_capture(db: AsyncSession, payment: Payment, *, occurred_at: datetime, key_suffix: str = "") -> None:
    captured = payment.amount_captured_minor
    postings = [Posting("processor_clearing", debit=captured)]
    expected = 0
    for (account, code, payee_type, payee_id), amount in _buckets(payment.lines):
        postings.append(Posting(account, credit=amount, line_code=code, payee_type=payee_type, payee_id=payee_id))
        expected += amount
    diff = captured - expected
    if diff > 0:
        postings.append(Posting("suspense", credit=diff, line_code="capture_difference"))
    elif diff < 0:
        postings.append(Posting("suspense", debit=-diff, line_code="capture_difference"))
    await post_journal(
        db,
        tenant_id=payment.tenant_id,
        key=f"capture:{payment.id}{key_suffix}",
        kind="capture",
        currency=payment.currency,
        occurred_at=occurred_at,
        postings=postings,
        payment_id=payment.id,
    )


async def _refunded_by_bucket(db: AsyncSession, payment_id: str) -> dict[tuple, int]:
    rows = await db.execute(
        select(
            LedgerEntry.account,
            LedgerEntry.line_code,
            LedgerEntry.payee_type,
            LedgerEntry.payee_id,
            func.sum(LedgerEntry.debit_minor),
        )
        .where(LedgerEntry.payment_id == payment_id, LedgerEntry.kind == "refund")
        .group_by(LedgerEntry.account, LedgerEntry.line_code, LedgerEntry.payee_type, LedgerEntry.payee_id)
    )
    return {(r[0], r[1], r[2], r[3]): int(r[4] or 0) for r in rows}


async def post_refund(db: AsyncSession, payment: Payment, *, refund_id: str, amount_minor: int, occurred_at: datetime) -> list[dict]:
    """Reverse revenue and VAT proportionally to what is still unrefunded. Returns credit-note lines."""
    buckets = _buckets(payment.lines)
    already = await _refunded_by_bucket(db, payment.id)
    capacities = [max(amount - already.get(key, 0), 0) for key, amount in buckets]
    allocatable = min(amount_minor, sum(capacities))
    parts = allocate(allocatable, capacities)
    postings = [Posting("processor_clearing", credit=amount_minor)]
    for (key, _), part in zip(buckets, parts, strict=True):
        account, code, payee_type, payee_id = key
        postings.append(Posting(account, debit=part, line_code=code, payee_type=payee_type, payee_id=payee_id))
    if amount_minor > allocatable:
        postings.append(Posting("suspense", debit=amount_minor - allocatable, line_code="refund_difference"))
    await post_journal(
        db,
        tenant_id=payment.tenant_id,
        key=f"refund:{refund_id}",
        kind="refund",
        currency=payment.currency,
        occurred_at=occurred_at,
        postings=postings,
        payment_id=payment.id,
        refund_id=refund_id,
    )
    # Credit-note lines mirror the original invoice lines with the refunded net/VAT per line.
    n = len(payment.lines)
    net_parts, vat_parts = parts[:n], parts[n:]
    lines = []
    for line, net, vat in zip(payment.lines, net_parts, vat_parts, strict=True):
        if net or vat:
            lines.append({**line, "net_minor": net, "vat_minor": vat, "gross_minor": net + vat})
    return lines


async def journal_balances(db: AsyncSession, payment_id: str) -> dict[str, int]:
    rows = await db.execute(
        select(LedgerJournal.key, func.sum(LedgerEntry.debit_minor), func.sum(LedgerEntry.credit_minor))
        .join(LedgerEntry, LedgerEntry.journal_id == LedgerJournal.id)
        .where(LedgerJournal.payment_id == payment_id)
        .group_by(LedgerJournal.key)
    )
    return {r[0]: int(r[1] or 0) - int(r[2] or 0) for r in rows}


async def payment_balance(db: AsyncSession, payment_id: str) -> int:
    """Σ debit − Σ credit over every line of the payment: always 0 for a sound ledger."""
    row = (
        await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.debit_minor), 0), func.coalesce(func.sum(LedgerEntry.credit_minor), 0)).where(
                LedgerEntry.payment_id == payment_id
            )
        )
    ).one()
    return int(row[0]) - int(row[1])


def account_totals(entries: list[LedgerEntry]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for e in entries:
        out[e.account] += e.debit_minor - e.credit_minor
    return dict(out)
