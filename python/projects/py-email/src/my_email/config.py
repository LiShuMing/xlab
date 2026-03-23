"""
Application configuration management.

Settings are loaded from:
1. Environment variables (highest priority)
2. Local .env file
3. Global ~/.env file for LLM settings (shared across projects)
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_from_env_file(env_path: Path, keys: list[str]) -> dict[str, str]:
    """
    Load specific keys from an env file.

    Args:
        env_path: Path to .env file.
        keys: List of keys to extract.

    Returns:
        Dict of key → value pairs found in the file.
    """
    result: dict[str, str] = {}
    if not env_path.exists():
        return result

    content = env_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            if key in keys:
                result[key] = value.strip()
    return result


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    LLM settings are loaded from ~/.env to allow sharing across projects.
    All other settings are loaded from local .env or environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,  # Make settings immutable after creation
    )

    # Gmail API configuration
    gmail_credentials_file: Path = Field(
        default=Path.home() / ".credentials/my-email/client_secret.json",
        description="Path to OAuth client secret JSON file",
    )
    gmail_token_file: Path = Field(
        default=Path.home() / ".credentials/my-email/token.json",
        description="Path to stored OAuth token file",
    )
    gmail_filter_query: str = Field(
        default="from:(*-dev@lists.apache.org) OR from:(announce@apache.org) OR label:newsletters",
        description="Gmail search query for filtering messages",
    )
    gmail_max_results: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum messages to fetch per API call",
    )
    gmail_timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="HTTP timeout in seconds for Gmail API calls",
    )
    gmail_proxy: str = Field(
        default="",
        description="HTTP proxy for Gmail API (e.g., http://127.0.0.1:7890)",
    )

    # Database configuration
    db_path: Path = Field(
        default=Path("data/my_email.db"),
        description="Path to SQLite database file",
    )

    # LLM configuration — loaded from ~/.env (global config)
    llm_base_url: str = Field(
        default="",
        description="OpenAI-compatible API base URL",
    )
    llm_api_key: str = Field(
        default="",
        description="API key for LLM endpoint",
    )
    llm_model: str = Field(
        default="",
        description="Model identifier to use for summarization",
    )
    llm_timeout: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Timeout in seconds for LLM API calls",
    )

    # Logging configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper


# Global LLM keys that should be loaded from ~/.env
_GLOBAL_LLM_KEYS: Final[list[str]] = [
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT",
    "LOG_LEVEL",
]


def _create_settings() -> Settings:
    """
    Create settings instance, loading LLM config from global ~/.env.

    Returns:
        Configured Settings instance.
    """
    # Start with environment/base settings
    settings = Settings()

    # Load LLM settings from ~/.env (global config shared across projects)
    global_env = Path.home() / ".env"
    global_config = _load_from_env_file(global_env, _GLOBAL_LLM_KEYS)

    # Build override dict for settings that have global values
    overrides: dict[str, str | int] = {}
    if global_config.get("LLM_BASE_URL"):
        overrides["llm_base_url"] = global_config["LLM_BASE_URL"]
    if global_config.get("LLM_API_KEY"):
        overrides["llm_api_key"] = global_config["LLM_API_KEY"]
    if global_config.get("LLM_MODEL"):
        overrides["llm_model"] = global_config["LLM_MODEL"]
    if global_config.get("LLM_TIMEOUT"):
        overrides["llm_timeout"] = int(global_config["LLM_TIMEOUT"])
    if global_config.get("LOG_LEVEL"):
        overrides["log_level"] = global_config["LOG_LEVEL"]

    # Create new settings with overrides (frozen=True ensures immutability)
    if overrides:
        return Settings(**overrides)

    return settings


# Singleton settings instance
settings: Final[Settings] = _create_settings()