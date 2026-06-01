from pydantic_settings import BaseSettings, SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "profile-service"
    mongodb_uri: str = ""
    mongodb_database: str = "healuxa_profile_dev"
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"
    mongodb_csfle_key_vault: str | None = None
    aws_kms_key_id: str | None = None


settings = Settings()
