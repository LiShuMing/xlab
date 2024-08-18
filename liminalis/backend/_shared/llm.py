"""Unified LLM client.

py-radar (dbradar/summarizer.py), py-invest (agents/orchestrator.py) and
py-ego (app/core/llm_client.py) each ship their own httpx-based OpenAI-
compatible client. M1+ migrates them onto this module so the project has a
single place to set timeouts, retry, model defaults, and rate limiting.

For M0 this module exposes only the call signature future code will share.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.settings import Settings


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class CompletionResponse:
    text: str
    raw: dict[str, Any]


class LLMClient:
    """Async client for OpenAI-compatible chat completions endpoints.

    Implementation lands in M1. The shape is fixed here so callers can be
    written against a stable interface from day one.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is not configured")
        self._settings = settings

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResponse:
        raise NotImplementedError("LLMClient.complete lands in M1 with the radar absorption")
