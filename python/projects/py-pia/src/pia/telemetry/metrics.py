"""Metrics collection for LLM calls and tool executions.

Simple timing metrics that integrate with structlog for observability.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TypeVar

import structlog

from pia.telemetry.context import get_context_dict

logger = structlog.get_logger()

T = TypeVar("T")


@dataclass
class LLMCallMetrics:
    """Metrics for a single LLM call."""

    model: str
    operation: str  # e.g., "extract", "analyze", "digest"
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    success: bool = True
    error_type: str | None = None
    correlation_id: str | None = field(default_factory=lambda: get_context_dict().get("correlation_id"))  # type: ignore[misc]
    session_id: str | None = field(default_factory=lambda: get_context_dict().get("session_id"))  # type: ignore[misc]

    def log(self) -> None:
        """Log metrics as a structured event."""
        log_data = {
            "event": "llm_call_metrics",
            "model": self.model,
            "operation": self.operation,
            "latency_ms": round(self.latency_ms, 2),
            "success": self.success,
        }
        if self.input_tokens is not None:
            log_data["input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            log_data["output_tokens"] = self.output_tokens
        if self.error_type:
            log_data["error_type"] = self.error_type
        if self.correlation_id:
            log_data["correlation_id"] = self.correlation_id
        if self.session_id:
            log_data["session_id"] = self.session_id

        if self.success:
            logger.info("LLM call completed", **log_data)
        else:
            logger.error("LLM call failed", **log_data)


@dataclass
class ToolExecutionMetrics:
    """Metrics for tool/function execution."""

    tool_name: str
    latency_ms: float
    success: bool = True
    error_type: str | None = None
    correlation_id: str | None = field(default_factory=lambda: get_context_dict().get("correlation_id"))  # type: ignore[misc]

    def log(self) -> None:
        """Log metrics as a structured event."""
        log_data = {
            "event": "tool_execution_metrics",
            "tool_name": self.tool_name,
            "latency_ms": round(self.latency_ms, 2),
            "success": self.success,
        }
        if self.error_type:
            log_data["error_type"] = self.error_type
        if self.correlation_id:
            log_data["correlation_id"] = self.correlation_id

        if self.success:
            logger.debug("Tool execution completed", **log_data)
        else:
            logger.error("Tool execution failed", **log_data)


@contextmanager
def timed_llm_call(
    model: str,
    operation: str,
) -> Callable[[bool, str | None], None]:
    """Context manager for timing LLM calls.

    Usage:
        with timed_llm_call(model="gpt-4o", operation="extract") as record:
            result = await llm.extract(...)
            record(success=True)  # Record successful completion

        with timed_llm_call(model="gpt-4o", operation="extract") as record:
            try:
                result = await llm.extract(...)
                record(success=True)
            except Exception as e:
                record(success=False, error_type=type(e).__name__)
                raise

    Args:
        model: The LLM model name.
        operation: The operation being performed (e.g., "extract", "analyze").

    Yields:
        A callable to record the result.
    """
    start = time.perf_counter()
    metrics: LLMCallMetrics | None = None

    def record_result(success: bool = True, error_type: str | None = None) -> None:
        nonlocal metrics
        latency_ms = (time.perf_counter() - start) * 1000
        metrics = LLMCallMetrics(
            model=model,
            operation=operation,
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
        )
        metrics.log()

    try:
        yield record_result
        # If record_result wasn't called, log with success=True
        if metrics is None:
            record_result(success=True)
    except Exception as e:
        if metrics is None:
            record_result(success=False, error_type=type(e).__name__)
        raise


@contextmanager
def timed_tool_execution(tool_name: str) -> Callable[[bool, str | None], None]:
    """Context manager for timing tool executions.

    Usage:
        with timed_tool_execution("fetch_url") as record:
            result = await fetch_service.fetch_url(...)
            record(success=True)

    Args:
        tool_name: Name of the tool being executed.

    Yields:
        A callable to record the result.
    """
    start = time.perf_counter()
    metrics: ToolExecutionMetrics | None = None

    def record_result(success: bool = True, error_type: str | None = None) -> None:
        nonlocal metrics
        latency_ms = (time.perf_counter() - start) * 1000
        metrics = ToolExecutionMetrics(
            tool_name=tool_name,
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
        )
        metrics.log()

    try:
        yield record_result
        if metrics is None:
            record_result(success=True)
    except Exception as e:
        if metrics is None:
            record_result(success=False, error_type=type(e).__name__)
        raise
