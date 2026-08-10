"""Shared API response shape helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def page_response(
    *,
    items: Sequence[Any],
    page: int,
    per_page: int,
    total_items: int,
    **extra: Any,
) -> dict[str, Any]:
    """Build a consistent paginated response dictionary."""
    total_pages = (total_items + per_page - 1) // per_page if total_items else 0
    return {
        "items": list(items),
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        **extra,
    }
