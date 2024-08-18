"""Shared httpx client with retry + circuit breaker.

py-radar carries its own circuit_breaker.py + tenacity wrappers; M1 will
collapse those into this module. M0 ships just the typed factory so new
code can already start importing from here.
"""

from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


def make_client(
    *,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, headers=headers or {}, timeout=timeout)
