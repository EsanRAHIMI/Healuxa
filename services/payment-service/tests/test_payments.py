"""Quotes, idempotent payment creation, manual capture, void, and booking-event integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update

from helpers import (
    appointment_event,
    booked_appointment,
    create_payment,
    customer,
    last_pi,
    new_id,
    ok,
    outbox,
    paid_appointment,
    pi_event,
    quote_for,
    staff,
)
from payment_service.infra.db import SessionLocal
from payment_service.infra.gateways.base import GatewayError
from payment_service.infra.models import Quote


async def test_appointment_quote_is_priced_server_side(client: AsyncClient, catalog) -> None:
    user = new_id()
    appointment, offering = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    assert [line["code"] for line in quote["lines"]] == ["professional_fee", "facility_fee", "platform_fee"]
    assert quote["subtotal"] == {"amount_minor": 73_500, "currency": "AED"}
    assert quote["tax"]["amount_minor"] == 3_675 and quote["total"]["amount_minor"] == 77_175
    assert quote["provider_id"] == offering.provider_id and quote["tax_status"] == "pending_accountant_review"
    assert quote["lines"][0]["payee_id"] == offering.provider_id


async def test_client_supplied_amounts_are_rejected(client: AsyncClient, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    with_amount = await client.post(
        "/v1/payment-quotes",
        json={"subject_type": "appointment", "subject_id": appointment["appointment_id"], "amount": {"amount_minor": 1, "currency": "AED"}},
        headers=customer(user),
    )
    assert with_amount.status_code == 422
    with_lines = await client.post(
        "/v1/payment-quotes",
        json={"subject_type": "appointment", "subject_id": appointment["appointment_id"],
              "lines": [{"code": "professional_fee", "description": "cheap", "category": "professional_service", "net_minor": 1}]},
        headers=customer(user),
    )
    assert with_lines.status_code == 422
    quote = await quote_for(client, user, appointment)
    sneaky = await client.post("/v1/payments", json={"quote_id": quote["id"], "amount": 1}, headers={**customer(user), "Idempotency-Key": "k-12345678"})
    assert sneaky.status_code == 422


async def test_quote_for_someone_elses_or_unknown_appointment_is_404(client: AsyncClient, catalog) -> None:
    owner = new_id()
    appointment, _ = await booked_appointment(catalog, owner)
    stranger = await client.post("/v1/payment-quotes", json={"subject_type": "appointment", "subject_id": appointment["appointment_id"]}, headers=customer(new_id()))
    assert stranger.status_code == 404
    unknown = await client.post("/v1/payment-quotes", json={"subject_type": "appointment", "subject_id": new_id()}, headers=customer(owner))
    assert unknown.status_code == 404


async def test_on_request_offering_needs_staff_quote(client: AsyncClient, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user, price_type="on_request")
    response = await client.post("/v1/payment-quotes", json={"subject_type": "appointment", "subject_id": appointment["appointment_id"]}, headers=customer(user))
    assert response.status_code == 422


async def test_concierge_quote_is_staff_prepared(client: AsyncClient) -> None:
    user = new_id()
    body = {
        "subject_type": "concierge_case",
        "subject_id": new_id(),
        "user_id": user,
        "lines": [{"code": "concierge_fee", "description": "Concierge coordination", "category": "concierge_service", "net_minor": 100_000}],
    }
    assert (await client.post("/v1/payment-quotes", json=body, headers=customer(user))).status_code == 403
    quote = await ok(await client.post("/v1/payment-quotes", json=body, headers=staff()), 201)
    assert quote["user_id"] == user and quote["total"]["amount_minor"] == 105_000
    # The customer pays it; staff cannot pay on their behalf.
    payment = await create_payment(client, user, quote["id"])
    assert payment["capture_method"] == "automatic" and payment["amount"]["amount_minor"] == 105_000


async def test_create_payment_is_idempotent(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    first = await create_payment(client, user, quote["id"], key="idem-key-0001")
    again = await create_payment(client, user, quote["id"], key="idem-key-0001")
    assert first["id"] == again["id"] and first["client_secret"] and again["client_secret"] == first["client_secret"]
    assert len(gateway.payment_intents) == 1
    assert first["status"] == "pending" and first["amount"]["amount_minor"] == quote["total"]["amount_minor"]
    assert first["capture_method"] == "manual"  # confirm-then-charge default for bookings
    different = await client.post("/v1/payments", json={"quote_id": quote["id"], "capture_method": "automatic"},
                                  headers={**customer(user), "Idempotency-Key": "idem-key-0001"})
    assert different.status_code == 409 and different.json()["code"] == "idempotency_conflict"
    reuse = await client.post("/v1/payments", json={"quote_id": quote["id"]}, headers={**customer(user), "Idempotency-Key": "idem-key-0002"})
    assert reuse.status_code == 409


async def test_idempotency_key_is_required(client: AsyncClient, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    response = await client.post("/v1/payments", json={"quote_id": quote["id"]}, headers=customer(user))
    assert response.status_code == 400


async def test_expired_quote_cannot_be_paid(client: AsyncClient, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    async with SessionLocal() as db:
        await db.execute(update(Quote).where(Quote.id == quote["id"]).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        await db.commit()
    response = await client.post("/v1/payments", json={"quote_id": quote["id"]}, headers={**customer(user), "Idempotency-Key": "k-expired-1"})
    assert response.status_code == 422


async def test_processor_outage_then_retry_with_same_key_opens_one_intent(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    gateway.fail_next = GatewayError("down")
    failed = await client.post("/v1/payments", json={"quote_id": quote["id"]}, headers={**customer(user), "Idempotency-Key": "retry-key-1"})
    assert failed.status_code == 503
    retried = await create_payment(client, user, quote["id"], key="retry-key-1")
    assert retried["client_secret"] and len(gateway.payment_intents) == 1


async def test_client_side_success_is_not_proof_of_payment(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"], capture_method="automatic")
    gateway.confirm(last_pi(gateway), "succeeded")  # the customer's screen says "paid"…
    still = await ok(await client.get(f"/v1/payments/{payment['id']}", headers=customer(user)))
    assert still["status"] == "pending" and await outbox("payment.succeeded") == []
    # …only server-side retrieval (or a verified webhook) moves it.
    refreshed = await ok(await client.post(f"/v1/payments/{payment['id']}/refresh", headers=customer(user)))
    assert refreshed["status"] == "succeeded" and refreshed["invoice_id"]


async def test_manual_capture_flow(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"])
    pi = last_pi(gateway)
    early = await client.post(f"/v1/payments/{payment['id']}/capture", headers=staff())
    assert early.status_code == 409  # not authorised yet
    await pi_event(client, gateway, pi, "authorized")
    held = await ok(await client.get(f"/v1/payments/{payment['id']}", headers=customer(user)))
    assert held["status"] == "authorized" and held["amount_authorized_minor"] == 77_175 and held["amount_captured_minor"] == 0
    assert [e["payload"]["payment_id"] for e in await outbox("payment.authorized")] == [payment["id"]]
    assert (await client.post(f"/v1/payments/{payment['id']}/capture", headers=customer(user))).status_code == 403
    captured = await ok(await client.post(f"/v1/payments/{payment['id']}/capture", headers=staff()))
    assert captured["status"] == "succeeded" and captured["amount_captured_minor"] == 77_175
    again = await ok(await client.post(f"/v1/payments/{payment['id']}/capture", headers=staff()))
    assert again["status"] == "succeeded" and len(await outbox("payment.succeeded")) == 1


async def test_void_releases_authorisation_and_captured_cannot_be_voided(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"])
    await pi_event(client, gateway, last_pi(gateway), "authorized")
    voided = await ok(await client.post(f"/v1/payments/{payment['id']}/cancel", json={"reason": "requested_by_customer"}, headers=staff()))
    assert voided["status"] == "canceled"
    assert (await outbox("payment.canceled"))[0]["payload"]["reason"] == "requested_by_customer"
    paid = await paid_appointment(client, gateway, catalog, new_id())
    assert (await client.post(f"/v1/payments/{paid['payment']['id']}/cancel", headers=staff())).status_code == 409


async def test_appointment_accepted_captures_held_payment(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"])
    await pi_event(client, gateway, last_pi(gateway), "authorized")
    env = await appointment_event("appointment.accepted", appointment)
    captured = await ok(await client.get(f"/v1/payments/{payment['id']}", headers=customer(user)))
    assert captured["status"] == "succeeded"
    # Redelivery of the same event is a no-op.
    from payment_service.domain.consumers import handle_appointment_event
    from payment_service.infra.db import SessionLocal as S

    await handle_appointment_event(S, env)
    assert len([c for c in gateway.calls if c[0] == "capture_payment"]) == 1


async def test_appointment_declined_voids_or_refunds(client: AsyncClient, gateway, catalog) -> None:
    user = new_id()
    appointment, _ = await booked_appointment(catalog, user)
    quote = await quote_for(client, user, appointment)
    payment = await create_payment(client, user, quote["id"])
    await pi_event(client, gateway, last_pi(gateway), "authorized")
    await appointment_event("appointment.declined", {**appointment, "reason": "no_capacity"})
    assert (await ok(await client.get(f"/v1/payments/{payment['id']}", headers=customer(user))))["status"] == "canceled"

    paid = await paid_appointment(client, gateway, catalog, user)
    await appointment_event("appointment.declined", {**paid["appointment"], "reason": "no_capacity"})
    refunded = await ok(await client.get(f"/v1/payments/{paid['payment']['id']}", headers=customer(user)))
    assert refunded["status"] == "refunded" and refunded["amount_refunded_minor"] == refunded["amount_captured_minor"]


async def test_payment_config_discloses_fees_and_never_secret_key(client: AsyncClient) -> None:
    config = await ok(await client.get("/v1/payments/config"))
    assert config["platform_fee"]["rate_bps"] == 500 and "5%" in config["platform_fee"]["label"]
    assert config["tax"]["status"] == "pending_accountant_review" and config["live_mode"] is False
    assert config["publishable_key"].startswith("pk_test_")
    assert "sk_" not in str(config) and "whsec" not in str(config)


async def test_list_payments_shows_only_own(client: AsyncClient, gateway, catalog) -> None:
    alice, bob = new_id(), new_id()
    a = await paid_appointment(client, gateway, catalog, alice)
    await paid_appointment(client, gateway, catalog, bob)
    mine = await ok(await client.get("/v1/payments", headers=customer(alice)))
    assert [p["id"] for p in mine["data"]] == [a["payment"]["id"]]
    assert all(p["client_secret"] is None for p in mine["data"])
    everyone = await ok(await client.get("/v1/payments", headers=staff()))
    assert len(everyone["data"]) == 2
