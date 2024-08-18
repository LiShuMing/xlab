"""Custom exception hierarchy for py-ego application."""


class PyEgoError(Exception):
    """Base exception for all py-ego errors."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class ConfigurationError(PyEgoError):
    """Raised when configuration is invalid or missing."""


class EmbeddingError(PyEgoError):
    """Raised when embedding generation fails."""

    def __init__(
        self,
        message: str,
        *,
        text: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.text = text


class MemoryError(PyEgoError):
    """Raised when memory operations fail."""

    def __init__(
        self,
        message: str,
        *,
        index: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.index = index


class LLMError(PyEgoError):
    """Raised when LLM API calls fail."""

    def __init__(
        self,
        message: str,
        *,
        model: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.model = model