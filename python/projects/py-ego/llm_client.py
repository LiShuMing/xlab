"""LLM client with retries and structured logging."""
from __future__ import annotations

import logging
from typing import Any

from config import get_openai_client, get_settings
from exceptions import LLMError
from models import ChatMessage

__all__ = ["LLMClient", "chat_completion"]


class LLMClient:
    """OpenAI-compatible LLM client with error handling and logging."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = get_openai_client()
        self._logger = logging.getLogger(__name__)

    def chat_completion(
        self,
        messages: list[dict[str, str] | ChatMessage],
        *,
        temperature: float = 0.8,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request to the LLM."""
        normalized_messages = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                normalized_messages.append(msg.model_dump())
            else:
                normalized_messages.append({
                    "role": msg["role"],
                    "content": self._clean_text(msg["content"]),
                })

        self._logger.debug(
            "LLM request",
            extra={
                "model": self._settings.llm_model,
                "message_count": len(normalized_messages),
            },
        )

        try:
            response = self._client.chat.completions.create(
                model=self._settings.llm_model,
                messages=normalized_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            content = response.choices[0].message.content or ""
            cleaned = self._clean_text(content)

            self._logger.debug(
                "LLM response",
                extra={
                    "model": self._settings.llm_model,
                    "response_length": len(cleaned),
                },
            )

            return cleaned

        except Exception as e:
            self._logger.error(f"LLM API call failed: {e}")
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
        text = "".join(
            char
            for char in text
            if char == "\n" or char == "\t" or (32 <= ord(char) <= 0x10FFFF)
        )
        return text.strip()


def chat_completion(
    messages: list[dict[str, str] | ChatMessage],
    *,
    temperature: float = 0.8,
    max_tokens: int = 2048,
    **kwargs: Any,
) -> str:
    """Convenience function for single chat completion."""
    client = LLMClient()
    return client.chat_completion(messages, temperature=temperature, max_tokens=max_tokens, **kwargs)