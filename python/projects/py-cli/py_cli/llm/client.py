"""Anthropic LLM client wrapper."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from py_cli.config import LLMConfig
from py_cli.exceptions import LLMError
from py_cli.llm.models import LLMResponse

if TYPE_CHECKING:
    from collections.abc import Sequence

# Import anthropic with fallback for type checking
try:
    from anthropic import Anthropic, AsyncAnthropic
except ImportError:
    Anthropic = Any  # type: ignore[misc, assignment]
    AsyncAnthropic = Any  # type: ignore[misc, assignment]


class LLMClient:
    """Client for Anthropic Claude API."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        """Initialize LLM client.

        Args:
            config: LLM configuration (loads from env if not provided)
        """
        self.config = config or LLMConfig.from_env()
        self._client: Anthropic | None = None
        self._async_client: AsyncAnthropic | None = None

    def _get_client(self) -> Anthropic:
        """Get or create synchronous client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                msg = (
                    "anthropic package not installed. "
                    "Run: pip install anthropic>=0.20.0"
                )
                raise LLMError(msg) from e

            self._client = Anthropic(api_key=self.config.api_key)
        return self._client

    def _get_async_client(self) -> AsyncAnthropic:
        """Get or create asynchronous client."""
        if self._async_client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as e:
                msg = (
                    "anthropic package not installed. "
                    "Run: pip install anthropic>=0.20.0"
                )
                raise LLMError(msg) from e

            self._async_client = AsyncAnthropic(api_key=self.config.api_key)
        return self._async_client

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
    ) -> LLMResponse:
        """Send a completion request to the LLM.

        Args:
            system_prompt: System instructions
            user_prompt: User message content
            max_retries: Maximum number of retry attempts

        Returns:
            LLM response

        Raises:
            LLMError: If request fails after all retries
        """
        client = self._get_client()

        for attempt in range(max_retries):
            try:
                message = client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                        }
                    ],
                )

                content = ""
                if message.content and len(message.content) > 0:
                    content = str(message.content[0].text) if hasattr(message.content[0], 'text') else str(message.content[0])

                return LLMResponse(
                    content=content,
                    model=message.model,
                    usage=dict(message.usage) if message.usage else {},
                    finish_reason=message.stop_reason,
                )

            except Exception as e:
                if attempt == max_retries - 1:
                    msg = f"LLM request failed after {max_retries} attempts: {e}"
                    raise LLMError(msg) from e

                # Exponential backoff
                wait_time = 2**attempt
                import time

                time.sleep(wait_time)

        # This should never be reached
        msg = "Unexpected end of complete method"
        raise LLMError(msg)

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
    ) -> LLMResponse:
        """Send an async completion request to the LLM.

        Args:
            system_prompt: System instructions
            user_prompt: User message content
            max_retries: Maximum number of retry attempts

        Returns:
            LLM response
        """
        client = self._get_async_client()

        for attempt in range(max_retries):
            try:
                message = await client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                        }
                    ],
                )

                content = ""
                if message.content and len(message.content) > 0:
                    content = str(message.content[0].text) if hasattr(message.content[0], 'text') else str(message.content[0])

                return LLMResponse(
                    content=content,
                    model=message.model,
                    usage=dict(message.usage) if message.usage else {},
                    finish_reason=message.stop_reason,
                )

            except Exception as e:
                if attempt == max_retries - 1:
                    msg = f"LLM request failed after {max_retries} attempts: {e}"
                    raise LLMError(msg) from e

                wait_time = 2**attempt
                await asyncio.sleep(wait_time)

        msg = "Unexpected end of complete_async method"
        raise LLMError(msg)

    async def complete_batch(
        self,
        requests: Sequence[tuple[str, str]],
        max_concurrency: int = 5,
    ) -> list[LLMResponse]:
        """Send multiple completion requests concurrently.

        Args:
            requests: List of (system_prompt, user_prompt) tuples
            max_concurrency: Maximum number of concurrent requests

        Returns:
            List of LLM responses in the same order as requests
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _complete_with_limit(
            system_prompt: str, user_prompt: str
        ) -> LLMResponse:
            async with semaphore:
                return await self.complete_async(system_prompt, user_prompt)

        tasks = [
            _complete_with_limit(sys_prompt, user_prompt)
            for sys_prompt, user_prompt in requests
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)
