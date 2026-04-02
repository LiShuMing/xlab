"""HTTP client with connection pooling for LLM API calls.

This module implements Harness Engineering Rule 6.1: Connection Pooling.
Uses httpx.AsyncClient with connection limits and semaphore for concurrency control.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from dbradar.circuit_breaker import with_circuit_breaker, CircuitBreakerOpenError
from dbradar.config import get_settings
from dbradar.logging_config import get_logger

logger = get_logger(__name__)


class LLMHttpClient:
    """Async HTTP client with connection pooling for LLM API calls.

    Features:
    - Connection pooling with configurable limits
    - Semaphore-based concurrency control
    - Retry logic with exponential backoff
    - Circuit breaker integration
    """

    _instance: Optional["LLMHttpClient"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "LLMHttpClient":
        """Singleton pattern to ensure single client instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the HTTP client (only runs once due to singleton)."""
        if self._initialized:
            return

        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._initialized = True

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure the AsyncClient is created with proper configuration."""
        if self._client is None or self._client.is_closed:
            settings = get_settings()

            # Configure connection limits
            limits = httpx.Limits(
                max_connections=settings.http_max_connections,
                max_keepalive_connections=settings.http_max_keepalive,
            )

            # Configure timeout
            timeout = httpx.Timeout(
                connect=10.0,
                read=float(settings.llm_timeout),
                write=10.0,
                pool=5.0,
            )

            self._client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=False,  # Disabled - install httpx[http2] to enable
            )

            logger.debug(
                "http_client_initialized",
                max_connections=settings.http_max_connections,
                max_keepalive=settings.http_max_keepalive,
                timeout=settings.llm_timeout,
            )

        return self._client

    async def _ensure_semaphore(self) -> asyncio.Semaphore:
        """Ensure the concurrency semaphore is created."""
        if self._semaphore is None:
            settings = get_settings()
            # Limit concurrent requests to prevent overwhelming the API
            max_concurrent = min(10, settings.http_max_connections // 2)
            self._semaphore = asyncio.Semaphore(max_concurrent)
            logger.debug("semaphore_initialized", max_concurrent=max_concurrent)
        return self._semaphore

    @asynccontextmanager
    async def acquire(self):
        """Context manager for acquiring a concurrent request slot.

        Usage:
            async with http_client.acquire():
                response = await http_client.post(...)
        """
        semaphore = await self._ensure_semaphore()
        async with semaphore:
            yield

    @with_circuit_breaker
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def post(
        self,
        url: str,
        headers: dict[str, str],
        json_payload: dict,
    ) -> httpx.Response:
        """Make an async POST request with concurrency control and retries.

        Args:
            url: The URL to POST to
            headers: Request headers
            json_payload: JSON body

        Returns:
            The HTTP response

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            httpx.HTTPError: If request fails after retries
        """
        client = await self._ensure_client()

        async with self.acquire():
            logger.debug(
                "http_request_start",
                url=url,
                method="POST",
            )
            response = await client.post(
                url,
                headers=headers,
                json=json_payload,
            )
            response.raise_for_status()
            logger.debug(
                "http_request_success",
                url=url,
                status_code=response.status_code,
            )
            return response

    async def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("http_client_closed")

    async def __aenter__(self) -> "LLMHttpClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# Convenience function for sync code to use async client
def get_http_client() -> LLMHttpClient:
    """Get the global LLM HTTP client instance."""
    return LLMHttpClient()
