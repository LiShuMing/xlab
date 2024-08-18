from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings


PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_ENV = Path.home() / ".env"


def _normalize_postgres_host(raw_url: str) -> tuple[str, str | None]:
    """Extract host and optional port from a PSQL_URL value."""
    parsed = urlparse(raw_url if "://" in raw_url else f"//{raw_url}")
    host = parsed.hostname or raw_url.split(":", 1)[0]
    port = str(parsed.port) if parsed.port else None
    return host, port


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    """

    # App
    app_env: str = "development"
    app_secret_key: str = "dev-secret-key"

    # Database
    database_url: str = ""
    psql_url: str = ""
    psql_port: str = "5432"
    psql_user: str = ""
    psql_password: str = ""
    psql_default_db: str = ""

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

    @model_validator(mode="after")
    def build_database_url_from_psql_env(self) -> "Settings":
        """Build SQLAlchemy's asyncpg URL from ~/.env PSQL_* settings."""
        if self.database_url:
            return self

        if self.psql_url and self.psql_user and self.psql_password:
            host, embedded_port = _normalize_postgres_host(self.psql_url)
            port = embedded_port or self.psql_port or "5432"
            database = self.psql_default_db or "postgres"
            user = quote(self.psql_user, safe="")
            password = quote(self.psql_password, safe="")
            database = quote(database, safe="")
            self.database_url = (
                f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
            )
        else:
            self.database_url = "sqlite+aiosqlite:///./pyego_local.db"
        return self

    class Config:
        """Pydantic settings configuration."""

        env_file = (HOME_ENV, PROJECT_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Returns:
        Settings: Application settings instance.
    """
    return Settings()
