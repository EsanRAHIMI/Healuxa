from pydantic_settings import SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "notification-service"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/notification"
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"

    default_locale: str = "en"
    default_timezone: str = "Asia/Dubai"

    # Delivery worker (email/SMS/WhatsApp/push). In-app inbox entries need no worker.
    delivery_worker_enabled: bool = True
    delivery_poll_seconds: float = 2.0
    delivery_batch_size: int = 50
    delivery_max_attempts: int = 5
    delivery_backoff_base_seconds: int = 30
    delivery_backoff_max_seconds: int = 3600

    # Channel drivers: `log` (default — records the attempt, sends nothing), `disabled`, or a real
    # driver (`smtp` for email). Real drivers additionally require ALLOW_REAL_DELIVERY=true so that
    # development and test environments can never send a real message.
    email_driver: str = "log"
    sms_driver: str = "log"
    whatsapp_driver: str = "log"
    push_driver: str = "log"
    allow_real_delivery: bool = False

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""  # checked by the SMTP driver when it is selected
    smtp_from: str = "Healuxa <no-reply@healuxa.com>"
    smtp_starttls: bool = True


settings = Settings()
