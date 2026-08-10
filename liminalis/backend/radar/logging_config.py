"""Compatibility wrapper around the shared Liminalis logging setup."""

from __future__ import annotations

from backend._shared.logging import (
    CorrelationIdContext,
    add_correlation_id,
    correlation_id,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)
from backend._shared.logging import configure_logging as configure_shared_logging
from backend.settings import get_settings

__all__ = [
    "CorrelationIdContext",
    "add_correlation_id",
    "configure_logging",
    "correlation_id",
    "get_correlation_id",
    "get_logger",
    "set_correlation_id",
]


def configure_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    """Configure logging using the shared runtime implementation."""
    configure_shared_logging(get_settings(), log_level=log_level, json_format=json_format)
