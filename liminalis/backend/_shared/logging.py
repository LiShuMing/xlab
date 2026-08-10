"""Structured logging for liminalis."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from backend.settings import Settings

_configured = False
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def add_correlation_id(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach the current correlation ID to structured log events."""
    cid = correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def _resolve_log_level(settings: Settings, *, override: str | None = None) -> int:
    level_name = (override or settings.log_level).upper()
    return getattr(logging, level_name)


def configure_logging(
    settings: Settings, *, log_level: str | None = None, json_format: bool | None = None
) -> None:
    """Idempotent setup. Called from app startup and from CLI entry points."""
    global _configured
    if _configured:
        return
    _configured = True

    resolved_level = _resolve_log_level(settings, override=log_level)
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        add_correlation_id,
        structlog.processors.StackInfoRenderer(),
    ]

    render_json = settings.is_production if json_format is None else json_format
    if render_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
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
    root.setLevel(resolved_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


class CorrelationIdContext:
    """Context manager for binding a correlation ID to logs."""

    def __init__(self, cid: str):
        self.cid = cid
        self.token: Any = None

    def __enter__(self) -> CorrelationIdContext:
        self.token = correlation_id.set(self.cid)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.token:
            correlation_id.reset(self.token)


def set_correlation_id(cid: str) -> Any:
    return correlation_id.set(cid)


def get_correlation_id() -> str | None:
    return correlation_id.get()


def reset_logging_for_tests() -> None:
    """Reset idempotence for tests that need to reconfigure logging."""
    global _configured
    _configured = False
