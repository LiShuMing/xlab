"""LLM client with retries and structured logging."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from backend._shared.llm import ChatMessage as SharedChatMessage
from backend._shared.llm import LLMError as SharedLLMError
from backend._shared.llm import SyncLLMClient
from backend.ego.config import get_settings
from backend.ego.exceptions import LLMError
from backend.ego.models import ChatMessage
from backend.settings import get_settings as get_runtime_settings

__all__ = ["LLMClient"]


class LLMClient:
    """OpenAI-compatible LLM client with error handling and logging."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._runtime_settings = get_runtime_settings()
        self._client = SyncLLMClient(self._runtime_settings)
        self._logger = logging.getLogger(__name__)

    def chat_completion(
        self,
        messages: list[dict[str, str] | ChatMessage],
        *,
        temperature: float = 0.8,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request to the LLM."""
        normalized_messages: list[SharedChatMessage] = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                payload = msg.model_dump()
                normalized_messages.append(
                    SharedChatMessage(role=payload["role"], content=self._clean_text(payload["content"]))
                )
            else:
                normalized_messages.append(
                    SharedChatMessage(role=msg["role"], content=self._clean_text(msg["content"]))
                )

        token_limit = max_tokens if max_tokens is not None else self._runtime_settings.llm_max_tokens
        started_at = perf_counter()

        self._logger.debug(
            "LLM request",
            extra={
                "model": self._runtime_settings.llm_model,
                "message_count": len(normalized_messages),
                "max_tokens": token_limit,
            },
        )

        try:
            response = self._client.complete(
                normalized_messages,
                model=self._runtime_settings.llm_model,
                temperature=temperature,
                max_tokens=token_limit,
                **kwargs,
            )
            cleaned = self._clean_text(response.text)

            self._logger.debug(
                "LLM response",
                extra={
                    "model": self._runtime_settings.llm_model,
                    "response_length": len(cleaned),
                    "elapsed_seconds": round(perf_counter() - started_at, 3),
                },
            )

            return cleaned

        except SharedLLMError as e:
            self._logger.error(
                "LLM API call failed after %.3fs: %s",
                perf_counter() - started_at,
                e,
            )
            raise LLMError(
                f"LLM API call failed: {e}",
                model=self._settings.llm_model,
                cause=e,
            ) from e

    def _clean_text(self, text: Any) -> str:
        if text is None:
            return ""
        text = str(text)
        text = text.encode("utf-8", "ignore").decode("utf-8")
        text = "".join(char for char in text if char == "\n" or char == "\t" or (32 <= ord(char) <= 0x10FFFF))
        return text.strip()
