"""Shared HTTP and fallback error semantics."""

from __future__ import annotations

from fastapi import HTTPException, status

from backend._shared.storage import allow_business_read_fallback
from backend.settings import Settings


def require_business_database(settings: Settings) -> None:
    """Raise a stable API error when the business database is unavailable."""
    if not settings.postgres_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="business database is not configured",
        )


def should_fallback_after_read_error(settings: Settings) -> bool:
    """Whether read APIs may return a static/config fallback after DB errors."""
    return allow_business_read_fallback(settings)
