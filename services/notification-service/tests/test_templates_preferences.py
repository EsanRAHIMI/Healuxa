"""Template catalog, preference defaults/consent, quiet hours, preference API access."""

from __future__ import annotations

from datetime import UTC, datetime, time

import pytest
from httpx import AsyncClient

from notification_service.api.deps import principal_headers
from notification_service.domain.preferences import EffectivePreferences, effective
from notification_service.domain.templates import CATALOG, LOCALES, TemplateError, get_template, render
from helpers import OTHER_TENANT, new_id, ok, set_prefs, user


def test_every_template_has_all_locales_and_known_category() -> None:
    for template in CATALOG.values():
        assert set(template.texts) == set(LOCALES), template.key
        assert template.kind in ("transactional", "marketing")


def test_render_localizes_status_labels() -> None:
    template = get_template("concierge.case_status_changed")
    assert render(template, "en", {"status": "awaiting_customer"})[1] == "Your concierge request is now: Waiting for your reply."
    assert "بانتظار ردك" in render(template, "ar", {"status": "awaiting_customer"})[1]
    assert "در انتظار پاسخ شما" in render(template, "fa", {"status": "awaiting_customer"})[1]
    assert render(template, "de", {"status": "completed"})[0] == "Concierge request update"  # falls back to en


def test_render_rejects_unknown_missing_and_invalid_params() -> None:
    template = get_template("concierge.case_status_changed")
    with pytest.raises(TemplateError):
        render(template, "en", {"status": "completed", "diagnosis": "x"})
    with pytest.raises(TemplateError):
        render(template, "en", {})
    with pytest.raises(TemplateError):
        render(template, "en", {"status": "bogus"})
    with pytest.raises(TemplateError):
        get_template("nope")


def test_legal_and_clinical_wording_is_flagged_for_review() -> None:
    assert get_template("catalog.provider_status_changed").needs_professional_review
    assert get_template("appointment.no_show").needs_professional_review
    assert not get_template("concierge.message_posted").needs_professional_review


def test_defaults_marketing_off_transactional_on() -> None:
    prefs = effective(new_id(), None)
    assert prefs.marketing_opt_in is False
    assert prefs.allows("marketing", "email") == (False, "no_marketing_consent")
    assert prefs.allows("concierge", "in_app") == (True, None)
    assert prefs.allows("concierge", "sms") == (False, "opted_out")


def _quiet(start: str, end: str, tz: str = "Asia/Dubai") -> EffectivePreferences:
    return EffectivePreferences("u", "en", tz, time.fromisoformat(start), time.fromisoformat(end), False, {}, None)


def test_quiet_hours_wrap_midnight_in_user_timezone() -> None:
    prefs = _quiet("22:00", "07:00")  # Dubai = UTC+4
    late = datetime(2026, 10, 28, 19, 30, tzinfo=UTC)  # 23:30 Dubai
    assert prefs.quiet_until(late) == datetime(2026, 10, 29, 3, 0, tzinfo=UTC)
    early = datetime(2026, 10, 28, 1, 0, tzinfo=UTC)  # 05:00 Dubai
    assert prefs.quiet_until(early) == datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
    assert prefs.quiet_until(datetime(2026, 10, 28, 10, 0, tzinfo=UTC)) is None  # 14:00 Dubai
    assert _quiet("13:00", "15:00", "UTC").quiet_until(datetime(2026, 10, 28, 14, 0, tzinfo=UTC)) == datetime(2026, 10, 28, 15, 0, tzinfo=UTC)


async def test_get_preferences_returns_defaults(client: AsyncClient) -> None:
    uid = new_id()
    prefs = await ok(await client.get(f"/v1/notifications/preferences/{uid}", headers=user(uid)))
    assert prefs["marketing_opt_in"] is False and prefs["locale"] == "en" and prefs["quiet_hours"] is None
    assert prefs["channels"]["marketing"]["email"] is True  # applies only after consent
    assert prefs["channels"]["concierge"] == {"in_app": True, "email": True, "sms": False, "whatsapp": False, "push": True}


async def test_update_preferences_merges_and_clears(client: AsyncClient) -> None:
    uid = new_id()
    await set_prefs(client, uid, {"locale": "fa", "quiet_hours": {"start": "22:00", "end": "07:00"}, "channels": {"concierge": {"email": False}}})
    prefs = await set_prefs(client, uid, {"channels": {"concierge": {"sms": True}}, "marketing_opt_in": True})
    assert prefs["locale"] == "fa" and prefs["marketing_opt_in"] is True
    assert prefs["channels"]["concierge"]["email"] is False and prefs["channels"]["concierge"]["sms"] is True
    assert prefs["quiet_hours"] == {"start": "22:00", "end": "07:00"}
    cleared = await set_prefs(client, uid, {"quiet_hours": None})
    assert cleared["quiet_hours"] is None and cleared["locale"] == "fa"


async def test_invalid_preferences_rejected(client: AsyncClient) -> None:
    uid = new_id()
    for body in ({"timezone": "Mars/Base"}, {"locale": "de"}, {"quiet_hours": {"start": "25:00", "end": "07:00"}}, {"channels": {"spam": {"email": True}}}):
        assert (await client.put(f"/v1/notifications/preferences/{uid}", json=body, headers=user(uid))).status_code == 422, body


async def test_preferences_are_private(client: AsyncClient) -> None:
    owner, other = new_id(), new_id()
    assert (await client.get(f"/v1/notifications/preferences/{owner}", headers=user(other))).status_code == 404
    assert (await client.put(f"/v1/notifications/preferences/{owner}", json={"locale": "ar"}, headers=user(other))).status_code == 404
    # Same user id in another tenant has separate preferences.
    await set_prefs(client, owner, {"locale": "ar"})
    foreign = await ok(await client.get(f"/v1/notifications/preferences/{owner}", headers=user(owner, tenant_id=OTHER_TENANT)))
    assert foreign["locale"] == "en"


async def test_forged_headers_and_missing_permissions(client: AsyncClient) -> None:
    uid = new_id()
    forged = {"X-Healuxa-User": uid, "X-Healuxa-Perms": "notifications:read,service"}
    assert (await client.get("/v1/notifications", headers=forged)).status_code == 401
    assert (await client.post("/v1/notifications/send", json={"user_id": uid, "template": "account.notice"}, headers=forged)).status_code == 401
    no_perms = principal_headers(uid, permissions="")
    assert (await client.get(f"/v1/notifications/preferences/{uid}", headers=no_perms)).status_code == 403
