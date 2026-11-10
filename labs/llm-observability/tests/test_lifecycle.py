import socket

import pytest

from llm_observe import manager


def test_port_conflict_stops_before_native_validation(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "STATE", tmp_path / "services.json")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        monkeypatch.setattr(manager, "render", lambda *_: {"ports": {"test": port}})
        monkeypatch.setattr(manager, "binaries", lambda: pytest.fail("Must stop before launching"))
        with pytest.raises(RuntimeError, match="occupied"):
            manager.start("http://127.0.0.1:8000", 0)
    assert not manager.STATE.exists()


def test_restart_preflight_accepts_closed_http_connection(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "STATE", tmp_path / "services.json")
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.listen(1)
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            connection, _ = listener.accept()
            connection.close()
            assert client.recv(1) == b""
    monkeypatch.setattr(manager, "render", lambda *_: {"ports": {"test": port}})

    def reached_validation():
        raise RuntimeError("port preflight passed")

    monkeypatch.setattr(manager, "binaries", reached_validation)
    with pytest.raises(RuntimeError, match="port preflight passed"):
        manager.start("http://127.0.0.1:8000", 0)


def test_partial_start_rolls_back_only_new_children(monkeypatch, tmp_path):
    for directory in ("run", "logs", "data"):
        (tmp_path / directory).mkdir()
    monkeypatch.setattr(manager, "LOCAL", tmp_path)
    monkeypatch.setattr(manager, "STATE", tmp_path / "run/services.json")
    monkeypatch.setattr(
        manager, "render", lambda *_: {"model_url": "http://127.0.0.1:8000", "ports": manager.PORTS}
    )
    monkeypatch.setattr(
        manager, "binaries", lambda: {"jaeger": "jaeger", "prometheus": "prometheus"}
    )
    monkeypatch.setattr(manager, "validate", lambda *_: None)
    monkeypatch.setattr(manager, "identity", lambda *_: "owned identity")
    halted = []
    monkeypatch.setattr(manager, "halt", lambda record: halted.append(record["pid"]))

    class Child:
        pid = 12345

        def wait(self, timeout):
            return 0

    calls = []

    def spawn(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise OSError("synthetic process creation failure")
        return Child()

    # No real processes or model endpoints are touched by this transaction test.
    class AvailablePort:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def bind(self, *_):
            pass

        def setsockopt(self, *_):
            pass

    monkeypatch.setattr(manager.socket, "socket", AvailablePort)
    monkeypatch.setattr(manager.subprocess, "Popen", spawn)
    with pytest.raises(OSError, match="synthetic"):
        manager.start("http://127.0.0.1:8000", 0)
    assert halted == [Child.pid]
    assert not manager.STATE.exists()


def test_native_validation_reports_signal_exit(monkeypatch, tmp_path):
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(manager, "LOCAL", tmp_path)

    class Result:
        returncode, stdout, stderr = -9, "", ""

    monkeypatch.setattr(manager.subprocess, "run", lambda *_args, **_kwargs: Result())
    with pytest.raises(RuntimeError, match="exited -9"):
        manager.validate({"promtool": "promtool", "jaeger": "jaeger"})
    assert "returncode=-9" in (tmp_path / "logs/validate-promtool.log").read_text()


def test_shutdown_waits_through_transitional_ps_identity(monkeypatch):
    states = iter(["original", "exiting", None])
    monkeypatch.setattr(manager, "identity", lambda _pid: next(states))
    monkeypatch.setattr(manager.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(manager.time, "sleep", lambda _: None)
    sent = []
    monkeypatch.setattr(manager.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    manager.halt({"pid": 12345, "identity": "original"})
    assert sent == [(12345, manager.signal.SIGTERM)]
