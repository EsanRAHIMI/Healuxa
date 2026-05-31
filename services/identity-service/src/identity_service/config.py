from pydantic_settings import BaseSettings, SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "identity-service"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/identity"
    jwt_private_key_pem: str | None = None
    jwt_access_ttl: int = 900
    jwt_refresh_ttl: int = 2592000
    jwt_issuer: str = "https://api.healuxa.com"
    argon2_memory_cost: int = 65536
    argon2_time_cost: int = 3
    argon2_parallelism: int = 4
    password_pepper: str = "dev-pepper-change-me"
    mfa_issuer: str = "Healuxa"
    mfa_encryption_key: str = "dev-mfa-key-32bytes-long!!!!!!"
    otp_ttl: int = 300
    login_max_attempts: int = 5
    lockout_seconds: int = 900
    nats_enabled: bool = False
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"


settings = Settings()
