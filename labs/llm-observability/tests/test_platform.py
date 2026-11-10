from pathlib import Path

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from llm_observe import manager
from llm_observe.exporter import HostCollector, parse_cpu, parse_gpu, parse_vm
from llm_observe.paths import local_origin
from llm_observe.safegit import source_allowed


def test_missing_probe_does_not_become_zero_usage():
    collector = HostCollector()
    collector.probe("ioreg", lambda: parse_gpu("missing"))
    registry = CollectorRegistry()
    registry.register(collector)
    metrics = generate_latest(registry).decode()
    assert 'metal_host_probe_success{probe="ioreg"} 0.0' in metrics
    assert "metal_host_gpu_device_utilization_ratio" not in metrics


def test_vm_uses_actual_page_size():
    result = parse_vm("""Mach Virtual Memory Statistics: (page size of 16384 bytes)
Swapins: 2.
Swapouts: 3.
Pages occupied by compressor: 4.
Pages wired down: 5.
Pages free: 6.
""")
    assert result["swapout_bytes_total"] == 3 * 16384
    assert result["compressor_bytes"] == 4 * 16384


def test_cpu_percentages_are_reported_as_fractions():
    metrics = parse_cpu("CPU usage: 12.30% user, 4.50% sys, 83.20% idle")
    assert metrics["cpu_user_ratio"] == pytest.approx(0.123)
    assert metrics["cpu_idle_ratio"] == pytest.approx(0.832)


def test_stop_refuses_reused_pid(monkeypatch):
    monkeypatch.setattr(manager, "identity", lambda _pid: "another process")
    signals = []
    monkeypatch.setattr(manager.os, "kill", lambda *args: signals.append(args))
    with pytest.raises(RuntimeError, match="refusing"):
        manager.halt({"pid": 123, "identity": "original process"})
    assert signals == []


def test_stop_is_idempotent_when_stack_was_not_started(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "STATE", tmp_path / "absent.json")
    monkeypatch.setattr(manager.os, "kill", lambda *_: pytest.fail("Must not signal any process"))
    manager.stop()
    manager.stop()


@pytest.mark.parametrize(
    "origin",
    [
        "https://127.0.0.1:8000",
        "http://user:secret@localhost",
        "http://example.com",
        "http://localhost/path",
    ],
)
def test_model_origin_rejects_remote_or_credentialed_targets(origin):
    with pytest.raises(ValueError):
        local_origin(origin)


@pytest.mark.parametrize(
    "path",
    [
        ".local/opt/source.py",
        "src/vendor/copied.py",
        "config/.env",
        "logs/request.jsonl",
        "src/debug.log",
        "tests/trace.json",
    ],
)
def test_commit_guard_rejects_runtime_or_vendored_content(path):
    assert not source_allowed(Path(path))


def test_commit_guard_keeps_own_source_and_templates():
    assert source_allowed(Path("src/llm_observe/manager.py"))
    assert source_allowed(Path("config/jaeger.yml.in"))
