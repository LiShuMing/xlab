"""Structured logging with context tracing for observability."""

from __future__ import annotations

import contextvars
import functools
import logging
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from structlog.typing import EventDict, WrappedLogger

# Context variables for distributed tracing
CORRELATION_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)
SESSION_ID: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")
AGENT_STEP: contextvars.ContextVar[str] = contextvars.ContextVar("agent_step", default="")
DOCUMENT_ID: contextvars.ContextVar[str] = contextvars.ContextVar("document_id", default="")

F = TypeVar("F", bound=Callable[..., Any])


def configure_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure structlog for the application.

    Args:
        verbose: Enable INFO level logging
        debug: Enable DEBUG level logging
    """
    level = logging.WARNING
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            _add_context_vars,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with the given name."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def _add_context_vars(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add context variables to the event dict."""
    corr_id = CORRELATION_ID.get()
    if corr_id:
        event_dict["correlation_id"] = corr_id
    session_id = SESSION_ID.get()
    if session_id:
        event_dict["session_id"] = session_id
    agent_step = AGENT_STEP.get()
    if agent_step:
        event_dict["agent_step"] = agent_step
    doc_id = DOCUMENT_ID.get()
    if doc_id:
        event_dict["document_id"] = doc_id
    return event_dict


def set_correlation_id(corr_id: str | None = None) -> str:
    """Set the correlation ID for the current context.

    Args:
        corr_id: Optional correlation ID, auto-generated if not provided

    Returns:
        The correlation ID
    """
    cid = corr_id or _generate_id()
    CORRELATION_ID.set(cid)
    return cid


def set_session_id(session_id: str | None = None) -> str:
    """Set the session ID for the current context.

    Args:
        session_id: Optional session ID, auto-generated if not provided

    Returns:
        The session ID
    """
    sid = session_id or _generate_id()
    SESSION_ID.set(sid)
    return sid


def set_agent_step(step: str) -> None:
    """Set the current agent step for the context."""
    AGENT_STEP.set(step)


def set_document_id(doc_id: str) -> None:
    """Set the document ID for the current context."""
    DOCUMENT_ID.set(doc_id)


def clear_context() -> None:
    """Clear all context variables."""
    CORRELATION_ID.set("")
    SESSION_ID.set("")
    AGENT_STEP.set("")
    DOCUMENT_ID.set("")


def _generate_id() -> str:
    """Generate a short unique ID."""
    import uuid

    return str(uuid.uuid4())[:8]


def log_llm_request(
    logger: structlog.stdlib.BoundLogger,
    model: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> None:
    """Log LLM request payload at DEBUG level.

    This is non-negotiable for debugging hallucinations.

    Args:
        logger: The logger instance
        model: The model name
        messages: The messages payload
        **kwargs: Additional parameters (temperature, max_tokens, etc.)
    """
    logger.debug(
        "llm_request_payload",
        model=model,
        message_count=len(messages),
        total_chars=sum(len(m.get("content", "")) for m in messages),
        **kwargs,
    )


def log_llm_response(
    logger: structlog.stdlib.BoundLogger,
    model: str,
    response: str,
    latency_ms: float,
    **kwargs: Any,
) -> None:
    """Log LLM response at DEBUG level.

    Args:
        logger: The logger instance
        model: The model name
        response: The raw response text
        latency_ms: Response latency in milliseconds
        **kwargs: Additional metadata
    """
    logger.debug(
        "llm_response_received",
        model=model,
        response_length=len(response),
        latency_ms=round(latency_ms, 2),
        **kwargs,
    )


def timed(
    operation: str,
) -> Callable[[F], F]:
    """Decorator to time and log function execution.

    Args:
        operation: Name of the operation being timed

    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(func.__module__)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                logger.debug(
                    "operation_timed",
                    operation=operation,
                    function=func.__name__,
                    elapsed_ms=round(elapsed, 2),
                )
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                logger.warning(
                    "operation_failed",
                    operation=operation,
                    function=func.__name__,
                    elapsed_ms=round(elapsed, 2),
                    error=type(e).__name__,
                )
                raise
        return wrapper  # type: ignore[return-value]
    return decorator


class ContextFilter(logging.Filter):
    """Standard logging filter that injects context variables."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[explicit-override]
        """Add context variables to the log record."""
        record.correlation_id = CORRELATION_ID.get()
        record.session_id = SESSION_ID.get()
        record.agent_step = AGENT_STEP.get()
        record.document_id = DOCUMENT_ID.get()
        return True
