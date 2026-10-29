"""payment-service settings.

Secrets (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SERVICE_AUTH_CLIENT_SECRET`) are covered by the
py-common production secret guard via the ``secret`` name fragment. On top of that this module refuses
any configuration that could move real money unless it is explicitly, consistently and only in
production asked for (see ``live_mode_problems``).
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import SettingsConfigDict

from healuxa_py_common.config import PRODUCTION_ENVS, ServiceSettings

LIVE_SECRET_PREFIXES = ("sk_live_", "rk_live_")
TEST_SECRET_PREFIXES = ("sk_test_", "rk_test_")
NON_PRODUCTION_FAKE_ENVS = {"development", "dev", "test", "ci", "local"}

DEFAULT_VAT_RATES_BPS = {
    # UAE VAT standard rate 5%. Healthcare zero-rating (Art. 41 Executive Regulation) may apply to some
    # preventive/basic healthcare lines — PENDING ACCOUNTANT REVIEW before any live invoice.
    "professional_service": 500,
    "facility_service": 500,
    "platform_fee": 500,
    "concierge_service": 500,
    "membership": 500,
    "third_party": 500,
}


def live_mode_problems(
    *,
    app_env: str,
    payment_gateway: str,
    payments_live_mode: bool,
    stripe_secret_key: str,
    stripe_publishable_key: str,
) -> list[str]:
    """Reasons this configuration must not start. Empty list = allowed."""
    problems: list[str] = []
    env = app_env.lower()
    secret_is_live = stripe_secret_key.startswith(LIVE_SECRET_PREFIXES)
    publishable_is_live = stripe_publishable_key.startswith("pk_live_")
    if payment_gateway == "fake" and env not in NON_PRODUCTION_FAKE_ENVS:
        problems.append(f"PAYMENT_GATEWAY=fake is only allowed in development/test (APP_ENV={app_env})")
    if secret_is_live or publishable_is_live or payments_live_mode:
        if not payments_live_mode:
            problems.append("live Stripe key present but PAYMENTS_LIVE_MODE is not true")
        if not secret_is_live:
            problems.append("PAYMENTS_LIVE_MODE=true requires a STRIPE_SECRET_KEY starting with sk_live_/rk_live_")
        if env != "production":
            problems.append(f"live payments are refused outside APP_ENV=production (APP_ENV={app_env})")
        if stripe_publishable_key and not publishable_is_live:
            problems.append("live mode requires a pk_live_ publishable key")
    elif payment_gateway == "stripe":
        if not stripe_secret_key.startswith(TEST_SECRET_PREFIXES):
            problems.append("PAYMENT_GATEWAY=stripe in sandbox mode requires an sk_test_/rk_test_ STRIPE_SECRET_KEY")
        if stripe_publishable_key and not stripe_publishable_key.startswith("pk_test_"):
            problems.append("sandbox mode requires a pk_test_ publishable key")
    return problems


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "payment-service"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/payment"
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"

    # ── Processor (PaymentGateway ACL) ──────────────────────────────────────
    payment_gateway: Literal["stripe", "fake"] = "fake"
    payments_live_mode: bool = False
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_api_base: str = "https://api.stripe.com"
    # Pinned API version: request/response shapes the adapter was written and tested against.
    stripe_api_version: str = "2024-06-20"
    stripe_timeout_seconds: float = 15.0
    webhook_tolerance_seconds: int = 300
    currency: str = "AED"

    # ── Pricing & tax (VAT configuration PENDING ACCOUNTANT REVIEW) ────────
    platform_fee_bps: int = 500
    platform_fee_fixed_minor: int = 0
    platform_fee_label: str = "Healuxa coordination fee"
    vat_name: str = "VAT"
    vat_rates_bps: dict[str, int] = DEFAULT_VAT_RATES_BPS
    tax_config_reviewed: bool = False
    quote_ttl_seconds: int = 1800
    appointment_capture_method: Literal["automatic", "manual"] = "manual"

    # ── Refund policy (cancellation window) ─────────────────────────────────
    refund_full_window_hours: int = 24
    refund_partial_percent: int = 50

    # ── Invoices ────────────────────────────────────────────────────────────
    invoice_number_prefix: str = "HLX"
    seller_legal_name: str = "Healuxa (legal entity name pending)"
    seller_trn: str = "TRN-PENDING"
    seller_address: str = "Dubai, United Arab Emirates (registered address pending)"

    # ── Integrations ────────────────────────────────────────────────────────
    provider_service_url: str = "http://localhost:8005"
    membership_payments_enabled: bool = False

    @model_validator(mode="after")
    def _refuse_unsafe_payment_mode(self):
        problems = live_mode_problems(
            app_env=self.app_env,
            payment_gateway=self.payment_gateway,
            payments_live_mode=self.payments_live_mode,
            stripe_secret_key=self.stripe_secret_key,
            stripe_publishable_key=self.stripe_publishable_key,
        )
        if self.app_env.lower() in PRODUCTION_ENVS and self.payment_gateway == "stripe" and not self.stripe_webhook_secret.startswith("whsec_"):
            problems.append("STRIPE_WEBHOOK_SECRET must be a whsec_ signing secret")
        if problems:
            raise ValueError("refusing payment configuration: " + "; ".join(problems))
        if not 0 <= self.platform_fee_bps <= 5000:
            raise ValueError("PLATFORM_FEE_BPS must be between 0 and 5000")
        if any(not 0 <= v <= 10000 for v in self.vat_rates_bps.values()):
            raise ValueError("VAT_RATES_BPS values must be between 0 and 10000")
        return self


settings = Settings()
