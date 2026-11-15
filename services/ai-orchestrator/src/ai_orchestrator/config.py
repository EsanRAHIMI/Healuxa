from pydantic_settings import SettingsConfigDict

from healuxa_py_common.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "ai-orchestrator"
    database_url: str = "postgresql+asyncpg://healuxa:dev@localhost:5432/ai"
    nats_enabled: bool = False
    identity_introspect_url: str = "http://localhost:8001/v1/auth/introspect"
    service_auth_client_id: str = "healuxa-internal"
    service_auth_client_secret: str = "dev-service-secret-change-me"

    # ── LLM provider (ACL). "anthropic" needs ANTHROPIC_API_KEY; "fake" is the deterministic test double.
    # Deliberately not named *_secret: an unset key must degrade to 503, not refuse to boot.
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    anthropic_max_tokens: int = 8000
    anthropic_timeout_seconds: float = 45.0
    anthropic_max_retries: int = 1
    # Server-side refusal fallback (beta). Disable if the account/platform rejects the parameter.
    anthropic_refusal_fallback: bool = True

    # ── Verified platform data sources (tools). Base URLs include /v1.
    provider_api_url: str = "http://localhost:8005/v1"
    appointment_api_url: str = "http://localhost:8007/v1"
    transformation_api_url: str = "http://localhost:8000/v1"
    concierge_api_url: str = "http://localhost:8021/v1"
    tool_timeout_seconds: float = 6.0

    # ── Guardrails enforced in code.
    max_message_chars: int = 2000
    max_turns_per_session: int = 80
    history_turns: int = 16
    max_tool_iterations: int = 6
    max_tool_calls_per_turn: int = 12
    turn_timeout_seconds: float = 90.0
    rate_limit_per_minute: int = 8
    rate_limit_per_day: int = 150
    max_cards_per_turn: int = 6
    slot_lookahead_days: int = 14


settings = Settings()
