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
from typing import Optional

import yaml
from pydantic import BaseModel, Field

_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "configs" / "default.yaml"


class RunConfig(BaseModel):
    """Complete configuration for a single run."""

    # I/O
    output_dir: Path = Field(default=Path("./runs"))
    format: list[str] = Field(default=["md", "json"])
    force: bool = False
    cache_dir: Optional[Path] = None
    run_name: Optional[str] = None

    # Parser
    parser: str = "pymupdf"
    chunk_size: int = 1200
    chunk_overlap: int = 150
    section_aware: bool = True
    extract_figures: bool = False
    extract_tables: bool = False
    skip_references: bool = False

    # Retrieval
    retrieval_mode: str = "hybrid"
    top_k: int = 8
    rerank: bool = False

    # LLM
    provider: str = "anthropic"
    model: str = "claude-opus-4-6"
    embedding_model: str = "text-embedding-3-large"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 120

    # Analysis
    template: str = "deep-dive"
    analysis_depth: str = "standard"
    with_related: bool = False
    with_critique: bool = False
    with_followup: bool = False
    citation_style: str = "inline"
    focus: Optional[str] = None

    # Pipeline control
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None
    resume: bool = False

    # Engineering
    save_trace: bool = False
    save_prompts: bool = False
    verbose: bool = False
    debug: bool = False

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def load(
        cls,
        config_file: Optional[Path] = None,
        **cli_overrides,
    ) -> "RunConfig":
        """Load config merging defaults, file, env vars, and CLI overrides."""
        # Start with defaults
        data: dict = {}

        # Load default YAML
        if _DEFAULT_CONFIG.exists():
            with open(_DEFAULT_CONFIG) as f:
                data.update(yaml.safe_load(f) or {})

        # Load user config file
        if config_file and config_file.exists():
            with open(config_file) as f:
                data.update(yaml.safe_load(f) or {})

        # Apply env vars (PAPER_AGENT_ prefix)
        env_map = {
            "PAPER_AGENT_MODEL": "model",
            "PAPER_AGENT_PROVIDER": "provider",
            "PAPER_AGENT_EMBEDDING_MODEL": "embedding_model",
        }
        for env_key, config_key in env_map.items():
            val = os.environ.get(env_key)
            if val:
                data[config_key] = val

        # Apply CLI overrides (None values are ignored)
        for key, val in cli_overrides.items():
            if val is not None:
                data[key] = val

        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})
