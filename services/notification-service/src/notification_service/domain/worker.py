"""Delivery worker for external channels: quiet hours, retries with exponential backoff, dead-letter.

Due deliveries are leased with ``FOR UPDATE SKIP LOCKED`` so several replicas can run safely.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notification_service.channels.base import (
    OutboundMessage,
    PermanentDeliveryError,
    TransientDeliveryError,
)
from notification_service.channels.drivers import DriverRegistry
from notification_service.config import Settings
from notification_service.domain import preferences as prefs
from notification_service.infra.models import Delivery, DeviceToken, Notification

logger = logging.getLogger(__name__)


def backoff(attempts: int, *, base: int, cap: int) -> timedelta:
    """base, 2·base, 4·base … capped (attempts counts failures so far, ≥ 1)."""
    return timedelta(seconds=min(base * 2 ** min(max(attempts - 1, 0), 20), cap))


class DeliveryWorker:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], registry: DriverRegistry, settings: Settings) -> None:
        self._sessions = session_factory
        self.registry = registry
        self._settings = settings

    async def run_once(self, *, at: datetime | None = None) -> int:
        """Process one batch of due deliveries. Returns how many were examined."""
        at = at or datetime.now(UTC)
        async with self._sessions() as db, db.begin():
            due = list(
                await db.scalars(
                    select(Delivery)
                    .where(Delivery.status == "pending", Delivery.next_attempt_at <= at)
                    .order_by(Delivery.next_attempt_at, Delivery.id)
                    .limit(self._settings.delivery_batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            for delivery in due:
                await self._process(db, delivery, at)
        return len(due)

    async def _process(self, db: AsyncSession, delivery: Delivery, at: datetime) -> None:
        delivery.updated_at = at
        notification = await db.get(Notification, delivery.notification_id)
        assert notification is not None
        preference = await prefs.load(db, delivery.tenant_id, delivery.user_id)

        # Preferences may have changed since the notification was queued: re-check before sending.
        allowed, reason = preference.allows(notification.category, delivery.channel)
        if not allowed:
            delivery.status, delivery.skip_reason, delivery.next_attempt_at = "skipped", reason, None
            return
        driver = self.registry.get(delivery.channel)
        if not driver.enabled:
            delivery.status, delivery.skip_reason, delivery.next_attempt_at = "skipped", "channel_disabled", None
            return
        if delivery.channel in prefs.INTRUSIVE_CHANNELS:
            until = preference.quiet_until(at)
            if until is not None:
                delivery.next_attempt_at, delivery.deferred_reason = until, "quiet_hours"
                return

        tokens: tuple[str, ...] = ()
        if delivery.channel == "push":
            tokens = tuple(
                await db.scalars(
                    select(DeviceToken.token).where(
                        DeviceToken.tenant_id == delivery.tenant_id, DeviceToken.user_id == delivery.user_id
                    )
                )
            )
            if not tokens:
                delivery.status, delivery.skip_reason, delivery.next_attempt_at = "skipped", "no_device_token", None
                return

        message = OutboundMessage(
            delivery_id=delivery.id,
            tenant_id=delivery.tenant_id,
            user_id=delivery.user_id,
            channel=delivery.channel,
            locale=notification.locale,
            title=notification.title,
            body=notification.body,
            idempotency_key=f"{delivery.source_key}:{delivery.user_id}:{delivery.channel}",
            device_tokens=tokens,
        )
        delivery.deferred_reason = None
        try:
            result = await driver.send(message)
        except PermanentDeliveryError as exc:
            delivery.attempts += 1
            delivery.status, delivery.next_attempt_at = "dead_letter", None
            delivery.last_error = f"permanent: {exc}"[:1000]
            logger.warning("delivery %s dead-lettered: %s", delivery.id, exc)
            return
        except (TransientDeliveryError, Exception) as exc:  # noqa: BLE001 — unknown errors are retried too
            delivery.attempts += 1
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:1000]
            if delivery.attempts >= self._settings.delivery_max_attempts:
                delivery.status, delivery.next_attempt_at = "dead_letter", None
                logger.warning("delivery %s dead-lettered after %d attempts", delivery.id, delivery.attempts)
            else:
                delivery.next_attempt_at = at + backoff(
                    delivery.attempts,
                    base=self._settings.delivery_backoff_base_seconds,
                    cap=self._settings.delivery_backoff_max_seconds,
                )
            return
        delivery.attempts += 1
        delivery.status, delivery.sent_at, delivery.next_attempt_at = "sent", at, None
        delivery.provider_ref = result.provider_ref
        delivery.last_error = None

    async def run_forever(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            processed = 0
            try:
                processed = await self.run_once()
            except Exception:  # noqa: BLE001 — DB outage must not kill the worker
                logger.exception("delivery worker iteration failed")
            if processed < self._settings.delivery_batch_size:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self._settings.delivery_poll_seconds)
