"""Tax invoices and credit notes.

Numbers are gap-free per tenant and series: the sequence row is incremented with ``UPDATE ... RETURNING``
inside the same transaction that inserts the document, so concurrent issuers serialise on the row lock
and a rolled-back transaction gives its number back. VAT fields and the seller TRN come from settings
(placeholders until the accountant review in docs/EXTERNAL_BLOCKERS.md).
"""

from __future__ import annotations

import html
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from payment_service.config import settings
from payment_service.domain.money import totals
from payment_service.events.publisher import event_publisher, money
from payment_service.infra.models import Invoice, InvoiceSequence, Payment

SERIES = {"invoice": "INV", "credit_note": "CN"}


async def next_number(db: AsyncSession, tenant_id: str, series: str) -> int:
    await db.execute(
        insert(InvoiceSequence).values(tenant_id=tenant_id, series=series, last_value=0).on_conflict_do_nothing()
    )
    value = await db.scalar(
        update(InvoiceSequence)
        .where(InvoiceSequence.tenant_id == tenant_id, InvoiceSequence.series == series)
        .values(last_value=InvoiceSequence.last_value + 1)
        .returning(InvoiceSequence.last_value)
    )
    return int(value)


def format_number(series: str, value: int) -> str:
    return f"{settings.invoice_number_prefix}-{series}-{value:06d}"


def seller() -> dict[str, str]:
    return {"legal_name": settings.seller_legal_name, "trn": settings.seller_trn, "address": settings.seller_address}


async def issue(
    db: AsyncSession,
    *,
    payment: Payment,
    kind: str,
    lines: list[dict],
    issued_at: datetime,
    refund_id: str | None = None,
) -> Invoice:
    series = SERIES[kind]
    value = await next_number(db, payment.tenant_id, series)
    subtotal, tax, total = totals(lines)
    original_id = None
    if kind == "credit_note":
        original_id = await db.scalar(select(Invoice.id).where(Invoice.payment_id == payment.id, Invoice.kind == "invoice"))
    invoice = Invoice(
        id=str(ULID()),
        tenant_id=payment.tenant_id,
        series=series,
        sequence=value,
        number=format_number(series, value),
        kind=kind,
        payment_id=payment.id,
        refund_id=refund_id,
        original_invoice_id=original_id,
        user_id=payment.user_id,
        currency=payment.currency,
        lines=lines,
        subtotal_minor=subtotal,
        tax_minor=tax,
        total_minor=total,
        seller=seller(),
        issued_at=issued_at,
    )
    db.add(invoice)
    await db.flush()
    await event_publisher.publish(
        db=db,
        event_type="payment.invoice_issued",
        tenant_id=payment.tenant_id,
        payload={
            "invoice_id": invoice.id,
            "number": invoice.number,
            "kind": kind,
            "payment_id": payment.id,
            "refund_id": refund_id,
            "user_id": payment.user_id,
            "total": money(total, payment.currency),
            "tax": money(tax, payment.currency),
            "issued_at": issued_at.isoformat(),
        },
    )
    return invoice


def invoice_view(invoice: Invoice) -> dict:
    m = lambda v: {"amount_minor": v, "currency": invoice.currency}  # noqa: E731
    return {
        "id": invoice.id,
        "number": invoice.number,
        "kind": invoice.kind,
        "payment_id": invoice.payment_id,
        "refund_id": invoice.refund_id,
        "original_invoice_id": invoice.original_invoice_id,
        "user_id": invoice.user_id,
        "issued_at": invoice.issued_at.isoformat(),
        "currency": invoice.currency,
        "seller": invoice.seller,
        "lines": invoice.lines,
        "subtotal": m(invoice.subtotal_minor),
        "tax": m(invoice.tax_minor),
        "total": m(invoice.total_minor),
        "pdf_url": None,
        "document_url": f"/v1/invoices/{invoice.id}/document",
    }


def _fmt(minor: int, currency: str) -> str:
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    return f"{sign}{currency} {minor // 100:,}.{minor % 100:02d}"


def render_html(invoice: Invoice) -> str:
    e = html.escape
    title = "Tax Invoice" if invoice.kind == "invoice" else "Tax Credit Note"
    rows = "".join(
        "<tr>"
        f"<td>{e(str(line['description']))}</td>"
        f"<td class='n'>{_fmt(int(line['net_minor']), invoice.currency)}</td>"
        f"<td class='n'>{int(line['vat_rate_bps']) / 100:.2f}%</td>"
        f"<td class='n'>{_fmt(int(line['vat_minor']), invoice.currency)}</td>"
        f"<td class='n'>{_fmt(int(line['gross_minor']), invoice.currency)}</td>"
        "</tr>"
        for line in invoice.lines
    )
    reference = (
        f"<p>Credit note against invoice reference: {e(invoice.original_invoice_id or '-')}</p>" if invoice.kind == "credit_note" else ""
    )
    s = invoice.seller
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{e(title)} {e(invoice.number)}</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;color:#111}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:.4rem;text-align:left}}.n{{text-align:right}}small{{color:#555}}</style></head>
<body>
<h1>{e(title)}</h1>
<p><strong>{e(s.get('legal_name', ''))}</strong><br>{e(s.get('address', ''))}<br>TRN: {e(s.get('trn', ''))}</p>
<p>Number: <strong>{e(invoice.number)}</strong><br>Date of issue: {e(invoice.issued_at.date().isoformat())}<br>
Customer reference: {e(invoice.user_id)}<br>Payment reference: {e(invoice.payment_id)}</p>
{reference}
<table><thead><tr><th>Description</th><th class="n">Net</th><th class="n">VAT rate</th><th class="n">VAT</th><th class="n">Total</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="n">Subtotal (excl. VAT): {_fmt(invoice.subtotal_minor, invoice.currency)}<br>
VAT: {_fmt(invoice.tax_minor, invoice.currency)}<br>
<strong>Total: {_fmt(invoice.total_minor, invoice.currency)}</strong></p>
<p><small>Amounts in {e(invoice.currency)}. Tax configuration pending accountant review.</small></p>
</body></html>
"""
