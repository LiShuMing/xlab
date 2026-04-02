"""Circuit breaker implementation for external API calls.

This module implements Harness Engineering Rule 3.3: Circuit Breaker Pattern.
Prevents cascade failures when external services (LLM APIs) are down.
"""

from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import pybreaker
from pybreaker import CircuitBreakerError

from dbradar.config import get_settings
from dbradar.logging_config import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Global circuit breaker instance
_llm_circuit_breaker: Optional[pybreaker.CircuitBreaker] = None


def get_llm_circuit_breaker() -> pybreaker.CircuitBreaker:
    """Get or create the global LLM circuit breaker.

    The circuit breaker state is shared across all LLM calls in the application.
    """
    global _llm_circuit_breaker
    if _llm_circuit_breaker is None:
        settings = get_settings()
        _llm_circuit_breaker = pybreaker.CircuitBreaker(
            fail_max=settings.circuit_breaker_failure_threshold,
            reset_timeout=settings.circuit_breaker_recovery_timeout,
            name="llm_api_circuit_breaker",
        )

        # Add listeners for logging state changes
        _llm_circuit_breaker.add_listener(CircuitBreakerListener())

        logger.debug(
            "circuit_breaker_initialized",
            fail_max=settings.circuit_breaker_failure_threshold,
            reset_timeout=settings.circuit_breaker_recovery_timeout,
        )

    return _llm_circuit_breaker


class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Listener for circuit breaker state changes."""

    def state_change(self, cb: pybreaker.CircuitBreaker, old_state: str, new_state: str) -> None:
        """Log circuit breaker state changes."""
        logger.warning(
            "circuit_breaker_state_changed",
            breaker_name=cb.name,
            old_state=old_state,
            new_state=new_state,
            failure_count=cb.fail_counter,
        )

    def failure(self, cb: pybreaker.CircuitBreaker, exc: Exception) -> None:
        """Log failures."""
        logger.debug(
            "circuit_breaker_failure_recorded",
            breaker_name=cb.name,
            error=str(exc),
            fail_counter=cb.fail_counter,
        )

    def success(self, cb: pybreaker.CircuitBreaker) -> None:
        """Log successful calls (only in debug)."""
        logger.debug(
            "circuit_breaker_success",
            breaker_name=cb.name,
        )


def with_circuit_breaker(func: F) -> F:
    """Decorator to wrap a function with circuit breaker protection.

    Usage:
        @with_circuit_breaker
        def call_llm_api(...) -> dict:
            ...
    """
    breaker = get_llm_circuit_breaker()

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return breaker(func)(*args, **kwargs)
        except CircuitBreakerError as e:
            logger.error(
                "circuit_breaker_open",
                function=func.__name__,
                error="Circuit breaker is OPEN - LLM API calls are blocked",
            )
            raise CircuitBreakerOpenError(
                "LLM API is currently unavailable due to repeated failures. "
                "Please try again later."
            ) from e

    return wrapper  # type: ignore


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open (blocking calls)."""
    pass


def get_circuit_breaker_status() -> dict[str, Any]:
    """Get current circuit breaker status for health checks."""
    breaker = get_llm_circuit_breaker()
    return {
        "name": breaker.name,
        "state": breaker.current_state,
        "failure_count": breaker.fail_counter,
        "fail_max": breaker.fail_max,
        "reset_timeout": breaker.reset_timeout,
    }
