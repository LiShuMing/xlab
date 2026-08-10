"""Shared ML runtime environment helpers."""

from __future__ import annotations

import logging
import os

from backend.settings import Settings
from backend.settings import get_settings as get_runtime_settings

ML_ENV_DEFAULTS = {
    "PYTORCH_ENABLE_MPS_FALLBACK": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
    "TOKENIZERS_PARALLELISM": "false",
    "TRANSFORMERS_VERBOSITY": "error",
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
}

ML_LIBRARY_LOGGERS = [
    "sentence_transformers",
    "transformers",
    "urllib3",
    "httpcore",
    "openai",
    "huggingface_hub",
    "httpx",
    "tqdm",
    "torch",
]


def configure_ml_environment(settings: Settings | None = None) -> None:
    """Configure process environment before importing ML libraries."""
    settings = settings or get_runtime_settings()
    for key, value in ML_ENV_DEFAULTS.items():
        os.environ[key] = value
    os.environ["USE_SIMPLE_EMBEDDING"] = "true" if settings.ego_simple_embedding_enabled else "false"


def is_simple_embedding_mode(settings: Settings | None = None) -> bool:
    """Return whether Ego should use deterministic hash embeddings."""
    settings = settings or get_runtime_settings()
    return settings.ego_simple_embedding_enabled


def suppress_ml_library_logs(*, level: int = logging.ERROR, disable: bool = False) -> None:
    """Reduce noisy third-party ML/HTTP logs."""
    for logger_name in ML_LIBRARY_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.disabled = disable
