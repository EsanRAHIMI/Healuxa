"""Authorisation matrix: forged headers, missing permissions, ownership, tenant isolation, event hygiene."""

from __future__ import annotations

import json
import re

from httpx import AsyncClient

from helpers import customer, new_id, ok, outbox, paid_appointment, staff
from payment_service.api.deps import principal_headers


async def test_forged_identity_headers_are_rejected(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    forged = {"X-Healuxa-User": new_id(), "X-Healuxa-Perms": "payments:read,payments:manage,payments:refund,finance:reconcile"}
    for method, path in [
        ("GET", f"/v1/payments/{paid['payment']['id']}"),
        ("POST", f"/v1/payments/{paid['payment']['id']}/refunds"),
        ("GET", "/v1/payments/reconciliation?from=2020-01-01T00:00:00Z&to=2100-01-01T00:00:00Z"),
        ("GET", "/v1/invoices"),
    ]:
        response = await client.request(method, path, headers=forged, json={} if method == "POST" else None)
        assert response.status_code == 401, path
    wrong_secret = {**forged, "X-Healuxa-Edge-Secret": "guess"}
    assert (await client.get("/v1/invoices", headers=wrong_secret)).status_code == 401


async def test_missing_permission_is_forbidden(client: AsyncClient) -> None:
    no_perms = principal_headers(new_id(), permissions="")
    assert (await client.post("/v1/payment-quotes", json={"subject_type": "appointment", "subject_id": new_id()}, headers=no_perms)).status_code == 403
    assert (await client.get("/v1/payments", headers=no_perms)).status_code == 403
    assert (await client.get("/v1/invoices", headers=no_perms)).status_code == 403


async def test_customer_cannot_see_or_act_on_another_customers_payment(client: AsyncClient, gateway, catalog) -> None:
    owner = new_id()
    paid = await paid_appointment(client, gateway, catalog, owner)
    pid = paid["payment"]["id"]
    other = customer(new_id())
    assert (await client.get(f"/v1/payments/{pid}", headers=other)).status_code == 404
    assert (await client.post(f"/v1/payments/{pid}/refresh", headers=other)).status_code == 404
    assert (await client.get(f"/v1/payments/{pid}/refunds", headers=other)).status_code == 404
    assert (await client.get(f"/v1/payment-quotes/{paid['quote']['id']}", headers=other)).status_code == 404
    assert (await client.get(f"/v1/payments/{pid}/ledger", headers=customer(owner))).status_code == 403
    assert (await ok(await client.get("/v1/invoices", headers=other)))["data"] == []
    # A customer cannot pay someone else's quote either.
    stolen = await client.post("/v1/payments", json={"quote_id": paid["quote"]["id"]}, headers={**other, "Idempotency-Key": "steal-key-1"})
    assert stolen.status_code == 404


async def test_staff_of_another_tenant_sees_nothing(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    pid = paid["payment"]["id"]
    foreign = staff(tenant_id="healuxa-europe")
    assert (await client.get(f"/v1/payments/{pid}", headers=foreign)).status_code == 404
    assert (await client.post(f"/v1/payments/{pid}/capture", headers=foreign)).status_code == 404
    assert (await client.get(f"/v1/payments/{pid}/ledger", headers=foreign)).status_code == 404
    refund = await client.post(f"/v1/payments/{pid}/refunds", json={"reason": "goodwill"}, headers={**foreign, "Idempotency-Key": "foreign-key-1"})
    assert refund.status_code == 404
    assert (await ok(await client.get("/v1/payments", headers=foreign)))["data"] == []
    report = await ok(await client.get("/v1/payments/reconciliation", params={"from": "2020-01-01T00:00:00Z", "to": "2100-01-01T00:00:00Z"}, headers=foreign))
    assert report["totals"] == {} and report["mismatches"] == []


async def test_client_secret_only_reaches_the_paying_customer(client: AsyncClient, gateway, catalog) -> None:
    from helpers import booked_appointment, create_payment, quote_for

    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"])
    assert payment["client_secret"]
    assert (await ok(await client.get(f"/v1/payments/{payment['id']}", headers=customer(user))))["client_secret"] is None
    staff_refresh = await ok(await client.post(f"/v1/payments/{payment['id']}/refresh", headers=staff()))
    assert staff_refresh["client_secret"] is None


CARD_PATTERNS = re.compile(r"\b\d{13,19}\b|card|cvc|cvv|last4|exp_month|client_secret|_secret_|pk_|sk_|whsec", re.IGNORECASE)


async def test_outbox_events_carry_no_card_data_secrets_or_service_names(client: AsyncClient, gateway, catalog) -> None:
    paid = await paid_appointment(client, gateway, catalog, new_id())
    await ok(await client.post(f"/v1/payments/{paid['payment']['id']}/refunds", json={"amount_minor": 100, "reason": "goodwill"},
                               headers={**staff(), "Idempotency-Key": "hygiene-1"}), 201)
    events = await outbox()
    types = {e["type"] for e in events}
    assert {"payment.succeeded", "payment.invoice_issued", "payment.refunded", "commission.computed"} <= types
    for event in events:
        text = json.dumps(event["payload"])
        assert not CARD_PATTERNS.search(text), (event["type"], text)
        assert "description" not in text and "Professional fee" not in text
        assert event["producer"] == "payment-service"


async def test_publisher_refuses_forbidden_payload_keys() -> None:
    import pytest

    from payment_service.events.publisher import event_publisher
    from payment_service.infra.db import SessionLocal

    async with SessionLocal() as db:
        with pytest.raises(ValueError):
            await event_publisher.publish(db=db, event_type="payment.failed", tenant_id="t", payload={"card": {"last4": "4242"}})
        with pytest.raises(ValueError):
            await event_publisher.publish(db=db, event_type="appointment.created", tenant_id="t", payload={})
