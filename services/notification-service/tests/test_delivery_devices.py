"""Delivery worker (drivers, quiet hours, retries, dead-letter) and device token registration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from notification_service.channels.base import DeliveryResult, PermanentDeliveryError, TransientDeliveryError
from notification_service.channels.drivers import DisabledDriver, DriverRegistry, LogDriver
from notification_service.config import Settings
from notification_service.domain.worker import backoff
from helpers import deliveries, new_id, ok, send, set_prefs, user

TOKEN = "ExponentPushToken[abcdefghijklmnop1234]"


class FailingDriver:
    name = "failing"
    enabled = True

    def __init__(self, channel: str, error: Exception) -> None:
        self.channel = channel
        self.error = error
        self.calls = 0

    async def send(self, message) -> DeliveryResult:
        self.calls += 1
        raise self.error


@pytest.fixture
def restore_drivers(worker):
    original = {c: worker.registry.get(c) for c in ("email", "sms", "whatsapp", "push")}
    yield worker.registry
    for channel, driver in original.items():
        worker.registry.replace(channel, driver)


async def test_log_driver_records_email_without_sending(client: AsyncClient, worker) -> None:
    uid = new_id()
    await send(client, uid)
    await worker.run_once()
    rows = await deliveries(uid)
    assert rows["email"].status == "sent" and rows["email"].attempts == 1 and rows["email"].provider_ref.startswith("log:")
    sent = [m for m in worker.registry.get("email").sent if m.user_id == uid]
    assert len(sent) == 1 and sent[0].idempotency_key.endswith(f":{uid}:email")


async def test_push_needs_a_registered_device(client: AsyncClient, worker) -> None:
    without, with_device = new_id(), new_id()
    await ok(await client.post("/v1/notification-devices", json={"platform": "ios", "token": TOKEN}, headers=user(with_device)), 201)
    await send(client, without)
    await send(client, with_device)
    await worker.run_once()
    assert (await deliveries(without))["push"].skip_reason == "no_device_token"
    assert (await deliveries(with_device))["push"].status == "sent"
    [message] = [m for m in worker.registry.get("push").sent if m.user_id == with_device]
    assert message.device_tokens == (TOKEN,)


async def test_quiet_hours_defer_push_but_not_inbox(client: AsyncClient, worker) -> None:
    uid = new_id()
    now = datetime.now(UTC)
    start = (now - timedelta(hours=1)).strftime("%H:%M")
    end = (now + timedelta(hours=1)).strftime("%H:%M")
    await set_prefs(client, uid, {"timezone": "UTC", "quiet_hours": {"start": start, "end": end}})
    await ok(await client.post("/v1/notification-devices", json={"platform": "android", "token": TOKEN}, headers=user(uid)), 201)
    await send(client, uid)
    now = datetime.now(UTC)  # the deliveries are due from their creation time
    await worker.run_once(at=now)
    rows = await deliveries(uid)
    assert rows["in_app"].status == "sent"
    assert rows["push"].status == "pending" and rows["push"].attempts == 0 and rows["push"].deferred_reason == "quiet_hours"
    assert rows["push"].next_attempt_at > now
    assert rows["email"].status == "sent"  # email is not intrusive
    await worker.run_once(at=rows["push"].next_attempt_at + timedelta(seconds=1))
    assert (await deliveries(uid))["push"].status == "sent"


async def test_transient_failures_back_off_then_dead_letter(client: AsyncClient, worker, restore_drivers) -> None:
    failing = FailingDriver("email", TransientDeliveryError("smtp 451"))
    restore_drivers.replace("email", failing)
    uid = new_id()
    await send(client, uid, channels=["email"])
    at = datetime.now(UTC)
    attempts_seen = []
    for _ in range(10):
        await worker.run_once(at=at)
        row = (await deliveries(uid))["email"]
        attempts_seen.append(row.attempts)
        if row.status == "dead_letter":
            break
        assert row.next_attempt_at - at == backoff(row.attempts, base=30, cap=3600)
        # Not due yet: nothing happens before the backoff expires.
        await worker.run_once(at=at + timedelta(seconds=1))
        assert (await deliveries(uid))["email"].attempts == row.attempts
        at = row.next_attempt_at
    assert row.status == "dead_letter" and row.attempts == 5 and "smtp 451" in row.last_error
    assert failing.calls == 5 and attempts_seen == [1, 2, 3, 4, 5]


async def test_permanent_failure_dead_letters_immediately(client: AsyncClient, worker, restore_drivers) -> None:
    restore_drivers.replace("email", FailingDriver("email", PermanentDeliveryError("mailbox does not exist")))
    uid = new_id()
    await send(client, uid, channels=["email"])
    await worker.run_once()
    row = (await deliveries(uid))["email"]
    assert row.status == "dead_letter" and row.attempts == 1


async def test_disabled_driver_skips_without_attempt(client: AsyncClient, worker, restore_drivers) -> None:
    restore_drivers.replace("email", DisabledDriver("email"))
    uid = new_id()
    await send(client, uid, channels=["email"])
    await worker.run_once()
    row = (await deliveries(uid))["email"]
    assert row.status == "skipped" and row.skip_reason == "channel_disabled" and row.attempts == 0


async def test_opt_out_after_queueing_is_honoured(client: AsyncClient, worker) -> None:
    uid = new_id()
    await send(client, uid, channels=["email"])
    await set_prefs(client, uid, {"channels": {"account": {"email": False}}})
    await worker.run_once()
    row = (await deliveries(uid))["email"]
    assert row.status == "skipped" and row.skip_reason == "opted_out" and row.attempts == 0


def test_registry_refuses_real_drivers_unless_allowed() -> None:
    with pytest.raises(ValueError, match="ALLOW_REAL_DELIVERY"):
        DriverRegistry.from_settings(Settings(email_driver="smtp", smtp_host="smtp.example", smtp_password="x"))
    with pytest.raises(ValueError, match="unknown sms driver"):
        DriverRegistry.from_settings(Settings(sms_driver="twilio"))
    registry = DriverRegistry.from_settings(Settings(push_driver="disabled"))
    assert isinstance(registry.get("email"), LogDriver) and not registry.get("push").enabled


def test_backoff_is_exponential_and_capped() -> None:
    assert [backoff(n, base=30, cap=3600).total_seconds() for n in (1, 2, 3, 8)] == [30, 60, 120, 3600]


async def test_device_registration_hides_token_and_moves_on_relogin(client: AsyncClient) -> None:
    first, second = new_id(), new_id()
    device = await ok(await client.post("/v1/notification-devices", json={"platform": "ios", "token": TOKEN}, headers=user(first)), 201)
    assert TOKEN not in str(device) and device["token_suffix"] == TOKEN[-6:]
    moved = await ok(await client.post("/v1/notification-devices", json={"platform": "ios", "token": TOKEN}, headers=user(second)), 201)
    assert moved["id"] == device["id"]
    assert (await client.delete(f"/v1/notification-devices/{device['id']}", headers=user(first))).status_code == 404
    assert (await client.delete(f"/v1/notification-devices/{device['id']}", headers=user(second))).status_code == 204
    assert (await client.delete(f"/v1/notification-devices/{device['id']}", headers=user(second))).status_code == 404


async def test_device_token_validation(client: AsyncClient) -> None:
    headers = user(new_id())
    assert (await client.post("/v1/notification-devices", json={"platform": "symbian", "token": TOKEN}, headers=headers)).status_code == 422
    assert (await client.post("/v1/notification-devices", json={"platform": "ios", "token": "short"}, headers=headers)).status_code == 422
    assert (await client.post("/v1/notification-devices", json={"platform": "ios", "token": "has spaces in the token value"}, headers=headers)).status_code == 422
