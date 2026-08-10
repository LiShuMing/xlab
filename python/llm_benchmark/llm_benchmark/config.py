"""Configuration loader from ~/.env file.

Reads OpenAI-compatible API credentials and runtime settings.
Supports KEY=VALUE format, ignoring comments (#) and blank lines.
Environment variables take precedence over .env file values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ModelConfig:
    """Configuration for a single model endpoint."""

    name: str
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    temperature: float = 0.0
    seed: int = 42
    max_tokens: int = 4096
    max_concurrent: int = 4
    timeout: float = 120.0


@dataclass
class BenchmarkConfig:
    """Top-level configuration for the benchmark framework."""

    default_model: str = ""
    models: dict[str, ModelConfig] = field(default_factory=dict)
    results_dir: Path = Path("results")


def _env_path() -> Path:
    """Return path to ~/.env file."""
    return Path.home() / ".env"


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE env file, ignoring comments and blank lines."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _resolve_env(key: str, file_values: dict[str, str]) -> Optional[str]:
    """Resolve a key: environment variable first, then .env file."""
    env_val = os.environ.get(key)
    if env_val is not None:
        return env_val
    return file_values.get(key)


def load_config(env_file: Optional[Path] = None) -> BenchmarkConfig:
    """Load benchmark configuration from ~/.env.

    Supported keys:
        LLM_BASE_URL     - default API base URL
        LLM_API_KEY      - default API key
        LLM_MODEL        - default model name
        LLM_MAX_CONCURRENT - max concurrent API calls (default: 4)
        LLM_TIMEOUT      - per-request timeout in seconds (default: 120)
        LLM_MAX_TOKENS   - max tokens per response (default: 4096)

    Multi-model format:
        LLM_MODEL_1=name,base_url,api_key
        LLM_MODEL_2=name,base_url,api_key
    """
    path = env_file or _env_path()
    file_values = _parse_env_file(path)

    # Default model config
    default_base_url = _resolve_env("LLM_BASE_URL", file_values) or "https://api.openai.com/v1"
    default_api_key = _resolve_env("LLM_API_KEY", file_values) or ""
    default_model_name = _resolve_env("LLM_MODEL", file_values) or ""
    max_concurrent = int(_resolve_env("LLM_MAX_CONCURRENT", file_values) or "4")
    timeout = float(_resolve_env("LLM_TIMEOUT", file_values) or "120")
    max_tokens = int(_resolve_env("LLM_MAX_TOKENS", file_values) or "4096")

    config = BenchmarkConfig(default_model=default_model_name)

    # Register default model
    if default_model_name:
        config.models[default_model_name] = ModelConfig(
            name=default_model_name,
            base_url=default_base_url,
            api_key=default_api_key,
            max_concurrent=max_concurrent,
            timeout=timeout,
            max_tokens=max_tokens,
        )

    # Register additional models (LLM_MODEL_1, LLM_MODEL_2, ...)
    for key, value in sorted(file_values.items()):
        if key.startswith("LLM_MODEL_") and key != "LLM_MODEL":
            parts = value.split(",")
            if len(parts) >= 2:
                model_name = parts[0].strip()
                model_base_url = parts[1].strip()
                model_api_key = parts[2].strip() if len(parts) > 2 else default_api_key
                config.models[model_name] = ModelConfig(
                    name=model_name,
                    base_url=model_base_url,
                    api_key=model_api_key,
                    max_concurrent=max_concurrent,
                    timeout=timeout,
                    max_tokens=max_tokens,
                )

    return config


def get_model_config(config: BenchmarkConfig, model_name: Optional[str] = None) -> ModelConfig:
    """Get model config by name, falling back to default model."""
    if model_name and model_name in config.models:
        return config.models[model_name]
    if config.default_model and config.default_model in config.models:
        return config.models[config.default_model]
    if config.models:
        return next(iter(config.models.values()))
    raise ValueError(
        "No model configured. Set LLM_MODEL, LLM_BASE_URL, and LLM_API_KEY in ~/.env"
    )