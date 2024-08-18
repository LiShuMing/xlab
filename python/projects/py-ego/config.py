"""
Configuration module using Pydantic Settings for type-safe configuration management.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM API configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=str(Path.home() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-3.5-turbo"
    timeout: int = 120

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Allow empty API key for local testing."""
        return v or ""


class EmbeddingConfig(BaseSettings):
    """Embedding model configuration."""

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_",
        env_file=str(Path.home() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = "BAAI/bge-small-zh-v1.5"
    use_local: bool = True  # Default to local because Kimi API doesn't support embeddings


class AppConfig(BaseSettings):
    """Application-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=str(Path.home() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper


class Settings(BaseSettings):
    """Central configuration container."""

    model_config = SettingsConfigDict(
        env_file=str(Path.home() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    @property
    def llm_model(self) -> str:
        return self.llm.model

    @property
    def llm_base_url(self) -> str:
        return self.llm.base_url

    @property
    def llm_api_key(self) -> str:
        return self.llm.api_key

    @property
    def llm_timeout(self) -> int:
        return self.llm.timeout

    @property
    def embedding_model(self) -> str:
        return self.embedding.model

    @property
    def use_local_embedding(self) -> bool:
        return self.embedding.use_local

    @property
    def log_level(self) -> str:
        return self.app.log_level


def _load_env_file() -> None:
    """Load environment file based on ENV_PATH if set."""
    default_path = Path.home() / ".env"
    env_path = Path(os.getenv("ENV_PATH", str(default_path)))
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    _load_env_file()
    return Settings()


def get_openai_client() -> "OpenAI":
    """Get an OpenAI-compatible client instance."""
    from openai import OpenAI

    settings = get_settings()
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
    )


# Legacy backward compatibility
def __getattr__(name: str):
    settings = get_settings()
    legacy_attrs = {
        "LLM_BASE_URL": settings.llm_base_url,
        "LLM_API_KEY": settings.llm_api_key,
        "LLM_MODEL": settings.llm_model,
        "LLM_TIMEOUT": settings.llm_timeout,
        "EMBEDDING_MODEL": settings.embedding_model,
        "USE_LOCAL_EMBEDDING": settings.use_local_embedding,
        "LOG_LEVEL": settings.log_level,
    }
    if name in legacy_attrs:
        return legacy_attrs[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")