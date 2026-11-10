import json
from argparse import Namespace

import pytest

from llm_observe import model, smoke
from llm_observe.vllm_launch import validate_arguments


def test_saved_profile_reuses_arguments_and_does_not_store_environment(monkeypatch, tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "python": "/bin/sh",
                "cwd": str(tmp_path),
                "args": ["model", "--max-model-len", "4096"],
                "offline": True,
            }
        )
    )
    monkeypatch.setattr(model, "PROFILE", profile)
    args = Namespace(
        python=None, working_directory=None, serve_args=[], offline=None, instrument=None
    )
    result = model.profile_from_args(args)
    assert result["args"] == ["model", "--max-model-len", "4096"]
    assert result["offline"] is True
    assert set(result) == {"python", "cwd", "args", "offline", "instrument"}


@pytest.mark.parametrize("args", [["model", "--port=1234"], ["model", "--middleware", "other"], []])
def test_model_arguments_cannot_override_tracing_or_origin(args):
    with pytest.raises(ValueError):
        validate_arguments(args)


def test_busy_model_is_not_signalled(monkeypatch):
    monkeypatch.setattr(
        model.manager,
        "get",
        lambda _: b"vllm:num_requests_running 1\nvllm:num_requests_waiting 0\n",
    )
    with pytest.raises(RuntimeError, match="busy"):
        model.require_idle("http://127.0.0.1:8000")


def test_missing_idle_metrics_is_not_treated_as_idle(monkeypatch):
    monkeypatch.setattr(model.manager, "get", lambda _: b"unrelated 0\n")
    with pytest.raises(RuntimeError, match="missing"):
        model.require_idle("http://127.0.0.1:8000")


def test_model_pid_reuse_refuses_signal(monkeypatch):
    monkeypatch.setattr(model, "snapshot", lambda pid: {"pid": pid, "identity": "new", "pgid": pid})
    signals = []
    monkeypatch.setattr(model.os, "kill", lambda *args: signals.append(args))
    with pytest.raises(RuntimeError, match="identity changed"):
        model.terminate([{"pid": 1234, "identity": "old", "pgid": 1234}], 1234)
    assert not signals


def test_trace_query_waits_for_server_export_without_regenerating(monkeypatch):
    results = iter(
        [
            {"data": [{"spans": [{"operationName": "client.request"}]}]},
            {
                "data": [
                    {
                        "spans": [
                            {"operationName": "client.request"},
                            {"operationName": "http.server"},
                        ]
                    }
                ]
            },
        ]
    )
    monkeypatch.setattr(smoke, "get", lambda _: json.dumps(next(results)).encode())
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)
    trace = smoke.query_trace(17686, "example", required_names={"client.request", "http.server"})
    assert len(trace["data"][0]["spans"]) == 2
