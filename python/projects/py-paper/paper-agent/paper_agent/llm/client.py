"""LLM client supporting Anthropic SDK with observability and metrics."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from paper_agent.utils.exceptions import (
    ConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from paper_agent.utils.logging import (
    get_logger,
    log_llm_request,
    log_llm_response,
)

logger = get_logger(__name__)


class LLMClient:
    """LLM client with structured logging, retries, and metrics.

    Reads from environment variables by default:
      - ANTHROPIC_API_KEY or QWEN_API_KEY
      - ANTHROPIC_BASE_URL or QWEN_BASE_URL
      - ANTHROPIC_MODEL (defaults to claude-opus-4-6)

    All LLM calls are logged with correlation IDs and timing metrics for observability.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        timeout: int = 120,
    ) -> None:
        """Initialize the LLM client.

        Args:
            model: Model name (e.g., 'claude-opus-4-6', 'qwen3.5-plus')
            api_key: API key (falls back to env vars)
            base_url: Custom base URL for API endpoint
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            timeout: Request timeout in seconds

        Raises:
            ConfigurationError: If API key is not provided and not in environment
        """
        resolved_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("QWEN_API_KEY")
        )
        resolved_url = (
            base_url
            or os.environ.get("ANTHROPIC_BASE_URL")
            or os.environ.get("QWEN_BASE_URL")
        )
        self.model = (
            model
            or os.environ.get("ANTHROPIC_MODEL")
            or "qwen3.5-plus"
        )
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        if not resolved_key:
            raise ConfigurationError(
                "API key not found. Set ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or QWEN_API_KEY.",
            )

        kwargs: dict[str, Any] = {"api_key": resolved_key, "timeout": timeout}
        if resolved_url:
            kwargs["base_url"] = resolved_url

        self._client = anthropic.Anthropic(**kwargs)
        logger.info(
            "llm_client_initialized",
            model=self.model,
            base_url=resolved_url,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((LLMTimeoutError, LLMRateLimitError)),
        reraise=True,
    )
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a prompt and return the text response.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Override default max_tokens
            temperature: Override default temperature

        Returns:
            The LLM response text

        Raises:
            LLMTimeoutError: If the request times out
            LLMRateLimitError: If rate limited
            LLMResponseError: If the response is invalid
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature

        log_llm_request(
            logger,
            model=self.model,
            messages=messages,
            system_present=system is not None,
            max_tokens=kwargs["max_tokens"],
            temperature=temperature or self.temperature,
        )

        start_time = time.perf_counter()
        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.APITimeoutError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "llm_timeout",
                model=self.model,
                timeout=self.timeout,
                elapsed_ms=round(elapsed_ms, 2),
            )
            raise LLMTimeoutError(
                f"LLM request timed out after {self.timeout}s",
                timeout_seconds=self.timeout,
                model=self.model,
                prompt_length=len(prompt),
            ) from e
        except anthropic.RateLimitError as e:
            retry_after = getattr(e, "retry_after", None)
            logger.error(
                "llm_rate_limited",
                model=self.model,
                retry_after=retry_after,
            )
            raise LLMRateLimitError(
                "LLM rate limit exceeded",
                retry_after=retry_after,
                model=self.model,
                prompt_length=len(prompt),
            ) from e
        except anthropic.APIError as e:
            logger.error(
                "llm_api_error",
                model=self.model,
                error=type(e).__name__,
                message=str(e),
            )
            raise LLMError(
                f"LLM API error: {e}",
                model=self.model,
                prompt_length=len(prompt),
                details={"error_type": type(e).__name__},
            ) from e

        # Handle ThinkingBlock + TextBlock (qwen3.5 thinking models)
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        log_llm_response(
            logger,
            model=self.model,
            response=text,
            latency_ms=elapsed_ms,
            usage=usage,
        )

        return text

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Send a prompt expecting a JSON response.

        Strips markdown code fences automatically.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Override default max_tokens

        Returns:
            Parsed JSON as dict or list

        Raises:
            LLMResponseError: If the response cannot be parsed as JSON
        """
        text = self.complete(prompt, system=system, max_tokens=max_tokens)

        # Strip ```json ... ``` fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        try:
            result = json.loads(cleaned)
            if not isinstance(result, (dict, list)):
                raise LLMResponseError(
                    "LLM response is not a JSON object or array",
                    raw_response=text,
                    model=self.model,
                    prompt_length=len(prompt),
                )
            return result
        except json.JSONDecodeError as e:
            logger.error(
                "json_parse_failed",
                error=str(e),
                text_preview=cleaned[:200],
                model=self.model,
            )
            raise LLMResponseError(
                f"Failed to parse LLM response as JSON: {e}",
                raw_response=text,
                model=self.model,
                prompt_length=len(prompt),
            ) from e

    def complete_structured(
        self,
        prompt: str,
        response_schema: type,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Send a prompt and validate response against a Pydantic schema.

        Args:
            prompt: The user prompt
            response_schema: Pydantic model class for validation
            system: Optional system prompt
            max_tokens: Override default max_tokens

        Returns:
            Validated Pydantic model instance

        Raises:
            LLMResponseError: If validation fails
        """
        from pydantic import ValidationError as PydanticValidationError

        raw = self.complete_json(prompt, system=system, max_tokens=max_tokens)

        try:
            if isinstance(raw, dict):
                return response_schema(**raw)
            # If it's a list and schema expects a single item, wrap it
            return response_schema(data=raw)
        except PydanticValidationError as e:
            logger.error(
                "schema_validation_failed",
                error=str(e),
                model=self.model,
            )
            raise LLMResponseError(
                f"LLM response failed schema validation: {e}",
                    raw_response=json.dumps(raw),
                model=self.model,
                prompt_length=len(prompt),
            ) from e
