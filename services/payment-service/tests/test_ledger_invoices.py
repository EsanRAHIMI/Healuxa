"""Double-entry ledger, gap-free invoice numbering, invoice documents."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from helpers import customer, new_id, ok, paid_appointment, staff
from payment_service.domain.invoices import next_number
from payment_service.domain.ledger import Posting, UnbalancedJournal, payment_balance, post_journal
from payment_service.infra.db import SessionLocal
from payment_service.infra.models import Invoice

TENANT = "healuxa-dubai"


async def test_capture_ledger_separates_revenue_tax_and_balances(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    ledger = await ok(await client.get(f"/v1/payments/{paid['payment']['id']}/ledger", headers=staff()))
    assert ledger["balanced"]
    by_account: dict[str, int] = {}
    for line in ledger["data"]:
        by_account[line["account"]] = by_account.get(line["account"], 0) + line["credit_minor"] - line["debit_minor"]
    assert by_account == {
        "processor_clearing": -77_175,
        "provider_revenue": 50_000,
        "facility_revenue": 20_000,
        "healuxa_revenue": 3_500,
        "vat_payable": 3_675,
    }
    provider_line = next(line for line in ledger["data"] if line["account"] == "provider_revenue")
    assert provider_line["payee_id"] == paid["offering"].provider_id


async def test_ledger_balances_to_zero_after_refunds_and_fees(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    pid = paid["payment"]["id"]
    for amount in (12_345, 1, 40_000):
        await ok(await client.post(f"/v1/payments/{pid}/refunds", json={"amount_minor": amount, "reason": "goodwill"},
                                   headers={**staff(), "Idempotency-Key": f"r-{new_id()}"}), 201)
    await ok(await client.post("/v1/payments/settlements/import", json={"from": "2020-01-01T00:00:00Z", "to": "2100-01-01T00:00:00Z"}, headers=staff()))
    async with SessionLocal() as db:
        assert await payment_balance(db, pid) == 0
    ledger = await ok(await client.get(f"/v1/payments/{pid}/ledger", headers=staff()))
    kinds = {line["kind"] for line in ledger["data"]}
    assert {"capture", "refund", "processor_fee"} <= kinds and ledger["balanced"]
    refunded_revenue = sum(line["debit_minor"] for line in ledger["data"] if line["kind"] == "refund" and line["account"] != "processor_clearing")
    assert refunded_revenue == 52_346


async def test_unbalanced_journal_is_refused() -> None:
    async with SessionLocal() as db:
        with pytest.raises(UnbalancedJournal):
            await post_journal(db, tenant_id=TENANT, key=f"x:{new_id()}", kind="capture", currency="AED", occurred_at=datetime.now(UTC),
                               postings=[Posting("processor_clearing", debit=100), Posting("healuxa_revenue", credit=99)])


async def test_concurrent_invoice_numbers_are_gap_free() -> None:
    async def take() -> int:
        async with SessionLocal() as db, db.begin():
            value = await next_number(db, TENANT, "INV")
            await asyncio.sleep(0.01)  # hold the row lock while others queue
            return value

    values = await asyncio.gather(*[take() for _ in range(25)])
    assert sorted(values) == list(range(1, 26))


async def test_rolled_back_number_is_reused() -> None:
    async with SessionLocal() as db, db.begin():
        assert await next_number(db, TENANT, "CN") == 1
    async with SessionLocal() as db:
        await db.begin()
        assert await next_number(db, TENANT, "CN") == 2
        await db.rollback()  # e.g. the invoice insert failed
    async with SessionLocal() as db, db.begin():
        assert await next_number(db, TENANT, "CN") == 2
    async with SessionLocal() as db, db.begin():
        assert await next_number(db, "healuxa-europe", "CN") == 1  # per tenant


async def test_invoice_and_credit_note_documents(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    paid = await paid_appointment(client, gateway, catalog, user)
    pid = paid["payment"]["id"]
    await ok(await client.post(f"/v1/payments/{pid}/refunds", json={"amount_minor": 10_000, "reason": "goodwill"},
                               headers={**staff(), "Idempotency-Key": "credit-note-1"}), 201)
    invoices = (await ok(await client.get("/v1/invoices", headers=customer(user))))["data"]
    kinds = sorted((i["kind"], i["number"]) for i in invoices)
    assert kinds == [("credit_note", "HLX-CN-000001"), ("invoice", "HLX-INV-000001")]
    invoice = next(i for i in invoices if i["kind"] == "invoice")
    credit = next(i for i in invoices if i["kind"] == "credit_note")
    assert invoice["total"]["amount_minor"] == 77_175 and invoice["tax"]["amount_minor"] == 3_675
    assert invoice["seller"]["trn"] == "TRN-PENDING"
    assert credit["total"]["amount_minor"] == 10_000 and credit["original_invoice_id"] == invoice["id"]
    assert credit["subtotal"]["amount_minor"] + credit["tax"]["amount_minor"] == 10_000
    doc = await client.get(f"/v1/invoices/{invoice['id']}/document", headers=customer(user))
    assert doc.status_code == 200 and "Tax Invoice" in doc.text and "HLX-INV-000001" in doc.text and "AED 771.75" in doc.text
    assert doc.headers["cache-control"] == "private, no-store"
    assert (await client.get(f"/v1/invoices/{invoice['id']}", headers=customer(new_id()))).status_code == 404
    assert (await client.get(f"/v1/invoices/{invoice['id']}/document", headers=customer(new_id()))).status_code == 404


async def test_invoice_html_escapes_content(client: AsyncClient, gateway, catalog) -> None:
    from payment_service.domain.invoices import render_html

    paid = await paid_appointment(client, gateway, catalog, new_id())
    async with SessionLocal() as db:
        invoice = await db.scalar(select(Invoice).where(Invoice.payment_id == paid["payment"]["id"]))
    invoice.lines = [{**invoice.lines[0], "description": "<script>alert(1)</script>"}]
    assert "<script>" not in render_html(invoice)
