import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "price_aggregator"
    postgres_user: str = "admin"
    postgres_password: str = "changeme"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session_string: str = ""

    # LLM — Groq (all models verified active as of 2026-03)
    # Override any of these in .env
    # Active Groq models: https://console.groq.com/docs/models
    llm_api_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"

    # Fallback chain — all active on Groq free tier as of 2026-03:
    # llama-3.1-8b-instant  — fast, 8B
    # gemma2-9b-it          — Google Gemma 2 9B
    # mistral-saba-24b      — Mistral 24B (preview)
    # compound-beta-mini    — Groq compound model
    llm_fallback_models: str = "llama-3.1-8b-instant,gemma2-9b-it,mistral-saba-24b,compound-beta-mini"

    # App
    secret_key: str = "changeme"
    debug: bool = False
    parser_confidence_threshold: float = 0.5
    skip_unchanged_prices: bool = True

    # Rate limiting: Groq free = 30 rpm, safe delay = 2s
    llm_rate_limit_delay: float = 2.0
    llm_concurrency: int = 1

    # Collector
    collector_history_days: int = 7

    @property
    def llm_fallback_models_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @field_validator("telegram_api_id")
    @classmethod
    def validate_telegram_api_id(cls, v: int) -> int:
        if v == 0:
            logger.warning("TELEGRAM_API_ID is not set — Telegram collection will not work.")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "changeme":
            logger.warning("SECRET_KEY is set to default 'changeme' — change it in production!")
        return v

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
