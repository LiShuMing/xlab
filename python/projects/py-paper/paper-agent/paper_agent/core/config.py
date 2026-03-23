"""Run configuration management.

Priority (highest to lowest):
1. CLI parameters
2. Config file (--config)
3. Environment variables
4. Default config (configs/default.yaml)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "configs" / "default.yaml"


class RunConfig(BaseModel):
    """Complete configuration for a single run.

    This model validates and manages all configuration parameters,
    following priority: CLI > Config File > Environment > Defaults.
    """

    # I/O
    output_dir: Path = Field(default=Path("./runs"))
    format: list[str] = Field(default=["md", "json"])
    force: bool = False
    cache_dir: Path | None = None
    run_name: str | None = None

    # Parser
    parser: str = "pymupdf"
    chunk_size: int = Field(default=1200, ge=100, le=10000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)
    section_aware: bool = True
    extract_figures: bool = False
    extract_tables: bool = False
    skip_references: bool = False

    # Retrieval
    retrieval_mode: str = "hybrid"
    top_k: int = Field(default=8, ge=1, le=100)
    rerank: bool = False

    # LLM
    provider: str = "anthropic"
    model: str = "claude-opus-4-6"
    embedding_model: str = "text-embedding-3-large"
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    timeout: int = Field(default=120, ge=1, le=600)

    # Analysis
    template: str = "deep-dive"
    analysis_depth: str = "standard"
    with_related: bool = False
    with_critique: bool = False
    with_followup: bool = False
    citation_style: str = "inline"
    focus: str | None = None

    # Pipeline control
    from_stage: str | None = None
    to_stage: str | None = None
    resume: bool = False

    # Engineering
    save_trace: bool = False
    save_prompts: bool = False
    verbose: bool = False
    debug: bool = False

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("format", mode="before")
    @classmethod
    def _validate_format(cls, v: Any) -> Any:
        """Ensure format is a list of valid formats."""
        if isinstance(v, str):
            return [fmt.strip() for fmt in v.split(",")]
        return v

    @field_validator("output_dir", "cache_dir", mode="before")
    @classmethod
    def _validate_path(cls, v: Any) -> Any:
        """Convert string paths to Path objects."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v)
        return v

    @classmethod
    def load(
        cls,
        config_file: Path | None = None,
        **cli_overrides: Any,
    ) -> RunConfig:
        """Load config merging defaults, file, env vars, and CLI overrides.

        Args:
            config_file: Optional path to YAML config file
            **cli_overrides: CLI parameter overrides

        Returns:
            Merged and validated RunConfig instance
        """
        # Start with empty data
        data: dict[str, Any] = {}

        # Load default YAML
        if _DEFAULT_CONFIG.exists():
            with open(_DEFAULT_CONFIG, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    data.update(loaded)

        # Load user config file
        if config_file and config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    data.update(loaded)

        # Apply env vars (PAPER_AGENT_ prefix)
        env_map: dict[str, str] = {
            "PAPER_AGENT_MODEL": "model",
            "PAPER_AGENT_PROVIDER": "provider",
            "PAPER_AGENT_EMBEDDING_MODEL": "embedding_model",
            "PAPER_AGENT_OUTPUT_DIR": "output_dir",
            "PAPER_AGENT_TEMPERATURE": "temperature",
            "PAPER_AGENT_MAX_TOKENS": "max_tokens",
        }
        for env_key, config_key in env_map.items():
            val = os.environ.get(env_key)
            if val:
                # Type conversion for numeric values
                if config_key == "temperature":
                    try:
                        data[config_key] = float(val)
                    except ValueError:
                        continue
                elif config_key == "max_tokens":
                    try:
                        data[config_key] = int(val)
                    except ValueError:
                        continue
                else:
                    data[config_key] = val

        # Apply CLI overrides (None values are ignored)
        for key, val in cli_overrides.items():
            if val is not None:
                data[key] = val

        # Filter to only valid model fields
        valid_fields = set(cls.model_fields.keys())
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to a dictionary with path serialization.

        Returns:
            Dictionary representation of the config
        """
        result: dict[str, Any] = {}
        for key, val in self.model_dump().items():
            if isinstance(val, Path):
                result[key] = str(val)
            else:
                result[key] = val
        return result
