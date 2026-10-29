"""Built-in drivers and the registry that selects one per channel from settings.

- ``log``: records that the message would be sent (ids and channel only) and sends nothing. Default.
- ``disabled``: the channel is off; deliveries are recorded as skipped.
- ``smtp`` (email): real delivery through an SMTP relay. Requires ``ALLOW_REAL_DELIVERY=true`` and a
  ``ContactResolver`` able to find addresses.
SMS, WhatsApp and push providers plug in by implementing ``ChannelDriver`` and registering a factory
in ``REAL_DRIVERS``; none ships yet, so selecting one fails at startup instead of silently dropping.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from collections.abc import Callable
from email.message import EmailMessage

from notification_service.channels.base import (
    ChannelDriver,
    ContactResolver,
    DeliveryResult,
    NoContactResolver,
    OutboundMessage,
    PermanentDeliveryError,
    TransientDeliveryError,
)
from notification_service.config import Settings

logger = logging.getLogger(__name__)

EXTERNAL_CHANNELS = ("email", "sms", "whatsapp", "push")


class LogDriver:
    name = "log"
    enabled = True

    def __init__(self, channel: str) -> None:
        self.channel = channel
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        if self.channel == "push" and not message.device_tokens:
            raise PermanentDeliveryError("no registered device token")
        # Never log the rendered body or addresses — ids are enough to trace a delivery.
        logger.info(
            "notification delivery (log driver) channel=%s delivery=%s user=%s",
            self.channel,
            message.delivery_id,
            message.user_id,
        )
        self.sent.append(message)
        return DeliveryResult(provider_ref=f"log:{message.delivery_id}")


class DisabledDriver:
    name = "disabled"
    enabled = False

    def __init__(self, channel: str) -> None:
        self.channel = channel

    async def send(self, message: OutboundMessage) -> DeliveryResult:  # pragma: no cover - never called
        raise PermanentDeliveryError("channel disabled")


class SmtpEmailDriver:
    name = "smtp"
    channel = "email"
    enabled = True

    def __init__(self, settings: Settings, contacts: ContactResolver) -> None:
        if not settings.smtp_host or not settings.smtp_password:
            raise ValueError("EMAIL_DRIVER=smtp requires SMTP_HOST and SMTP_PASSWORD")
        self._settings = settings
        self._contacts = contacts

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        address = await self._contacts.address(message.tenant_id, message.user_id, "email")
        if not address:
            raise PermanentDeliveryError("no email address for recipient")
        email = EmailMessage()
        email["From"] = self._settings.smtp_from
        email["To"] = address
        email["Subject"] = message.title
        email["Message-ID"] = f"<{message.idempotency_key.replace(':', '.')}@healuxa>"
        email.set_content(message.body)
        try:
            await asyncio.to_thread(self._deliver, email)
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused) as exc:
            raise PermanentDeliveryError(type(exc).__name__) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise TransientDeliveryError(type(exc).__name__) from exc
        return DeliveryResult(provider_ref=email["Message-ID"])

    def _deliver(self, email: EmailMessage) -> None:
        s = self._settings
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as client:
            if s.smtp_starttls:
                client.starttls()
            if s.smtp_username:
                client.login(s.smtp_username, s.smtp_password)
            client.send_message(email)


RealFactory = Callable[[Settings, ContactResolver], ChannelDriver]
REAL_DRIVERS: dict[tuple[str, str], RealFactory] = {
    ("email", "smtp"): SmtpEmailDriver,
}


class DriverRegistry:
    def __init__(self, drivers: dict[str, ChannelDriver]) -> None:
        self._drivers = drivers

    def get(self, channel: str) -> ChannelDriver:
        return self._drivers[channel]

    def replace(self, channel: str, driver: ChannelDriver) -> None:
        """Swap a driver at runtime (tests, or wiring a provider SDK at startup)."""
        self._drivers[channel] = driver

    @classmethod
    def from_settings(cls, settings: Settings, contacts: ContactResolver | None = None) -> DriverRegistry:
        contacts = contacts or NoContactResolver()
        drivers: dict[str, ChannelDriver] = {}
        for channel in EXTERNAL_CHANNELS:
            choice = getattr(settings, f"{channel}_driver").lower()
            if choice == "log":
                drivers[channel] = LogDriver(channel)
            elif choice == "disabled":
                drivers[channel] = DisabledDriver(channel)
            elif (channel, choice) in REAL_DRIVERS:
                if not settings.allow_real_delivery:
                    raise ValueError(
                        f"{channel.upper()}_DRIVER={choice} sends real messages; set ALLOW_REAL_DELIVERY=true to allow it"
                    )
                drivers[channel] = REAL_DRIVERS[(channel, choice)](settings, contacts)
            else:
                raise ValueError(f"unknown {channel} driver: {choice!r}")
        return cls(drivers)
