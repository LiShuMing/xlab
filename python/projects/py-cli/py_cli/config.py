"""Configuration management for py-cli."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# Load environment variables from ~/.env
_ENV_PATH: Final = Path.home() / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


@dataclass(frozen=True)
class LLMConfig:
    """LLM client configuration."""

    api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096
    temperature: float = 0.1

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Create configuration from environment variables."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            msg = (
                "ANTHROPIC_API_KEY not found. "
                "Please set it in ~/.env file or environment variables."
            )
            raise ValueError(msg)

        return cls(
            api_key=api_key,
            model=os.getenv("ANTHROPIC_MODEL", cls.model),
            max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", str(cls.max_tokens))),
            temperature=float(os.getenv("ANTHROPIC_TEMPERATURE", str(cls.temperature))),
        )


@dataclass(frozen=True)
class AnalyzerConfig:
    """Git analyzer configuration."""

    default_days: int = 30
    max_commits: int = 100
    max_diff_size: int = 100_000  # Maximum diff size in characters
    include_merge_commits: bool = False

    @classmethod
    def default(cls) -> AnalyzerConfig:
        """Get default configuration."""
        return cls()


@dataclass(frozen=True)
class Config:
    """Global application configuration."""

    llm: LLMConfig
    analyzer: AnalyzerConfig

    @classmethod
    def load(cls) -> Config:
        """Load configuration from environment and defaults."""
        return cls(
            llm=LLMConfig.from_env(),
            analyzer=AnalyzerConfig.default(),
        )
