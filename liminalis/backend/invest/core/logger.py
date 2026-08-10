"""Compatibility wrapper around the shared Liminalis logging setup."""

from __future__ import annotations

from backend._shared.logging import configure_logging as configure_shared_logging
from backend._shared.logging import get_logger
from backend.settings import get_settings

__all__ = ["get_logger", "setup_logging"]


def setup_logging(level: str = "INFO") -> None:
    """Configure logging using the shared runtime implementation."""
    configure_shared_logging(get_settings(), log_level=level)
