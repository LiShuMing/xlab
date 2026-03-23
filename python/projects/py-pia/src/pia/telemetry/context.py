"""Distributed context tracing for observability.

Provides correlation_id and session_id tracking across async boundaries
using contextvars. This enables tracing a single request through multiple
LLM calls and tool executions.
"""

from __future__ import annotations

import contextvars
import uuid
from contextlib import contextmanager
from typing import Generator

# Context variables for request tracing
_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_id", default=None
)
_agent_step: contextvars.ContextVar[int] = contextvars.ContextVar("agent_step", default=0)


def get_correlation_id() -> str | None:
    """Get the current correlation ID."""
    return _correlation_id.get()


def get_session_id() -> str | None:
    """Get the current session ID."""
    return _session_id.get()


def get_agent_step() -> int:
    """Get the current agent step counter."""
    return _agent_step.get()


def increment_agent_step() -> int:
    """Increment and return the agent step counter."""
    current = _agent_step.get()
    new_step = current + 1
    _agent_step.set(new_step)
    return new_step


def reset_agent_step() -> None:
    """Reset the agent step counter to zero."""
    _agent_step.set(0)


@contextmanager
def correlation_context(
    correlation_id: str | None = None,
    session_id: str | None = None,
    reset_step: bool = True,
) -> Generator[None, None, None]:
    """Context manager to set correlation and session IDs.

    Usage:
        with correlation_context():
            # correlation_id and session_id are auto-generated
            result = await analyze_product(...)

        with correlation_context(correlation_id="custom-id", session_id="session-123"):
            # Custom IDs are used
            result = await analyze_product(...)

    Args:
        correlation_id: Optional correlation ID. Auto-generated if not provided.
        session_id: Optional session ID. Auto-generated if not provided.
        reset_step: If True, reset the agent step counter on entry.

    Yields:
        None
    """
    corr_id = correlation_id or str(uuid.uuid4())
    sess_id = session_id or str(uuid.uuid4())

    # Set new values
    corr_token = _correlation_id.set(corr_id)
    sess_token = _session_id.set(sess_id)

    # Handle step counter
    step_token: contextvars.Token[int] | None = None
    if reset_step:
        step_token = _agent_step.set(0)
    else:
        step_token = _agent_step.set(_agent_step.get())

    try:
        yield
    finally:
        # Restore previous values
        _correlation_id.reset(corr_token)
        _session_id.reset(sess_token)
        _agent_step.reset(step_token)


def get_context_dict() -> dict[str, object]:
    """Get current context as a dictionary for logging.

    Returns:
        Dict with correlation_id, session_id, and agent_step (if set).
    """
    result: dict[str, object] = {}
    if corr_id := _correlation_id.get():
        result["correlation_id"] = corr_id
    if sess_id := _session_id.get():
        result["session_id"] = sess_id
    if step := _agent_step.get():
        result["agent_step"] = step
    return result
