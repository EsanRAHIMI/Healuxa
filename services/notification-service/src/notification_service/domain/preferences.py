"""User notification preferences: per-category channel switches, consent, quiet hours, locale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from notification_service.config import settings
from notification_service.domain.templates import CATEGORY_KIND, LOCALES, MARKETING
from notification_service.infra.models import CHANNELS, Preference

# Channels that may interrupt a person; quiet hours defer them. Inbox and email are not deferred.
INTRUSIVE_CHANNELS = frozenset({"push", "sms", "whatsapp"})

# Defaults when the user has expressed no choice. Marketing is off on every channel until the user
# gives consent (``marketing_opt_in``); after consent these defaults apply to marketing too.
TRANSACTIONAL_DEFAULTS = {"in_app": True, "email": True, "push": True, "sms": False, "whatsapp": False}
MARKETING_DEFAULTS = {"in_app": True, "email": True, "push": False, "sms": False, "whatsapp": False}


@dataclass(frozen=True)
class EffectivePreferences:
    user_id: str
    locale: str
    timezone: str
    quiet_start: time | None
    quiet_end: time | None
    marketing_opt_in: bool
    channels: dict[str, dict[str, bool]]
    updated_at: datetime | None

    def allows(self, category: str, channel: str) -> tuple[bool, str | None]:
        """(allowed, reason-if-not)."""
        if CATEGORY_KIND.get(category) == MARKETING and not self.marketing_opt_in:
            return False, "no_marketing_consent"
        if not self.channels.get(category, {}).get(channel, False):
            return False, "opted_out"
        return True, None

    def quiet_until(self, at: datetime) -> datetime | None:
        """End of the current quiet period (UTC), or None when ``at`` is outside quiet hours."""
        if self.quiet_start is None or self.quiet_end is None or self.quiet_start == self.quiet_end:
            return None
        zone = _zone(self.timezone)
        local = at.astimezone(zone)
        start = datetime.combine(local.date(), self.quiet_start, zone)
        end = datetime.combine(local.date(), self.quiet_end, zone)
        if self.quiet_start < self.quiet_end:
            inside = start <= local < end
        else:  # wraps midnight, e.g. 22:00–07:00
            if local >= start:
                end += timedelta(days=1)
                inside = True
            else:
                inside = local < end
        return end.astimezone(UTC) if inside else None


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def default_switches(category: str) -> dict[str, bool]:
    base = MARKETING_DEFAULTS if CATEGORY_KIND[category] == MARKETING else TRANSACTIONAL_DEFAULTS
    return {channel: base[channel] for channel in CHANNELS}


def effective(user_id: str, pref: Preference | None) -> EffectivePreferences:
    stored = (pref.channels if pref else None) or {}
    channels = {}
    for category in CATEGORY_KIND:
        switches = default_switches(category)
        switches.update({k: bool(v) for k, v in (stored.get(category) or {}).items() if k in switches})
        channels[category] = switches
    locale = pref.locale if pref and pref.locale in LOCALES else settings.default_locale
    return EffectivePreferences(
        user_id=user_id,
        locale=locale,
        timezone=(pref.timezone if pref and pref.timezone else settings.default_timezone),
        quiet_start=pref.quiet_start if pref else None,
        quiet_end=pref.quiet_end if pref else None,
        marketing_opt_in=bool(pref.marketing_opt_in) if pref else False,
        channels=channels,
        updated_at=pref.updated_at if pref else None,
    )


async def load(db: AsyncSession, tenant_id: str, user_id: str) -> EffectivePreferences:
    return effective(user_id, await db.get(Preference, (tenant_id, user_id)))
