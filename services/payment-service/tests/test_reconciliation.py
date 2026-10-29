"""Settlement import, reconciliation mismatch detection, payee settlement reports."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import update

from helpers import customer, new_id, ok, paid_appointment, staff
from payment_service.infra.db import SessionLocal
from payment_service.infra.models import BalanceTransaction

WINDOW = {"from": "2020-01-01T00:00:00Z", "to": "2100-01-01T00:00:00Z"}


async def _import(client: AsyncClient) -> dict:
    return await ok(await client.post("/v1/payments/settlements/import", json=WINDOW, headers=staff()))


async def _report(client: AsyncClient) -> dict:
    return await ok(await client.get("/v1/payments/reconciliation", params=WINDOW, headers=staff()))


async def test_clean_period_reconciles(client: AsyncClient, gateway, catalog) -> None:
    a = await paid_appointment(client, gateway, catalog, new_id())
    await paid_appointment(client, gateway, catalog, new_id())
    await ok(await client.post(f"/v1/payments/{a['payment']['id']}/refunds", json={"amount_minor": 5000, "reason": "goodwill"},
                               headers={**staff(), "Idempotency-Key": "rec-refund-1"}), 201)
    gateway.payout()
    first = await _import(client)
    assert first["imported"] == 4 and first["payouts"] == 1  # 2 charges (fees inline), 1 refund, 1 payout
    again = await _import(client)
    assert again["imported"] == 0 and again["skipped"] == first["imported"]
    report = await _report(client)
    assert report["mismatches"] == [], report["mismatches"]
    assert report["totals"]["captured_minor"] == 2 * 77_175 and report["totals"]["refunded_minor"] == 5000
    assert report["matched"] == 4


async def test_mismatches_are_flagged(client: AsyncClient, gateway, catalog) -> None:
    a = await paid_appointment(client, gateway, catalog, new_id())
    b = await paid_appointment(client, gateway, catalog, new_id())
    # b's charge never shows up at the processor; a's amount differs; an unknown charge appears.
    gateway.balance_transactions = [t for t in gateway.balance_transactions if t["source"] != gateway.stripe_object("payment_intent", b["pi_id"])["latest_charge"]]
    gateway._balance_txn("charge", "ch_unknown", 1234, fee=10)
    payout = gateway.payout(amount_override=1)
    await _import(client)
    a_charge = gateway.stripe_object("payment_intent", a["pi_id"])["latest_charge"]
    async with SessionLocal() as db:
        await db.execute(update(BalanceTransaction).where(BalanceTransaction.source_id == a_charge).values(amount_minor=77_000))
        await db.commit()
    kinds = {(m["kind"], m["payment_id"] or m["processor_ref"]) for m in (await _report(client))["mismatches"]}
    assert ("amount_mismatch", a["payment"]["id"]) in kinds
    assert ("missing_processor_transaction", b["payment"]["id"]) in kinds
    assert any(k == "unknown_processor_transaction" for k, _ in kinds)
    assert ("payout_mismatch", payout["source"]) in kinds


async def test_reconciliation_requires_finance_permission(client: AsyncClient) -> None:
    manager = staff(permissions="payments:read,payments:manage")
    assert (await client.get("/v1/payments/reconciliation", params=WINDOW, headers=manager)).status_code == 403
    assert (await client.post("/v1/payments/settlements/import", json=WINDOW, headers=customer(new_id()))).status_code == 403


async def test_settlement_report_for_payee_members_only(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    provider_id = paid["offering"].provider_id
    facility_id = paid["offering"].facility_id
    await ok(await client.post(f"/v1/payments/{paid['payment']['id']}/refunds", json={"amount_minor": 10_500, "reason": "goodwill"},
                               headers={**staff(), "Idempotency-Key": "settle-refund-1"}), 201)
    provider_user, facility_user, stranger = new_id(), new_id(), new_id()
    for payee_type, payee_id, user in [("provider", provider_id, provider_user), ("facility", facility_id, facility_user)]:
        await ok(await client.post("/v1/payments/payees/members", json={"payee_type": payee_type, "payee_id": payee_id, "user_id": user}, headers=staff()), 201)
    params = {"payee_type": "provider", "payee_id": provider_id}
    report = await ok(await client.get("/v1/payments/settlements/report", params=params, headers=customer(provider_user)))
    assert report["gross_minor"] == 50_000 and 0 < report["refunded_minor"] < 10_500 and report["net_minor"] == 50_000 - report["refunded_minor"]
    assert "user_id" not in str(report)  # no customer identifiers for providers
    assert (await client.get("/v1/payments/settlements/report", params=params, headers=customer(facility_user))).status_code == 404
    assert (await client.get("/v1/payments/settlements/report", params=params, headers=customer(stranger))).status_code == 404
    facility = await ok(await client.get("/v1/payments/settlements/report", params={"payee_type": "facility", "payee_id": facility_id}, headers=customer(facility_user)))
    assert facility["gross_minor"] == 20_000
    finance = await ok(await client.get("/v1/payments/settlements/report", params=params, headers=staff()))
    assert finance["net_minor"] == report["net_minor"]
    assert (await client.post("/v1/payments/payees/members", json={"payee_type": "provider", "payee_id": provider_id, "user_id": stranger},
                              headers=customer(provider_user))).status_code == 403
