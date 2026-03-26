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

    # LLM — Groq only
    # Set in .env:
    #   LLM_API_URL=https://api.groq.com/openai/v1
    #   LLM_API_KEY=gsk_...
    #   LLM_MODEL=llama-3.3-70b-versatile
    #   LLM_FALLBACK_MODELS=llama3-70b-8192,mixtral-8x7b-32768
    llm_api_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"

    # Groq fallback models (all served at api.groq.com)
    llm_fallback_models: str = "llama3-70b-8192,mixtral-8x7b-32768,gemma2-9b-it"

    # App
    secret_key: str = "changeme"
    debug: bool = False
    parser_confidence_threshold: float = 0.5
    skip_unchanged_prices: bool = True

    # Rate limiting: seconds between LLM calls (Groq free = 30 rpm)
    llm_rate_limit_delay: float = 2.0
    llm_concurrency: int = 1

    # Collector: how many days back to fetch on first run
    collector_history_days: int = 7

    @property
    def llm_fallback_models_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @field_validator("telegram_api_id")
    @classmethod
    def validate_telegram_api_id(cls, v: int) -> int:
        if v == 0:
            logger.warning(
                "TELEGRAM_API_ID is not set — Telegram collection will not work."
            )
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
