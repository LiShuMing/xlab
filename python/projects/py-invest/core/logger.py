"""Logging system based on structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import Processor


def get_logger(name: str = "invest-ai") -> structlog.BoundLogger:
    """Get structured logger instance.

    Args:
        name: Logger name, typically the module name.

    Returns:
        Configured BoundLogger instance.
    """
    return structlog.get_logger(name)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging system.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
    """
    # Standard library logging setup
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # structlog configuration
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.dev.ConsoleRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
