"""LLM client wrapper using OpenAI SDK."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from openai import RateLimitError as OpenAIRateLimitError

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM configuration.

    Attributes:
        api_key: API key for the LLM provider.
        base_url: Base URL for the API endpoint.
        model_name: Model identifier (e.g., 'qwen-plus', 'gpt-4o').
        temperature: Sampling temperature (0.0-1.0).
        max_tokens: Maximum tokens in response.
        timeout: Request timeout in seconds.
    """

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model_name: str = "qwen-plus"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 120

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from ~/.env file.

        Returns:
            LLMConfig instance with values from environment.
        """
        env_path = Path.home() / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

        return cls(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            model_name=os.getenv("LLM_MODEL", "qwen-plus"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4000")),
            timeout=int(os.getenv("LLM_TIMEOUT", "120")),
        )


@lru_cache(maxsize=1)
def _get_cached_config() -> LLMConfig:
    """Get cached LLM config."""
    return LLMConfig.from_env()


class LLMClient:
    """LLM client for OpenAI-compatible APIs.

    This client wraps the OpenAI SDK for use with various LLM providers
    including Qwen (DashScope), Kimi, and standard OpenAI models.

    Example:
        >>> client = LLMClient()
        >>> response = await client.chat("你好")
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM client.

        Args:
            config: Optional LLM configuration. Uses ~/.env if not provided.
        """
        self.config = config or _get_cached_config()
        self._sync_client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None

    @property
    def model(self) -> "ModelProperty":
        """Get model property for langchain-like access.

        Returns:
            ModelProperty instance with invoke/ainvoke methods.
        """
        return ModelProperty(self)

    def _get_async_client(self) -> AsyncOpenAI:
        """Get async OpenAI client.

        Returns:
            AsyncOpenAI instance.
        """
        if self._async_client is None:
            import httpx
            # Check if we need to use proxy
            proxy = os.getenv("https_proxy") or os.getenv("HTTP_PROXY")

            # For LLM API calls, often better to bypass proxy
            # Create client without proxy for better async compatibility
            self._async_client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                http_client=httpx.AsyncClient(proxy=None) if proxy else None,
            )
        return self._async_client

    def _get_sync_client(self) -> OpenAI:
        """Get sync OpenAI client.

        Returns:
            OpenAI instance.
        """
        if self._sync_client is None:
            self._sync_client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._sync_client

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """Send chat completion request.

        Args:
            messages: List of message dicts with role/content.
            **kwargs: Additional args for chat.completions.create.

        Returns:
            Response content string.
        """
        client = self._get_async_client()
        response = await client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs
        )
        return response.choices[0].message.content

    def chat_sync(self, messages: list[dict], **kwargs) -> str:
        """Send synchronous chat completion request.

        Args:
            messages: List of message dicts with role/content.
            **kwargs: Additional args for chat.completions.create.

        Returns:
            Response content string.
        """
        client = self._get_sync_client()
        response = client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs
        )
        return response.choices[0].message.content

    def with_temperature(self, temperature: float) -> "LLMClient":
        """Create new client with specified temperature.

        Args:
            temperature: New temperature value.

        Returns:
            New LLMClient instance.
        """
        return LLMClient(LLMConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model_name=self.config.model_name,
            temperature=temperature,
            max_tokens=self.config.max_tokens,
        ))

    def with_max_tokens(self, max_tokens: int) -> "LLMClient":
        """Create new client with specified max_tokens.

        Args:
            max_tokens: New max tokens value.

        Returns:
            New LLMClient instance.
        """
        return LLMClient(LLMConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=max_tokens,
        ))


@dataclass
class RateLimitStats:
    """Statistics for rate-limited client.

    Attributes:
        total_requests: Total number of requests made.
        total_tokens: Total tokens used (if tracked).
        rate_limit_retries: Number of rate limit retries.
        max_concurrent_reached: Times semaphore was fully utilized.
    """
    total_requests: int = 0
    total_tokens: int = 0
    rate_limit_retries: int = 0
    max_concurrent_reached: int = 0


class RateLimitedLLMClient:
    """Wraps LLMClient with concurrency control and retry logic.

    This wrapper provides:
    - Semaphore-based concurrency limiting
    - Token usage tracking (optional)
    - Exponential backoff retry for 429 rate limit errors

    Example:
        >>> client = LLMClient()
        >>> rate_limited = RateLimitedLLMClient.wrap(client, max_concurrent=5)
        >>> response = await rate_limited.chat([{"role": "user", "content": "Hello"}])
    """

    def __init__(
        self,
        client: LLMClient,
        max_concurrent: int = 5,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        track_tokens: bool = True,
    ):
        """Initialize rate-limited wrapper.

        Args:
            client: The underlying LLMClient to wrap.
            max_concurrent: Maximum concurrent API calls.
            max_retries: Maximum retry attempts for 429 errors.
            base_delay: Base delay for exponential backoff (seconds).
            max_delay: Maximum delay for exponential backoff (seconds).
            track_tokens: Whether to track token usage.
        """
        self._client = client
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._track_tokens = track_tokens
        self._stats = RateLimitStats()
        self._lock = asyncio.Lock()

    @classmethod
    def wrap(
        cls,
        client: LLMClient,
        max_concurrent: int = 5,
        **kwargs,
    ) -> "RateLimitedLLMClient":
        """Create a rate-limited wrapper around an LLMClient.

        Args:
            client: The LLMClient to wrap.
            max_concurrent: Maximum concurrent API calls.
            **kwargs: Additional arguments passed to __init__.

        Returns:
            RateLimitedLLMClient instance.
        """
        return cls(client, max_concurrent=max_concurrent, **kwargs)

    @property
    def config(self) -> LLMConfig:
        """Access the underlying client's config."""
        return self._client.config

    @property
    def model(self) -> "ModelProperty":
        """Access the underlying client's model property."""
        return self._client.model

    @property
    def stats(self) -> RateLimitStats:
        """Get current rate limit statistics."""
        return self._stats

    async def _update_stats(self, **kwargs) -> None:
        """Thread-safe stats update."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._stats, key):
                    current = getattr(self._stats, key)
                    setattr(self._stats, key, current + value)

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """Send chat completion request with rate limiting.

        This method wraps the underlying client's chat() with:
        - Concurrency control via semaphore
        - Retry logic for 429 errors with exponential backoff

        Args:
            messages: List of message dicts with role/content.
            **kwargs: Additional args for chat.completions.create.

        Returns:
            Response content string.

        Raises:
            RateLimitError: If max retries exceeded for rate limiting.
            Exception: Other exceptions from the underlying client.
        """
        async with self._semaphore:
            # Track if we're at max capacity
            if self._semaphore.locked():
                await self._update_stats(max_concurrent_reached=1)

            last_exception = None

            for attempt in range(self._max_retries + 1):
                try:
                    await self._update_stats(total_requests=1)

                    response = await self._client.chat(messages, **kwargs)

                    # Track tokens if response provides them
                    if self._track_tokens and hasattr(response, 'usage'):
                        tokens = getattr(response.usage, 'total_tokens', 0)
                        await self._update_stats(total_tokens=tokens)

                    return response

                except OpenAIRateLimitError as e:
                    last_exception = e
                    await self._update_stats(rate_limit_retries=1)

                    if attempt < self._max_retries:
                        delay = min(
                            self._base_delay * (2 ** attempt),
                            self._max_delay
                        )
                        logger.warning(
                            f"Rate limit hit, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{self._max_retries})"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({self._max_retries}) exceeded for rate limit"
                        )
                        raise

                except Exception:
                    # Non-rate-limit errors pass through immediately
                    raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in rate-limited chat")

    def chat_sync(self, messages: list[dict], **kwargs) -> str:
        """Synchronous chat - passes through without rate limiting.

        Note: Rate limiting is primarily for async concurrent calls.
        For sync usage, implement external throttling if needed.

        Args:
            messages: List of message dicts with role/content.
            **kwargs: Additional args for chat.completions.create.

        Returns:
            Response content string.
        """
        return self._client.chat_sync(messages, **kwargs)

    def with_temperature(self, temperature: float) -> "RateLimitedLLMClient":
        """Create new rate-limited client with specified temperature.

        Args:
            temperature: New temperature value.

        Returns:
            New RateLimitedLLMClient instance wrapping new LLMClient.
        """
        new_client = self._client.with_temperature(temperature)
        return RateLimitedLLMClient(
            client=new_client,
            max_concurrent=self._max_concurrent,
            max_retries=self._max_retries,
            base_delay=self._base_delay,
            max_delay=self._max_delay,
            track_tokens=self._track_tokens,
        )

    def with_max_tokens(self, max_tokens: int) -> "RateLimitedLLMClient":
        """Create new rate-limited client with specified max_tokens.

        Args:
            max_tokens: New max tokens value.

        Returns:
            New RateLimitedLLMClient instance wrapping new LLMClient.
        """
        new_client = self._client.with_max_tokens(max_tokens)
        return RateLimitedLLMClient(
            client=new_client,
            max_concurrent=self._max_concurrent,
            max_retries=self._max_retries,
            base_delay=self._base_delay,
            max_delay=self._max_delay,
            track_tokens=self._track_tokens,
        )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RateLimitedLLMClient("
            f"max_concurrent={self._max_concurrent}, "
            f"stats={self._stats})"
        )


class ModelProperty:
    """Property wrapper for langchain-like model access."""

    def __init__(self, client: LLMClient):
        self.client = client

    def _convert_messages(self, messages: list) -> list[dict]:
        """Convert langchain messages to OpenAI format.

        Args:
            messages: List of langchain Message objects.

        Returns:
            List of dicts with role/content in OpenAI format.
        """
        role_map = {
            "human": "user",
            "ai": "assistant",
            "assistant": "assistant",
            "system": "system",
            "user": "user",
        }
        result = []
        for m in messages:
            msg_type = getattr(m, "type", "user")
            role = role_map.get(msg_type, "user")
            result.append({"role": role, "content": m.content})
        return result

    def invoke(self, messages: list) -> "AIMessage":
        """Synchronous invoke (langchain compatible).

        Args:
            messages: List of langchain Message objects.

        Returns:
            AIMessage with response content.
        """
        msg_dicts = self._convert_messages(messages)
        content = self.client.chat_sync(msg_dicts)
        return AIMessage(content=content)

    async def ainvoke(self, messages: list) -> "AIMessage":
        """Async invoke (langchain compatible).

        Args:
            messages: List of langchain Message objects.

        Returns:
            AIMessage with response content.
        """
        msg_dicts = self._convert_messages(messages)
        content = await self.client.chat(msg_dicts)
        return AIMessage(content=content)


class AIMessage:
    """Simple AI message wrapper for langchain compatibility."""

    def __init__(self, content: str):
        self.content = content
        self.type = "assistant"

    def __repr__(self) -> str:
        return f"AIMessage(content={self.content!r})"


class HumanMessage:
    """Human message wrapper for langchain compatibility."""

    def __init__(self, content: str):
        self.content = content
        self.type = "human"

    def __repr__(self) -> str:
        return f"HumanMessage(content={self.content!r})"


class SystemMessage:
    """System message wrapper for langchain compatibility."""

    def __init__(self, content: str):
        self.content = content
        self.type = "system"

    def __repr__(self) -> str:
        return f"SystemMessage(content={self.content!r})"


async def create_llm_client(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
) -> LLMClient:
    """Factory function to create LLM client.

    Args:
        model_name: Optional model name override.
        temperature: Optional temperature override.

    Returns:
        Configured LLMClient instance.
    """
    config = LLMConfig.from_env()

    if model_name:
        config.model_name = model_name
    if temperature is not None:
        config.temperature = temperature

    return LLMClient(config)
