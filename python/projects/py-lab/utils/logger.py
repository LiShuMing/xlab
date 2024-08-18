"""
Structured logging utility for the AI Lab Platform.

Uses structlog for structured JSON logging with context tracing support.
Provides correlation_id and session_id tracking across async boundaries.
"""

import contextvars
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import structlog
from structlog.stdlib import BoundLogger

from config.settings import LOGS_DIR, settings

# Context variables for tracing
CORRELATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
SESSION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_id", default=None
)
AGENT_STEP: contextvars.ContextVar[int] = contextvars.ContextVar(
    "agent_step", default=0
)


def get_correlation_id() -> str | None:
    """Get current correlation ID from context."""
    return CORRELATION_ID.get()


def get_session_id() -> str | None:
    """Get current session ID from context."""
    return SESSION_ID.get()


def set_correlation_id(correlation_id: str | None) -> None:
    """Set correlation ID in context."""
    CORRELATION_ID.set(correlation_id)


def set_session_id(session_id: str | None) -> None:
    """Set session ID in context."""
    SESSION_ID.set(session_id)


def increment_agent_step() -> int:
    """Increment and return current agent step."""
    current = AGENT_STEP.get()
    AGENT_STEP.set(current + 1)
    return current + 1


def reset_agent_step() -> None:
    """Reset agent step counter."""
    AGENT_STEP.set(0)


class ContextTraceProcessor:
    """
    Structlog processor that injects context variables into log entries.
    """
    
    def __call__(
        self,
        logger: structlog.types.WrappedLogger,
        method_name: str,
        event_dict: structlog.types.EventDict
    ) -> structlog.types.EventDict:
        """Add context variables to event dict."""
        correlation_id = get_correlation_id()
        session_id = get_session_id()
        agent_step = AGENT_STEP.get()
        
        if correlation_id:
            event_dict["correlation_id"] = correlation_id
        if session_id:
            event_dict["session_id"] = session_id
        if agent_step > 0:
            event_dict["agent_step"] = agent_step
            
        return event_dict


def _get_log_file_path() -> Path:
    """Generate log file path with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d")
    return LOGS_DIR / f"ai_lab_{timestamp}.log"


def configure_logging() -> None:
    """
    Configure structlog and stdlib logging.
    
    This should be called once at application startup.
    """
    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )
    
    # Configure structlog
    shared_processors: list[structlog.types.Processor] = [
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add context tracing
        ContextTraceProcessor(),
        # Format positional arguments
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add caller info
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        # Filter by level
        structlog.stdlib.filter_by_level,
    ]
    
    # File processors (JSON format)
    file_processors = shared_processors + [
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
    
    # Console processors (pretty format)
    console_processors = shared_processors + [
        structlog.dev.ConsoleRenderer(colors=True, pad_event=25),
    ]
    
    # Configure handlers
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]
    
    if settings.log_to_file:
        file_handler = logging.FileHandler(
            _get_log_file_path(),
            encoding="utf-8",
            mode="a"
        )
        handlers.append(file_handler)
    
    # Configure structlog
    structlog.configure(
        processors=console_processors,  # Default to console for structlog
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Store file processors for file handler
    if settings.log_to_file:
        # Create JSON formatter for file handler
        json_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
        handlers[-1].setFormatter(json_formatter)


def get_logger(name: str) -> BoundLogger:
    """
    Get a configured structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured BoundLogger instance with structured logging support
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("event_happened", key="value", count=42)
        {"event": "event_happened", "key": "value", "count": 42, ...}
    """
    return cast(BoundLogger, structlog.get_logger(name))


# Convenience function for LLM tracing
def trace_llm_call(
    logger: BoundLogger,
    provider: str,
    model: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    latency_ms: float | None = None,
    **extra: Any
) -> None:
    """
    Log LLM call metrics for observability.
    
    Args:
        logger: Logger instance
        provider: LLM provider name
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        latency_ms: Call latency in milliseconds
        **extra: Additional fields to log
    """
    log_data = {
        "event": "llm_call",
        "provider": provider,
        "model": model,
        **extra,
    }
    
    if prompt_tokens is not None:
        log_data["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        log_data["completion_tokens"] = completion_tokens
    if latency_ms is not None:
        log_data["latency_ms"] = round(latency_ms, 2)
        
    logger.debug(**log_data)


def trace_llm_io(
    logger: BoundLogger,
    direction: str,
    payload: dict[str, Any],
    level: str = "debug"
) -> None:
    """
    Log LLM input/output for debugging hallucinations.
    
    Args:
        logger: Logger instance
        direction: "input" or "output"
        payload: The payload to log
        level: Log level (debug, info)
    """
    if not settings.enable_llm_tracing:
        return
        
    log_method = getattr(logger, level)
    log_method(
        f"llm_{direction}",
        direction=direction,
        payload=payload,
    )
