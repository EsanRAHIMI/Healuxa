from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Shared backend settings per Healuxa_TechSpec.md §25.1."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    service_name: str = "unknown-service"
    log_level: str = "INFO"
    nats_url: str = "nats://localhost:4222"
    redis_url: str = "redis://localhost:6379/0"
    otel_exporter_otlp_endpoint: str | None = None
    sentry_dsn: str | None = None
    jwt_public_jwks_url: str = "http://identity-service:8001/.well-known/jwks.json"
    service_auth_client_id: str | None = None
    service_auth_client_secret: str | None = None
    internal_network: str = "healuxa-net"
    tenant_default: str = "healuxa-dubai"
