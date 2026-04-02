"""Configuration management for Daily DB Radar using Pydantic Settings.

This module implements type-safe configuration management as per
Harness Engineering Rule 7.1.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe application configuration using Pydantic Settings.

    Configuration is loaded from environment variables and ~/.env file.
    Secrets are automatically masked in logs using SecretStr.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars not defined here
    )

    # LLM Configuration
    llm_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="LLM API key",
    )
    llm_base_url: Optional[str] = Field(
        default=None,
        description="LLM API base URL",
    )
    llm_model: str = Field(
        default="qwen3.5-plus",
        description="LLM model name",
    )
    llm_timeout: int = Field(
        default=300,
        ge=1,
        le=600,
        description="LLM request timeout in seconds",
    )

    # Application Configuration
    cache_dir: Path = Field(
        default=Path("cache"),
        description="Cache directory path",
    )
    output_dir: Path = Field(
        default=Path("out"),
        description="Output directory path",
    )
    feeds_file: Path = Field(
        default=Path("feeds.json"),
        description="Path to feeds.json",
    )
    max_items: int = Field(
        default=80,
        ge=1,
        le=500,
        description="Maximum items to process",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Top K items to select",
    )
    days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to look back",
    )
    language: Literal["en", "zh"] = Field(
        default="en",
        description="Output language",
    )

    # OSS Sync Configuration
    oss_access_key_id: Optional[str] = Field(
        default=None,
        description="OSS access key ID",
    )
    oss_access_key_secret: Optional[SecretStr] = Field(
        default=None,
        description="OSS access key secret",
    )
    oss_endpoint: str = Field(
        default="oss-cn-hangzhou.aliyuncs.com",
        description="OSS endpoint",
    )
    oss_bucket: str = Field(
        default="dbradar-sync",
        description="OSS bucket name",
    )
    oss_prefix: str = Field(
        default="sync/",
        description="OSS file prefix",
    )

    # Circuit Breaker Configuration
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Circuit breaker failure threshold",
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Circuit breaker recovery timeout in seconds",
    )

    # Connection Pool Configuration
    http_max_connections: int = Field(
        default=20,
        ge=1,
        le=100,
        description="HTTP connection pool max connections",
    )
    http_max_keepalive: int = Field(
        default=10,
        ge=1,
        le=50,
        description="HTTP connection pool max keepalive connections",
    )
    http_timeout: int = Field(
        default=30,
        ge=1,
        le=120,
        description="HTTP client timeout in seconds",
    )

    @field_validator("cache_dir", "output_dir", "feeds_file", mode="before")
    @classmethod
    def validate_paths(cls, v: Optional[str]) -> Optional[Path]:
        """Convert string paths to Path objects."""
        if v is None:
            return None
        if isinstance(v, Path):
            return v
        return Path(v)

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_api_key(self) -> str:
        """Get the API key as a plain string.

        Note: Only use this when actually making API calls.
        Never log the returned value.
        """
        return self.llm_api_key.get_secret_value() if self.llm_api_key else ""

    def get_oss_secret(self) -> Optional[str]:
        """Get the OSS secret as a plain string.

        Note: Only use this when actually making OSS calls.
        Never log the returned value.
        """
        if self.oss_access_key_secret:
            return self.oss_access_key_secret.get_secret_value()
        return None


# Backward compatibility: Config class that wraps Settings
class Config:
    """Backward-compatible configuration holder.

    Deprecated: Use Settings class directly instead.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        website_file: Optional[Path] = None,
        feeds_file: Optional[Path] = None,
        max_items: int = 80,
        top_k: int = 10,
        days: int = 7,
        language: str = "en",
        oss_access_key_id: Optional[str] = None,
        oss_access_key_secret: Optional[str] = None,
        oss_endpoint: Optional[str] = None,
        oss_bucket: Optional[str] = None,
        oss_prefix: Optional[str] = None,
    ):
        """Initialize Config with backward-compatible parameters."""
        settings = get_settings()

        self.api_key = api_key or settings.get_api_key()
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.timeout = settings.llm_timeout
        self.cache_dir = cache_dir or settings.cache_dir
        self.output_dir = output_dir or settings.output_dir
        self.website_file = website_file or Path("websites.txt")
        self.feeds_file = feeds_file or settings.feeds_file
        self.max_items = max_items or settings.max_items
        self.top_k = top_k or settings.top_k
        self.days = days or settings.days
        self.language = language or settings.language

        # OSS sync configuration
        self.oss_access_key_id = oss_access_key_id or settings.oss_access_key_id
        self.oss_access_key_secret = (
            oss_access_key_secret or settings.get_oss_secret()
        )
        self.oss_endpoint = oss_endpoint or settings.oss_endpoint
        self.oss_bucket = oss_bucket or settings.oss_bucket
        self.oss_prefix = oss_prefix or settings.oss_prefix

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get the cached Settings instance.

    Settings are loaded once and cached for the lifetime of the application.
    This ensures consistent configuration across all components.
    """
    return Settings()


# Global config instance for backward compatibility
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance (backward compatible)."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance (backward compatible)."""
    global _config
    _config = config
