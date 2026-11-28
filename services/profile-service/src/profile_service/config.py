from pydantic_settings import BaseSettings, SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "profile-service"
    mongodb_uri: str = ""
    mongodb_database: str = "healuxa_profile_dev"
    mongodb_server_selection_timeout_ms: int = 10_000
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"
    mongodb_csfle_key_vault: str | None = None
    aws_kms_key_id: str | None = None

    # ── Medical records (documents a customer uploads and shares by explicit consent) ──────────
    # Base64 of 32 random bytes (AES-256-GCM). Empty disables the records API (503) outside
    # production; production refuses to start without it (py-common secret guard).
    records_encryption_key: str = ""
    # Identifier stored with every sealed file so keys can be rotated.
    records_key_id: str = "k1"
    # Retired keys still needed to open older files: "<key_id>:<base64>,<key_id>:<base64>".
    records_retired_keys: str = ""
    records_max_file_bytes: int = 10 * 1024 * 1024
    records_max_per_user: int = 200
    records_max_total_bytes_per_user: int = 1024 * 1024 * 1024
    records_default_grant_days: int = 30
    records_max_grant_days: int = 365
    # Facility staff roles that may read records shared with their facility (billing is excluded).
    records_facility_roles: str = "facility_admin,scheduler"

    # Organisation membership source of truth (synchronous, short timeout; failures refuse the read).
    identity_service_token_url: str = "http://localhost:8001/v1/auth/service-token"
    provider_service_url: str = "http://localhost:8005"
    provider_timeout_seconds: float = 3.0


settings = Settings()
