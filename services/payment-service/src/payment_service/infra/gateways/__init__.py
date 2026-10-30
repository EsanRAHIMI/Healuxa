"""Gateway selection. The configuration guard in config.py has already refused live/unsafe modes."""

from __future__ import annotations

from payment_service.config import live_mode_problems, settings
from payment_service.infra.gateways.base import PaymentGateway, WebhookTranslator
from payment_service.infra.gateways.stripe import StripeGateway, StripeWebhookTranslator

_gateway: PaymentGateway | None = None


def build_gateway() -> PaymentGateway:
    # Defence in depth: re-check at construction time, so a gateway can never be built in a mode the
    # settings validator would refuse (e.g. settings mutated at runtime).
    problems = live_mode_problems(
        app_env=settings.app_env,
        payment_gateway=settings.payment_gateway,
        payments_live_mode=settings.payments_live_mode,
        stripe_secret_key=settings.stripe_secret_key,
        stripe_publishable_key=settings.stripe_publishable_key,
    )
    if problems:
        raise RuntimeError("refusing payment gateway: " + "; ".join(problems))
    if settings.payment_gateway == "stripe":
        return StripeGateway(
            secret_key=settings.stripe_secret_key,
            api_base=settings.stripe_api_base,
            api_version=settings.stripe_api_version,
            timeout=settings.stripe_timeout_seconds,
        )
    from payment_service.infra.gateways.fake import FakeGateway

    return FakeGateway()


def get_gateway() -> PaymentGateway:
    global _gateway
    if _gateway is None:
        _gateway = build_gateway()
    return _gateway


def set_gateway(gateway: PaymentGateway | None) -> None:
    global _gateway
    _gateway = gateway


def get_webhook_translator(name: str) -> WebhookTranslator | None:
    if name == "stripe":
        return StripeWebhookTranslator(secret=settings.stripe_webhook_secret, tolerance=settings.webhook_tolerance_seconds)
    return None  # tap_payments: reserved in the contract, adapter not built
