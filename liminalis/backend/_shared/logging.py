"""Structured logging for liminalis.

Replaces backend.app's stdlib logging.basicConfig setup. Once M1 lands, the
existing TraceFilter/exception handler will be wired through structlog
processors so every log line carries the same trace_id contextvar.
"""

from __future__ import annotations

import logging
import sys

import structlog

from backend.settings import Settings

_configured = False


def configure_logging(settings: Settings) -> None:
    """Idempotent setup. Called from app startup and from CLI entry points."""
    global _configured
    if _configured:
        return
    _configured = True

    log_level = logging.INFO if settings.is_production else logging.DEBUG
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging (uvicorn / sqlalchemy / arq) into structlog format.
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processor=renderer,
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
