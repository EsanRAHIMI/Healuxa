from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Channel = Literal["in_app", "email", "sms", "whatsapp", "push"]
Category = Literal["concierge", "appointments", "provider_account", "account", "marketing"]
Locale = Literal["en", "ar", "fa"]
EntityType = Literal["provider", "facility", "concierge_case", "appointment", "user"]
HHMM = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageMeta(Strict):
    next_cursor: str | None = None
    limit: int
    has_more: bool


class NotificationOut(Strict):
    id: str
    category: Category
    template: str
    locale: Locale
    title: str
    body: str
    entity_type: str | None = None
    entity_id: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class NotificationPage(BaseModel):
    data: list[NotificationOut]
    page: PageMeta


class UnreadCount(Strict):
    unread: int


class MarkedCount(Strict):
    marked: int


class SendRequest(Strict):
    user_id: str = Field(min_length=16, max_length=36)
    tenant_id: str | None = Field(default=None, max_length=64)
    channel: Literal["push", "web_push", "email", "sms", "in_app", "whatsapp"] | None = None
    channels: list[Channel] | None = None
    template: str = Field(max_length=80)
    data: dict[str, Any] = Field(default_factory=dict)
    entity_type: EntityType | None = None
    entity_id: str | None = Field(default=None, max_length=36)

    @field_validator("data")
    @classmethod
    def _only_small_scalars(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key, item in value.items():
            if not isinstance(item, (str, int)) or isinstance(item, bool) or (isinstance(item, str) and len(item) > 200):
                raise ValueError(f"data.{key} must be a short string or integer")
        return value

    def requested_channels(self) -> tuple[str, ...] | None:
        chosen = list(self.channels or [])
        if self.channel:
            chosen.append("push" if self.channel == "web_push" else self.channel)
        return tuple(dict.fromkeys(chosen)) or None


class DeliveryStatus(Strict):
    channel: Channel
    status: Literal["pending", "sent", "skipped", "dead_letter"]
    skip_reason: str | None = None


class SendResult(Strict):
    notification_id: str
    deliveries: list[DeliveryStatus]


class QuietHours(Strict):
    start: str = Field(pattern=HHMM)
    end: str = Field(pattern=HHMM)


class ChannelSwitches(Strict):
    in_app: bool | None = None
    email: bool | None = None
    sms: bool | None = None
    whatsapp: bool | None = None
    push: bool | None = None


class PreferencesOut(Strict):
    user_id: str
    locale: Locale
    timezone: str
    quiet_hours: QuietHours | None = None
    marketing_opt_in: bool
    channels: dict[str, dict[str, bool]]
    updated_at: datetime | None = None


class PreferencesUpdate(Strict):
    locale: Locale | None = None
    timezone: str | None = Field(default=None, max_length=64)
    quiet_hours: QuietHours | None = None
    marketing_opt_in: bool | None = None
    channels: dict[Category, ChannelSwitches] | None = None


class DeviceTokenCreate(Strict):
    platform: Literal["ios", "android", "web"]
    token: str = Field(min_length=16, max_length=512)

    @field_validator("token")
    @classmethod
    def _printable(cls, value: str) -> str:
        if not re.fullmatch(r"[\x21-\x7e]+", value):
            raise ValueError("token must be printable ASCII without spaces")
        return value


class DeviceTokenOut(Strict):
    id: str
    platform: Literal["ios", "android", "web"]
    token_suffix: str
    created_at: datetime


class RecipientLinkIn(Strict):
    tenant_id: str | None = Field(default=None, max_length=64)
    entity_type: EntityType
    entity_id: str = Field(min_length=1, max_length=36)
    user_id: str = Field(min_length=1, max_length=36)
    role: str | None = Field(default=None, max_length=32)
