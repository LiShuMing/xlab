from __future__ import annotations

import logging

from backend._shared.logging import (
    CorrelationIdContext,
    add_correlation_id,
    configure_logging,
    get_correlation_id,
    reset_logging_for_tests,
)
from backend.settings import Settings


def test_correlation_id_context_adds_log_field() -> None:
    with CorrelationIdContext("req-123"):
        event = add_correlation_id(None, "info", {})

    assert event["correlation_id"] == "req-123"
    assert get_correlation_id() is None


def test_configure_logging_uses_runtime_log_level() -> None:
    reset_logging_for_tests()
    try:
        configure_logging(Settings(log_level="WARNING"))
        assert logging.getLogger().level == logging.WARNING
    finally:
        reset_logging_for_tests()
