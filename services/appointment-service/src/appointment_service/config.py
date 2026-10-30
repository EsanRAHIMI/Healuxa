from pydantic_settings import SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "appointment-service"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/appointment"
    nats_enabled: bool = False

    # Caller authentication (bearer introspection) and this service's own service token.
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    identity_service_token_url: str = "http://localhost:8001/v1/auth/service-token"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"

    # Availability source of truth (synchronous, short timeout; failures answer 503 — never guess).
    provider_service_url: str = "http://localhost:8005"
    provider_timeout_seconds: float = 3.0

    # Slot discovery for anonymous callers runs in this tenant.
    public_tenant: str = "healuxa-dubai"

    # Booking policy.
    hold_ttl_minutes: int = 10
    max_active_holds_per_customer: int = 3
    slot_interval_minutes: int = 15
    min_lead_minutes: int = 60
    max_horizon_days: int = 90
    max_slot_range_days: int = 31
    customer_cancel_cutoff_minutes: int = 120
    check_in_opens_minutes: int = 60
    no_show_grace_minutes: int = 15
    reminder_offsets_minutes: list[int] = [1440, 120]
    # Stage D hook: when true, priced bookings start with payment_status=pending and cannot be
    # confirmed until payment-service reports the payment authorized or captured.
    payment_required: bool = False

    # Background sweeper: expires holds/unanswered requests and hands due reminders to notification.
    sweeper_enabled: bool = True
    sweeper_interval_seconds: float = 30.0


settings = Settings()
