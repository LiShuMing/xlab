"""Exponential backoff retry logic for API calls."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})


async def with_retry(
    fn: Callable[..., T],
    *args,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    **kwargs,
) -> T:
    """Call fn with exponential backoff retry on transient errors.

    Retries on:
        - HTTP 429 (Too Many Requests)
        - HTTP 502/503/504 (Server Errors)
        - httpx.TimeoutException
        - httpx.NetworkError

    Args:
        fn: Async callable to retry.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay in seconds between retries.
        backoff_factor: Multiplier for exponential backoff.

    Returns:
        The return value of fn on success.

    Raises:
        The last exception after exhausting retries.
    """
    import httpx

    last_exception: Exception | None = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRYABLE_STATUSES:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        "HTTP %d on attempt %d/%d, retrying in %.1fs...",
                        e.response.status_code,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                    continue
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    "%s on attempt %d/%d, retrying in %.1fs...",
                    type(e).__name__,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
                continue
            raise

    assert last_exception is not None
    raise last_exception