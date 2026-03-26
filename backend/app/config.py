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

    # LLM — primary model
    llm_api_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # LLM — fallback models tried in order when primary returns 429/404.
    # Comma-separated, e.g.:
    # LLM_FALLBACK_MODELS=meta-llama/llama-3.3-70b-instruct:free,mistralai/mistral-7b-instruct:free
    llm_fallback_models: str = (
        "meta-llama/llama-3.3-70b-instruct:free,"
        "mistralai/mistral-7b-instruct:free,"
        "qwen/qwen2.5-vl-72b-instruct:free"
    )

    # App
    secret_key: str = "changeme"
    debug: bool = False
    parser_confidence_threshold: float = 0.5
    skip_unchanged_prices: bool = True

    # Collector: how many days back to fetch on first run (and hard cutoff on every run)
    # Override via COLLECTOR_HISTORY_DAYS=14 in .env
    collector_history_days: int = 7

    @property
    def llm_fallback_models_list(self) -> list[str]:
        """Return fallback models as a list, filtering empty strings."""
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @field_validator("telegram_api_id")
    @classmethod
    def validate_telegram_api_id(cls, v: int) -> int:
        if v == 0:
            logger.warning(
                "TELEGRAM_API_ID is not set — Telegram collection will not work. "
                "Set it in .env file."
            )
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "changeme":
            logger.warning(
                "SECRET_KEY is set to default 'changeme' — change it in production!"
            )
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
