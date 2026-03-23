"""Custom exception hierarchy for pia.

All pia-specific exceptions inherit from PiaError, allowing callers to
catch all pia-related errors with a single except clause.
"""

from __future__ import annotations


class PiaError(Exception):
    """Base exception for all pia errors."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(PiaError):
    """Raised when configuration is invalid or missing."""

    pass


class ProductError(PiaError):
    """Base exception for product-related errors."""

    pass


class ProductNotFoundError(ProductError):
    """Raised when a requested product does not exist."""

    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product '{product_id}' not found.", details={"product_id": product_id})
        self.product_id = product_id


class ProductValidationError(ProductError):
    """Raised when product configuration validation fails."""

    pass


class ReleaseError(PiaError):
    """Base exception for release-related errors."""

    pass


class ReleaseNotFoundError(ReleaseError):
    """Raised when a requested release does not exist."""

    def __init__(self, product_id: str, version: str | None = None) -> None:
        if version:
            msg = f"Release '{version}' not found for product '{product_id}'."
        else:
            msg = f"No releases found for product '{product_id}'."
        super().__init__(msg, details={"product_id": product_id, "version": version})
        self.product_id = product_id
        self.version = version


class ReleaseFetchError(ReleaseError):
    """Raised when fetching releases from a source fails."""

    def __init__(
        self,
        message: str,
        *,
        product_id: str,
        source_type: str,
        source_url: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "product_id": product_id,
                "source_type": source_type,
                "source_url": source_url,
                "cause": str(cause) if cause else None,
            },
        )
        self.product_id = product_id
        self.source_type = source_type
        self.source_url = source_url
        self.__cause__ = cause


class RateLimitError(ReleaseFetchError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, product_id: str, source_type: str, source_url: str) -> None:
        super().__init__(
            f"Rate limit exceeded for {source_type}. "
            "Consider adding authentication tokens to increase limits.",
            product_id=product_id,
            source_type=source_type,
            source_url=source_url,
        )


class LLMError(PiaError):
    """Base exception for LLM-related errors."""

    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM configuration is invalid or missing."""

    pass


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or cannot be parsed."""

    def __init__(
        self,
        message: str,
        *,
        model: str,
        response_preview: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "model": model,
                "response_preview": response_preview,
                "cause": str(cause) if cause else None,
            },
        )
        self.model = model
        self.response_preview = response_preview
        self.__cause__ = cause


class LLMTimeoutError(LLMError):
    """Raised when LLM call times out."""

    def __init__(self, model: str, timeout: float) -> None:
        super().__init__(
            f"LLM call to {model} timed out after {timeout}s.",
            details={"model": model, "timeout": timeout},
        )
        self.model = model
        self.timeout = timeout


class LLMRateLimitError(LLMError):
    """Raised when LLM provider rate limit is hit."""

    def __init__(self, model: str, retry_after: int | None = None) -> None:
        msg = f"Rate limit exceeded for model {model}."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg, details={"model": model, "retry_after": retry_after})
        self.model = model
        self.retry_after = retry_after


class AnalysisError(PiaError):
    """Raised when analysis pipeline fails."""

    pass


class CacheError(PiaError):
    """Raised when cache operations fail."""

    pass
