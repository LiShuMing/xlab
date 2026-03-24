"""Application configuration using pydantic-settings for type-safe settings management."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    """

    # App
    app_env: str = "development"
    app_secret_key: str = "dev-secret-key"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pyego_miniapp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # WeChat
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    # LLM
    llm_base_url: str = "https://api.kimi.com/v1"
    llm_api_key: str = ""
    llm_model: str = "kimi-for-coding"

    # Embedding
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = 512

    # JWT
    jwt_secret_key: str = "jwt-secret-key"
    jwt_access_token_expire_minutes: int = 120
    jwt_refresh_token_expire_days: int = 7

    class Config:
        """Pydantic settings configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Returns:
        Settings: Application settings instance.
    """
    return Settings()