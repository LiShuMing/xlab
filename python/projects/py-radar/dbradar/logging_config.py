"""Structured logging configuration for Daily DB Radar.

This module configures structlog for structured logging with context tracing,
as per Harness Engineering standards (RULE.md Rule 2.1, 2.2, 2.3).

Usage:
    from dbradar.logging_config import get_logger, correlation_id

    # Set correlation ID for request tracing
    correlation_id.set("req-123")

    # Use structured logger
    logger = get_logger()
    logger.info("fetch_started", source="rss", url="https://example.com/feed")
    logger.debug("llm_request", model="qwen-max", tokens=1500)
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# Context variable for request correlation ID
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def add_correlation_id(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Add correlation_id from context vars to log event."""
    cid = correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    """Configure structlog for structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, output JSON format. If False, output console format.
    """
    shared_processors: list = [
        # Add timestamp in ISO format
        structlog.processors.TimeStamper(fmt="iso"),
        # Add log level
        structlog.stdlib.add_log_level,
        # Add correlation ID from context
        add_correlation_id,
        # Format positional arguments
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add caller info (file, line, function)
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]

    if json_format:
        # JSON format for production (log aggregation)
        formatter = structlog.processors.JSONRenderer()
    else:
        # Console format for development
        formatter = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [formatter],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class CorrelationIdContext:
    """Context manager for setting correlation ID.

    Usage:
        with CorrelationIdContext("req-123"):
            logger.info("processing_started")
            # All logs within this context include correlation_id
    """

    def __init__(self, cid: str):
        self.cid = cid
        self.token: Any = None

    def __enter__(self) -> "CorrelationIdContext":
        self.token = correlation_id.set(self.cid)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.token:
            correlation_id.reset(self.token)


def set_correlation_id(cid: str) -> Any:
    """Set correlation ID for current context.

    Args:
        cid: Correlation ID string

    Returns:
        Token for resetting (use with correlation_id.reset(token))
    """
    return correlation_id.set(cid)


def get_correlation_id() -> str | None:
    """Get current correlation ID from context."""
    return correlation_id.get()
