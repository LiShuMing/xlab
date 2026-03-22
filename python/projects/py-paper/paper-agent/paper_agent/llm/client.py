"""LLM client supporting Anthropic SDK with custom base URL."""

from __future__ import annotations

import os
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Thin wrapper around Anthropic SDK.

    Reads from env vars by default:
      - ANTHROPIC_API_KEY or QWEN_API_KEY
      - ANTHROPIC_BASE_URL or QWEN_BASE_URL
      - ANTHROPIC_MODEL or defaults to qwen3.5-plus
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

        kwargs: dict[str, Any] = {"api_key": resolved_key, "timeout": timeout}
        if resolved_url:
            kwargs["base_url"] = resolved_url

        self._client = anthropic.Anthropic(**kwargs)
        logger.info("llm_client_ready", model=self.model, base_url=resolved_url)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a prompt and return the text response."""
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        logger.debug("llm_request", model=self.model, prompt_len=len(prompt))
        response = self._client.messages.create(**kwargs)

        # Handle ThinkingBlock + TextBlock (qwen3.5 thinking models)
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        logger.debug("llm_response", response_len=len(text))
        return text

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> dict | list:
        """Send a prompt expecting a JSON response. Strips markdown fences."""
        import json, re

        text = self.complete(prompt, system=system, max_tokens=max_tokens)
        # Strip ```json ... ``` fences
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text.strip())
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("json_parse_failed", error=str(e), text_preview=text[:200])
            raise
