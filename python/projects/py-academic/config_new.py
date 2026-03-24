"""
Configuration module using Pydantic Settings.
Reads from ~/.env with LLM_ prefix.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    from pydantic import Field, field_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


def _load_env_file() -> None:
    """Load environment file from ~/.env"""
    default_path = Path.home() / ".env"
    env_path = Path(os.getenv("ENV_PATH", str(default_path)))
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


if HAS_PYDANTIC:
    class LLMConfig(BaseSettings):
        """LLM API configuration from ~/.env"""
        
        model_config = SettingsConfigDict(
            env_prefix="LLM_",
            env_file=str(Path.home() / ".env"),
            env_file_encoding="utf-8",
            extra="ignore",
        )
        
        base_url: str = "https://api.openai.com/v1"
        api_key: str = ""
        model: str = "gpt-4o-mini"
        timeout: int = 120
        
        @field_validator("api_key", mode="before")
        @classmethod
        def validate_api_key(cls, v: str) -> str:
            return v or ""
    
    
    class Settings(BaseSettings):
        """Central configuration."""
        
        model_config = SettingsConfigDict(
            env_file=str(Path.home() / ".env"),
            env_file_encoding="utf-8",
            extra="ignore",
        )
        
        llm: LLMConfig = Field(default_factory=LLMConfig)
        log_level: str = "INFO"
        
        @field_validator("log_level", mode="before")
        @classmethod
        def validate_log_level(cls, v: str) -> str:
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            v_upper = v.upper()
            if v_upper not in valid_levels:
                return "INFO"
            return v_upper
    
    
    @lru_cache(maxsize=1)
    def get_settings() -> Settings:
        """Get cached settings instance."""
        _load_env_file()
        return Settings()
    
    
    def get_openai_client():
        """Get an OpenAI-compatible client instance."""
        from openai import OpenAI
        
        settings = get_settings()
        return OpenAI(
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key,
            timeout=settings.llm.timeout,
        )
    
    
    # Legacy compatibility - module level attributes
    def __getattr__(name: str):
        settings = get_settings()
        legacy_attrs = {
            "LLM_BASE_URL": settings.llm.base_url,
            "LLM_API_KEY": settings.llm.api_key,
            "LLM_MODEL": settings.llm.model,
            "LLM_TIMEOUT": settings.llm.timeout,
            "LOG_LEVEL": settings.log_level,
        }
        if name in legacy_attrs:
            return legacy_attrs[name]
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

else:
    # Fallback to simple os.getenv if pydantic is not available
    _load_env_file()
    
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    def get_openai_client():
        """Get an OpenAI-compatible client instance."""
        from openai import OpenAI
        return OpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            timeout=LLM_TIMEOUT,
        )
