"""Unified OpenAI-compatible LLM client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from backend.settings import Settings


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class CompletionResponse:
    text: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class LLMRuntimeConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout: float = 120.0
    temperature: float = 0.7
    max_tokens: int = 1024
    max_retries: int = 1
    max_concurrency: int = 4

    @classmethod
    def from_settings(cls, settings: Settings) -> LLMRuntimeConfig:
        return cls(
            api_key=settings.llm_api_key or "",
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            max_retries=settings.llm_max_retries,
            max_concurrency=settings.llm_max_concurrency,
        )


class LLMError(RuntimeError):
    """Raised when an upstream LLM request fails."""


def _normalize_config(config: LLMRuntimeConfig | Settings) -> LLMRuntimeConfig:
    if isinstance(config, LLMRuntimeConfig):
        return config
    return LLMRuntimeConfig.from_settings(config)


def _build_payload(
    config: LLMRuntimeConfig,
    messages: list[ChatMessage],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "model": model or config.model,
        "messages": [{"role": message.role, "content": message.content} for message in messages],
        "temperature": config.temperature if temperature is None else temperature,
        "max_tokens": max_tokens or config.max_tokens,
    }
    if extra:
        payload.update({key: value for key, value in extra.items() if value is not None})
    return payload


def _extract_completion_text(raw: dict[str, Any]) -> str:
    try:
        text = raw["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response did not include choices[0].message.content") from exc
    return str(text).strip()


class LLMClient:
    """Async client for OpenAI-compatible chat completions endpoints."""

    def __init__(
        self,
        settings: LLMRuntimeConfig | Settings,
        *,
        client: httpx.AsyncClient | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self._config = _normalize_config(settings)
        self._own_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._config.base_url.rstrip("/"),
            timeout=httpx.Timeout(self._config.timeout),
            headers={"Authorization": f"Bearer {self._config.api_key}"},
        )
        self._semaphore = semaphore or asyncio.Semaphore(max(self._config.max_concurrency, 1))

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra_payload: Any,
    ) -> CompletionResponse:
        payload = _build_payload(
            self._config,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra_payload,
        )
        started_at = perf_counter()
        async with self._semaphore:
            response = await self._request_with_retries(payload)

        raw = response.json()
        text = _extract_completion_text(raw)
        raw.setdefault("_meta", {})["elapsed_seconds"] = round(perf_counter() - started_at, 3)
        return CompletionResponse(text=text, raw=raw)

    async def _request_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        if not self._config.api_key:
            raise LLMError("LLM_API_KEY is not configured")
        attempts = max(self._config.max_retries, 0) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._client.post("/chat/completions", json=payload)
                if response.status_code not in {408, 429, 500, 502, 503, 504}:
                    response.raise_for_status()
                    return response
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                await asyncio.sleep(min(2**attempt, 8))
        raise LLMError(f"LLM request failed after {attempts} attempt(s): {last_error}") from last_error

    async def aclose(self) -> None:
        if self._own_client:
            await self._client.aclose()


class SyncLLMClient:
    """Synchronous OpenAI-compatible client for legacy thread-based callers."""

    def __init__(
        self,
        settings: LLMRuntimeConfig | Settings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = _normalize_config(settings)
        self._own_client = client is None
        self._client = client or httpx.Client(
            base_url=self._config.base_url.rstrip("/"),
            timeout=httpx.Timeout(self._config.timeout),
            headers={"Authorization": f"Bearer {self._config.api_key}"},
        )

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra_payload: Any,
    ) -> CompletionResponse:
        payload = _build_payload(
            self._config,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra_payload,
        )
        started_at = perf_counter()
        response = self._request_with_retries(payload)
        raw = response.json()
        text = _extract_completion_text(raw)
        raw.setdefault("_meta", {})["elapsed_seconds"] = round(perf_counter() - started_at, 3)
        return CompletionResponse(text=text, raw=raw)

    def _request_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        if not self._config.api_key:
            raise LLMError("LLM_API_KEY is not configured")
        attempts = max(self._config.max_retries, 0) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.post("/chat/completions", json=payload)
                if response.status_code not in {408, 429, 500, 502, 503, 504}:
                    response.raise_for_status()
                    return response
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                import time

                time.sleep(min(2**attempt, 8))
        raise LLMError(f"LLM request failed after {attempts} attempt(s): {last_error}") from last_error

    def close(self) -> None:
        if self._own_client:
            self._client.close()


_client: LLMClient | None = None


def get_llm_client(settings: Settings) -> LLMClient:
    """Return the process-wide shared LLM client."""
    global _client
    if _client is None:
        _client = LLMClient(settings)
    return _client


async def dispose_llm_client() -> None:
    """Close the process-wide shared LLM client."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
