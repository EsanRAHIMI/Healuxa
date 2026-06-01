from pydantic_settings import BaseSettings, SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "transformation-engine"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/transformation"
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"
    # TechSpec §25.2 placeholders — not used in scaffold
    mongodb_uri: str | None = None
    ai_orchestrator_url: str = "http://localhost:8017"
    ml_service_url: str = "http://localhost:8018"
    matching_url: str = "http://localhost:8006"
    commercial_url: str = "http://localhost:8020"
    kpi_objective: str = "outcomes_retention_ltv"


settings = Settings()
