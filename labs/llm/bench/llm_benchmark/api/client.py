"""OpenAI-compatible API client for LLM evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from llm_benchmark.api.retry import with_retry
from llm_benchmark.config import ModelConfig


@dataclass
class APIResponse:
    """Result of a single API call."""

    text: str
    """The model's response text."""

    token_usage: int
    """Total tokens used (prompt + completion)."""

    latency_ms: float
    """Total request latency in milliseconds."""

    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_content: str = ""
    timings: dict = field(default_factory=dict)


class LLMClient:
    """Async HTTP client for OpenAI-compatible Chat Completions API."""

    def __init__(self, model_config: ModelConfig):
        self._config = model_config
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self._config.api_key:
                headers["Authorization"] = f"Bearer {self._config.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url.rstrip("/"),
                timeout=httpx.Timeout(self._config.timeout),
                trust_env=self._config.trust_env,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
    ) -> APIResponse:
        """Send a chat completion request and return the response.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            model: Override the default model name.
            temperature: Override the default temperature (0 for reproducibility).
            max_tokens: Override the default max tokens.
            seed: Override the default seed (42 for reproducibility).

        Returns:
            APIResponse with text, token usage, and latency.
        """
        client = await self._ensure_client()

        payload = {
            "model": model or self._config.name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._config.temperature,
            "max_tokens": max_tokens or self._config.max_tokens,
            "seed": seed if seed is not None else self._config.seed,
        }
        if self._config.reasoning_effort is not None:
            payload["reasoning_effort"] = self._config.reasoning_effort

        start = time.perf_counter()

        async def _request():
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()

        data = await with_retry(_request, max_retries=self._config.max_retries)
        latency_ms = (time.perf_counter() - start) * 1000

        choice = data["choices"][0]
        text = choice["message"].get("content") or ""
        if not isinstance(text, str):
            raise ValueError("API message.content is not a string")
        usage = data.get("usage", {})
        token_usage = usage.get("total_tokens", 0)

        return APIResponse(
            text=text,
            token_usage=token_usage,
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "unknown"),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            reasoning_content=choice["message"].get("reasoning_content") or "",
            timings=data.get("timings", {}),
        )

    async def models(self) -> dict:
        """Read model metadata without triggering generation."""
        client = await self._ensure_client()
        response = await client.get("/models")
        response.raise_for_status()
        return response.json()
