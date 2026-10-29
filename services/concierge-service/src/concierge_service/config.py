from pydantic_settings import SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "concierge-service"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/concierge"
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"
    # First-response SLA: a coordinator must triage, claim or reply within this many minutes.
    first_response_sla_minutes: int = 240


settings = Settings()
