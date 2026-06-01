from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "assessment-service"
    log_level: str = "INFO"
    tenant_default: str = "healuxa-dubai"

    mongodb_uri: str = ""
    mongodb_database: str = "healuxa_assessment_dev"

    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = ""

    nats_enabled: bool = False
    nats_url: str = "nats://localhost:4222"


settings = Settings()
