import json
import logging

import pytest

from reasoning_lab.logging import attach_file, configure, detach, duration, get_logger, parse_level
from reasoning_lab.runtime import Monitor


def test_level_parsing_rejects_unknown_names():
    assert parse_level("debug") == logging.DEBUG
    with pytest.raises(ValueError, match="Unknown log level"):
        parse_level("chatty")


def test_configure_is_idempotent_and_detach_removes_file_handler(tmp_path, monkeypatch):
    monkeypatch.delenv("REASONING_LAB_LOG_LEVEL", raising=False)
    logger = configure()
    configure()
    assert len([h for h in logger.handlers if type(h) is logging.StreamHandler]) == 1
    handler = attach_file(tmp_path / "run.log")
    get_logger("test").info("measured %.2f", 1.5)
    detach(handler)
    assert handler not in logger.handlers
    assert "measured 1.50" in (tmp_path / "run.log").read_text()


def test_monitor_event_is_an_instant_marker_inside_its_phase(tmp_path):
    with Monitor(tmp_path / "system.jsonl", "cpu", interval=0.01) as monitor:
        with monitor.phase("work", {}, step=3):
            monitor.event("stop", reason="paging_slowdown")
    events = json.loads((tmp_path / "trace.json").read_text())["traceEvents"]
    spans = [event for event in events if event["ph"] == "X"]
    markers = [event for event in events if event["ph"] == "i"]
    assert len(spans) == 1 and len(markers) == 1
    assert spans[0]["args"] == {"depth": 0, "step": 3}
    assert markers[0]["args"]["reason"] == "paging_slowdown"
    assert spans[0]["ts"] <= markers[0]["ts"] <= spans[0]["ts"] + spans[0]["dur"]


def test_duration_switches_to_minutes():
    assert duration(1.5) == "1.500s"
    assert duration(3725.0) == "62.1min"
