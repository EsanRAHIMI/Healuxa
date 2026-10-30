from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCTION_ENVS = {"production", "staging"}
# Settings whose names contain these fragments are treated as secrets.
SECRET_FRAGMENTS = ("secret", "pepper", "encryption_key", "private_key")
# Values that betray a development default left in place.
INSECURE_MARKERS = ("change-me", "changeme", "dev-", "ci-", "test-", "example")


def insecure_secrets(values: dict[str, object]) -> list[str]:
    """Names of secret-like settings that are empty or still hold a development default."""
    problems = []
    for name, value in values.items():
        if not any(fragment in name for fragment in SECRET_FRAGMENTS):
            continue
        if name == "jwt_private_key_pem" and value is None:
            continue  # optional: identity-service then manages signing keys in its database
        text = "" if value is None else str(value)
        if not text.strip() or any(marker in text.lower() for marker in INSECURE_MARKERS):
            problems.append(name.upper())
    return problems


class ServiceSettings(BaseSettings):
    """Shared backend settings per Healuxa_TechSpec.md §25.1."""

    # hide_input_in_errors: a failed validation must never echo secret values into logs.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

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

    @model_validator(mode="after")
    def _refuse_insecure_secrets_in_production(self):
        # A deployment that forgets a secret must fail loudly, never run on a public dev default.
        if self.app_env.lower() in PRODUCTION_ENVS:
            problems = insecure_secrets(self.model_dump())
            if problems:
                raise ValueError(
                    f"APP_ENV={self.app_env}: set real values for " + ", ".join(sorted(problems))
                )
        return self
