from pydantic_settings import SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "provider-service"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/provider"
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"
    supported_currencies: list[str] = ["AED"]
    # Public directory lookups run in this tenant when the caller is anonymous.
    public_tenant: str = "healuxa-dubai"


settings = Settings()
