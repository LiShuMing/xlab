"""HTTP client with connection pooling for LLM API calls.

This module implements Harness Engineering Rule 6.1: Connection Pooling.
Uses httpx.AsyncClient with connection limits and semaphore for concurrency control.
"""

import asyncio
from contextlib import asynccontextmanager

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend._shared.http import (
    HTTPClientConfig,
    HTTPError,
    Response,
    SharedAsyncHTTPClient,
    TimeoutException,
)
from backend.radar.circuit_breaker import with_circuit_breaker
from backend.radar.logging_config import get_logger
from backend.settings import get_settings

logger = get_logger(__name__)


class LLMHttpClient:
    """Async HTTP client with connection pooling for LLM API calls.

    Features:
    - Connection pooling with configurable limits
    - Semaphore-based concurrency control
    - Retry logic with exponential backoff
    - Circuit breaker integration
    """

    _instance: "LLMHttpClient | None" = None
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

        self._client: SharedAsyncHTTPClient | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._initialized = True

    async def _ensure_client(self) -> SharedAsyncHTTPClient:
        """Ensure the shared async HTTP client is created with proper configuration."""
        if self._client is None:
            settings = get_settings()
            config = HTTPClientConfig.from_settings(
                settings,
                read_timeout=settings.llm_timeout,
            )
            self._client = SharedAsyncHTTPClient(config)

            logger.debug(
                "http_client_initialized",
                max_connections=config.max_connections,
                max_keepalive=config.max_keepalive_connections,
                timeout=settings.llm_timeout,
            )

        return self._client

    async def _ensure_semaphore(self) -> asyncio.Semaphore:
        """Ensure the concurrency semaphore is created."""
        if self._semaphore is None:
            client = await self._ensure_client()
            max_concurrent = client.max_concurrency
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
        retry=retry_if_exception_type((HTTPError, TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def post(
        self,
        url: str,
        headers: dict[str, str],
        json_payload: dict,
    ) -> Response:
        """Make an async POST request with concurrency control and retries.

        Args:
            url: The URL to POST to
            headers: Request headers
            json_payload: JSON body

        Returns:
            The HTTP response

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            HTTPError: If request fails after retries
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
        if self._client:
            await self._client.close()
            self._client = None
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
