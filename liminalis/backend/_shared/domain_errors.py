"""Domain-level exceptions that keep services independent from FastAPI."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for service-layer business errors."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class DomainValidationError(DomainError):
    """Raised when caller input is invalid for the domain."""

    status_code = 400


class DomainNotFoundError(DomainError):
    """Raised when a requested domain object cannot be found."""

    status_code = 404


class DomainConflictError(DomainError):
    """Raised when a request conflicts with existing domain state."""

    status_code = 409
