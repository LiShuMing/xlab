"""Custom exceptions for paper-agent.

All exceptions follow a hierarchy for easy catching:
    PaperAgentError (base)
        ├── ConfigurationError
        ├── ParseError
        ├── LLMError
        │       ├── LLMTimeoutError
        │       ├── LLMRateLimitError
        │       └── LLMResponseError
        ├── ValidationError
        └── StateError
"""

from __future__ import annotations

from typing import Any


class PaperAgentError(Exception):
    """Base exception for all paper-agent errors."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:  # type: ignore[explicit-override]
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigurationError(PaperAgentError):
    """Raised when there's a configuration error."""

    pass


class ParseError(PaperAgentError):
    """Raised when PDF parsing fails."""

    pass


class LLMError(PaperAgentError):
    """Base exception for LLM-related errors."""

    def __init__(
        self,
        message: str,
        *,
        model: str | None = None,
        prompt_length: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.model = model
        self.prompt_length = prompt_length


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: float,
        model: str | None = None,
        prompt_length: int | None = None,
    ) -> None:
        super().__init__(message, model=model, prompt_length=prompt_length)
        self.timeout_seconds = timeout_seconds


class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is hit."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: int | None = None,
        model: str | None = None,
        prompt_length: int | None = None,
    ) -> None:
        super().__init__(message, model=model, prompt_length=prompt_length)
        self.retry_after = retry_after


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or cannot be parsed."""

    def __init__(
        self,
        message: str,
        *,
        raw_response: str | None = None,
        model: str | None = None,
        prompt_length: int | None = None,
    ) -> None:
        super().__init__(message, model=model, prompt_length=prompt_length)
        self.raw_response = raw_response


class ValidationError(PaperAgentError):
    """Raised when data validation fails."""

    pass


class StateError(PaperAgentError):
    """Raised when pipeline state is invalid."""

    pass
