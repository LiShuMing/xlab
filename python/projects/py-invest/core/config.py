"""Configuration management using pydantic-settings."""

from functools import lru_cache
from typing import Optional
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load ~/.env first (global config), then local .env
load_dotenv(Path.home() / ".env")
load_dotenv(override=True)


class Settings(BaseSettings):
    """Application settings.

    Attributes:
        app_name: Application display name.
        app_env: Deployment environment (development/production).
        debug: Enable debug mode.
        log_level: Logging level.
        openai_api_key: OpenAI API key.
        openai_base_url: OpenAI API base URL.
        model_name: Default LLM model name.
        llm_temperature: Default LLM temperature.
        llm_max_tokens: Default max tokens for LLM.
        database_url: PostgreSQL connection URL.
        redis_url: Redis connection URL.
        api_host: API server host.
        api_port: API server port.
        cors_origins: Allowed CORS origins.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = "Invest-AI"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "info"

    # LLM settings
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    model_name: str = "gpt-4o"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4000

    # Database settings
    database_url: str = "postgresql://localhost:5432/invest_ai"
    redis_url: str = "redis://localhost:6379/0"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment.

        Returns:
            True if in production, False otherwise.
        """
        return self.app_env == "production"

    @property
    def llm_config(self) -> dict:
        """Get LLM configuration dictionary.

        Returns:
            Dictionary with LLM settings.
        """
        return {
            "api_key": self.openai_api_key,
            "base_url": self.openai_base_url,
            "model_name": self.model_name,
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
        }


@lru_cache
def get_settings() -> Settings:
    """Get singleton settings instance.

    Returns:
        Cached Settings instance.
    """
    return Settings()
