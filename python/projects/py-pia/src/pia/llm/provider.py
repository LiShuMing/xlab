"""LLM provider abstraction with retry logic and comprehensive telemetry.

Auto-detects the protocol from LLM_BASE_URL:
  - URL contains "anthropic" → use Anthropic Messages API (anthropic SDK)
  - Otherwise              → use OpenAI-compatible Chat API (openai SDK)

This lets pia work with:
  - Anthropic Claude directly (api.anthropic.com)
  - DashScope Anthropic-compatible proxy (coding.dashscope.aliyuncs.com/apps/anthropic)
  - Kimi / OpenAI / any OpenAI-compatible endpoint
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Literal

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pia.config.settings import get_settings
from pia.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from pia.llm.prompts import SYSTEM_PROMPT, make_analysis_prompt, make_extraction_prompt
from pia.llm.schemas import ReleaseExtraction
from pia.telemetry import get_context_dict, increment_agent_step
from pia.telemetry.metrics import timed_llm_call

if TYPE_CHECKING:
    from pia.models.product import Product
    from pia.models.release import Release
    from pia.models.source_doc import NormalizedDoc

logger = structlog.get_logger()
PROMPT_VERSION = "v1"


class LLMProvider:
    """LLM provider with auto-selection, retry logic, and full telemetry.

    Features:
    - Auto-detects Anthropic vs OpenAI protocol
    - Exponential backoff retry for transient failures
    - Full request/response logging at DEBUG level
    - Metrics collection for latency tracking
    - Context propagation (correlation_id, session_id)
    """

    def __init__(self, model: str | None = None) -> None:
        """Initialize the LLM provider.

        Args:
            model: LLM model name override. Falls back to settings.

        Raises:
            LLMConfigurationError: If required configuration is missing.
        """
        settings = get_settings()
        self.model = model or settings.llm_model
        self._base_url = settings.llm_base_url
        self._api_key = settings.llm_api_key
        self._timeout = settings.llm_timeout
        self._use_anthropic = self._is_anthropic_endpoint(self._base_url)

        if not self._api_key:
            raise LLMConfigurationError(
                "LLM_API_KEY is not configured. Add it to ~/.env: LLM_API_KEY=sk-..."
            )

        if self._use_anthropic:
            import anthropic

            self._client = anthropic.Anthropic(
                base_url=self._base_url,
                api_key=self._api_key,
            )
            logger.info(
                "llm backend: anthropic-compatible",
                base_url=self._base_url,
                model=self.model,
            )
        else:
            import openai

            self._client = openai.OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=self._timeout,
            )
            logger.info(
                "llm backend: openai-compatible",
                base_url=self._base_url,
                model=self.model,
            )

    @staticmethod
    def _is_anthropic_endpoint(base_url: str) -> bool:
        """Check if the endpoint is Anthropic-based."""
        return "anthropic" in base_url.lower()

    def _log_request(self, messages: list[dict[str, Any]], max_tokens: int) -> None:
        """Log the LLM request at DEBUG level.

        This is non-negotiable for debugging hallucinations and prompt issues.
        """
        context = get_context_dict()
        log_data: dict[str, Any] = {
            "event": "llm_request",
            "model": self.model,
            "max_tokens": max_tokens,
            "message_count": len(messages),
        }
        if context.get("correlation_id"):
            log_data["correlation_id"] = context["correlation_id"]
        if context.get("session_id"):
            log_data["session_id"] = context["session_id"]
        if context.get("agent_step"):
            log_data["agent_step"] = context["agent_step"]

        # Log full payload at TRACE level (may be very large)
        logger.debug("LLM request payload", messages=messages, **log_data)

    def _log_response(self, response_text: str, latency_ms: float | None = None) -> None:
        """Log the LLM response at DEBUG level."""
        context = get_context_dict()
        log_data: dict[str, Any] = {
            "event": "llm_response",
            "model": self.model,
            "response_length": len(response_text),
        }
        if latency_ms is not None:
            log_data["latency_ms"] = round(latency_ms, 2)
        if context.get("correlation_id"):
            log_data["correlation_id"] = context["correlation_id"]

        # Log preview at DEBUG, full response at TRACE
        preview = response_text[:500] + "..." if len(response_text) > 500 else response_text
        logger.debug("LLM response received", preview=preview, **log_data)
        logger.debug("LLM full response", response=response_text, **log_data)

    def _call(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        operation: str = "unknown",
    ) -> str:
        """Synchronously call the LLM with retry logic.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Maximum tokens to generate.
            operation: Operation name for metrics/logging.

        Returns:
            Generated text response.

        Raises:
            LLMTimeoutError: On timeout.
            LLMRateLimitError: On rate limit.
            LLMResponseError: On other errors.
        """
        increment_agent_step()

        # Log the full request before any network call
        self._log_request(messages, max_tokens)

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
            reraise=True,
        )
        def _call_with_retry() -> str:
            with timed_llm_call(self.model, operation) as record:
                try:
                    if self._use_anthropic:
                        response = self._client.messages.create(
                            model=self.model,
                            max_tokens=max_tokens,
                            system=SYSTEM_PROMPT,
                            messages=messages,  # type: ignore[arg-type]
                        )
                        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
                        if not text_blocks:
                            raise LLMResponseError(
                                "Empty Anthropic response: no text blocks",
                                model=self.model,
                            )
                        result = "\n".join(text_blocks)
                    else:
                        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
                        response = self._client.chat.completions.create(
                            model=self.model,
                            messages=full_messages,  # type: ignore[arg-type]
                            max_tokens=max_tokens,
                        )
                        content = response.choices[0].message.content
                        if not content:
                            raise LLMResponseError(
                                "Empty OpenAI response: no content",
                                model=self.model,
                            )
                        result = content

                    self._log_response(result)
                    record(success=True)
                    return result

                except httpx.TimeoutException as e:
                    record(success=False, error_type="TimeoutException")
                    raise LLMTimeoutError(self.model, self._timeout) from e
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        retry_after = e.response.headers.get("retry-after")
                        record(
                            success=False,
                            error_type="RateLimitError",
                        )
                        raise LLMRateLimitError(
                            self.model,
                            retry_after=int(retry_after) if retry_after else None,
                        ) from e
                    record(success=False, error_type=f"HTTP_{e.response.status_code}")
                    raise LLMResponseError(
                        f"HTTP error: {e.response.status_code}",
                        model=self.model,
                        cause=e,
                    ) from e
                except Exception as e:
                    error_type = type(e).__name__
                    record(success=False, error_type=error_type)
                    raise LLMResponseError(
                        f"LLM call failed: {e}",
                        model=self.model,
                        cause=e,
                    ) from e

        return _call_with_retry()

    async def extract_release_info(
        self,
        product_name: str,
        version: str,
        content: str,
    ) -> ReleaseExtraction:
        """Stage A: structured extraction from release notes.

        Args:
            product_name: Human-readable product name.
            version: Release version.
            content: Normalized markdown content.

        Returns:
            Structured extraction result.

        Raises:
            LLMResponseError: If extraction fails or response cannot be parsed.
        """
        prompt = make_extraction_prompt(product_name, version, content)
        text = self._call(
            [{"role": "user", "content": prompt}],
            max_tokens=4096,
            operation="extract",
        )

        # Extract JSON from markdown code block or raw JSON
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                logger.error(
                    "no json in extraction response",
                    preview=text[:500],
                    product=product_name,
                    version=version,
                )
                raise LLMResponseError(
                    "LLM did not return valid JSON in extraction response",
                    model=self.model,
                    response_preview=text[:500],
                )

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(
                "json parse error",
                error=str(e),
                preview=json_text[:500],
            )
            raise LLMResponseError(
                f"Failed to parse LLM JSON: {e}",
                model=self.model,
                response_preview=json_text[:500],
                cause=e,
            ) from e

        try:
            return ReleaseExtraction.model_validate(data)
        except Exception as e:
            raise LLMResponseError(
                f"Failed to validate extraction schema: {e}",
                model=self.model,
                response_preview=json_text[:500],
                cause=e,
            ) from e

    async def generate_analysis(
        self,
        product: "Product",
        release: "Release",
        extraction: ReleaseExtraction,
        normalized_doc: "NormalizedDoc",
        supplemental: list[str] | None = None,
    ) -> tuple[str, str]:
        """Stage B: generate full expert analysis report.

        Args:
            product: Product configuration.
            release: Release metadata.
            extraction: Structured extraction from Stage A.
            normalized_doc: Normalized source document.
            supplemental: Optional supplemental content.

        Returns:
            Tuple of (report_content_markdown, prompt_version).
        """
        prompt = make_analysis_prompt(product, release, extraction, normalized_doc, supplemental)
        content = self._call(
            [{"role": "user", "content": prompt}],
            max_tokens=8192,
            operation="analyze",
        )
        return content, PROMPT_VERSION

    async def generate_digest(
        self,
        products_info: list[dict[str, Any]],
        time_window: Literal["weekly", "monthly"],
    ) -> tuple[str, str]:
        """Generate a multi-product digest report.

        Args:
            products_info: List of product info dicts.
            time_window: Time window for the digest.

        Returns:
            Tuple of (digest_content_markdown, prompt_version).
        """
        from pia.llm.prompts import make_digest_prompt

        prompt = make_digest_prompt(products_info, time_window)
        content = self._call(
            [{"role": "user", "content": prompt}],
            max_tokens=8192,
            operation="digest",
        )
        return content, PROMPT_VERSION
