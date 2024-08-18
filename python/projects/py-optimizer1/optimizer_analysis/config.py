"""Configuration for Optimizer Analysis system."""
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM configuration for AI-powered analysis."""
    base_url: str = Field(..., description="OpenAI-compatible API base URL")
    api_key: str = Field(..., description="API key")
    model: str = Field(..., description="Model name")
    timeout: int = Field(120, description="Request timeout in seconds")

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load LLM configuration from environment variables."""
        return cls(
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "gpt-4"),
            timeout=int(os.getenv("LLM_TIMEOUT", "120")),
        )

    @classmethod
    def from_env_file(cls, env_path: str = "~/.env") -> "LLMConfig":
        """Load LLM configuration from .env file."""
        env_file = Path(env_path).expanduser()
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
        return cls.from_env()


class AppConfig(BaseModel):
    """Application configuration."""
    llm: LLMConfig
    work_dir: str = Field(".", description="Working directory for artifacts")
    log_level: str = Field("INFO", description="Logging level")

    @classmethod
    def load(cls, env_path: str = "~/.env") -> "AppConfig":
        """Load configuration from environment."""
        llm_config = LLMConfig.from_env_file(env_path)
        return cls(
            llm=llm_config,
            work_dir=os.getenv("OPTIMIZER_WORK_DIR", "."),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )