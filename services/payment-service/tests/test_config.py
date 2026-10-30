"""Live mode must be impossible unless explicitly, consistently and only in production requested."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from payment_service.config import Settings, live_mode_problems

LIVE_SK = "sk_live_" + "x" * 24
TEST_SK = "sk_test_" + "x" * 24


def build(**overrides) -> Settings:
    base = {
        "app_env": "development",
        "payment_gateway": "fake",
        "stripe_secret_key": "",
        "stripe_publishable_key": "",
        "stripe_webhook_secret": "",
    }
    return Settings(_env_file=None, **{**base, **overrides})


def test_default_development_config_is_fake_and_sandbox() -> None:
    s = build()
    assert s.payment_gateway == "fake" and not s.payments_live_mode


def test_live_key_without_live_flag_is_refused() -> None:
    with pytest.raises(ValidationError, match="PAYMENTS_LIVE_MODE"):
        build(payment_gateway="stripe", stripe_secret_key=LIVE_SK)


def test_live_flag_without_live_key_is_refused() -> None:
    with pytest.raises(ValidationError, match="sk_live_"):
        build(payment_gateway="stripe", stripe_secret_key=TEST_SK, payments_live_mode=True)


@pytest.mark.parametrize("env", ["development", "test", "staging"])
def test_live_flag_and_live_key_are_refused_outside_production(env: str) -> None:
    with pytest.raises(ValidationError, match="outside APP_ENV=production"):
        build(app_env=env, payment_gateway="stripe", stripe_secret_key=LIVE_SK, payments_live_mode=True,
              stripe_webhook_secret="whsec_real", service_auth_client_secret="s3cr3t-real-value")


def test_live_publishable_key_alone_is_refused() -> None:
    with pytest.raises(ValidationError):
        build(payment_gateway="stripe", stripe_secret_key=TEST_SK, stripe_publishable_key="pk_live_abc")


def test_live_mode_only_with_flag_key_and_production() -> None:
    assert live_mode_problems(app_env="production", payment_gateway="stripe", payments_live_mode=True,
                              stripe_secret_key=LIVE_SK, stripe_publishable_key="pk_live_abc") == []


def test_fake_gateway_is_refused_in_staging_and_production() -> None:
    for env in ("staging", "production"):
        assert any("fake" in p for p in live_mode_problems(app_env=env, payment_gateway="fake", payments_live_mode=False,
                                                           stripe_secret_key="", stripe_publishable_key=""))


def test_stripe_sandbox_requires_test_key() -> None:
    with pytest.raises(ValidationError, match="sk_test_"):
        build(payment_gateway="stripe", stripe_secret_key="")
    assert build(payment_gateway="stripe", stripe_secret_key=TEST_SK).payment_gateway == "stripe"


def test_production_secret_guard_covers_processor_secrets() -> None:
    with pytest.raises(ValidationError) as info:
        build(app_env="production", payment_gateway="stripe", stripe_secret_key="", stripe_webhook_secret="")
    message = str(info.value)
    assert "STRIPE_SECRET_KEY" in message and "STRIPE_WEBHOOK_SECRET" in message
    assert LIVE_SK not in message  # values are never echoed


def test_gateway_factory_rechecks_mode(monkeypatch) -> None:
    from payment_service.infra import gateways

    monkeypatch.setattr(gateways.settings, "stripe_secret_key", LIVE_SK)
    monkeypatch.setattr(gateways.settings, "payment_gateway", "stripe")
    with pytest.raises(RuntimeError, match="refusing payment gateway"):
        gateways.build_gateway()
