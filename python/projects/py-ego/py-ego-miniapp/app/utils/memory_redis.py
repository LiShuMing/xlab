"""In-process Redis subset for local development.

This module intentionally implements only the Redis commands used by the
authentication service. It lets the API run without a local Redis daemon when
``REDIS_URL=memory://`` is set.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _CacheValue:
    value: str
    expires_at: float | None


class MemoryRedis:
    """Small async Redis-compatible token cache for local development."""

    def __init__(self) -> None:
        self._values: dict[str, _CacheValue] = {}

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        """Store a value with a TTL in seconds."""
        self._values[key] = _CacheValue(
            value=value,
            expires_at=time.time() + seconds,
        )
        return True

    async def get(self, key: str) -> str | None:
        """Return a value unless it has expired."""
        cached = self._values.get(key)
        if cached is None:
            return None

        if cached.expires_at is not None and cached.expires_at <= time.time():
            self._values.pop(key, None)
            return None

        return cached.value

    async def delete(self, key: str) -> int:
        """Delete a key and return Redis-like deletion count."""
        existed = key in self._values
        self._values.pop(key, None)
        return int(existed)
