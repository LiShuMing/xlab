"""Async LLM client for chat completions.

This module provides an OpenAI-compatible async LLM client with
proper error handling, logging, and connection management.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI-compatible async LLM client.

    This client provides async chat completion capabilities using
    an OpenAI-compatible API endpoint (e.g., Kimi, OpenAI, etc.).

    Attributes:
        _settings: Application settings for LLM configuration.
        _client: Async HTTP client for API requests.
    """

    def __init__(self) -> None:
        """Initialize the LLM client with settings."""
        self._settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=self._settings.llm_base_url,
            headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
            timeout=60.0,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.8,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send async chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional parameters for the API.

        Returns:
            str: The generated response content.

        Raises:
            LLMError: If the API request fails.
        """
        payload = {
            "model": self._settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        logger.debug(
            "LLM request",
            extra={
                "model": self._settings.llm_model,
                "message_count": len(messages),
            },
        )

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"] or ""

            logger.debug(
                "LLM response",
                extra={
                    "model": self._settings.llm_model,
                    "response_length": len(content),
                },
            )

            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
            raise LLMError(f"LLM API returned error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"LLM request error: {e}")
            raise LLMError(f"LLM request failed: {e}") from e
        except Exception as e:
            logger.error(f"LLM unexpected error: {e}")
            raise LLMError(f"LLM call failed: {e}") from e

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    async def __aenter__(self) -> LLMClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()


class LLMError(Exception):
    """Exception raised for LLM API errors."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.8,
    max_tokens: int = 2048,
) -> str:
    """Convenience function for single chat completion.

    Creates a temporary client, makes the request, and closes it.
    For multiple requests, use LLMClient directly as a context manager.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.

    Returns:
        str: The generated response content.
    """
    async with LLMClient() as client:
        return await client.chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
