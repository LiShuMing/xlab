import json

import pytest

from llm_observe import controlled
from llm_observe.investigate import covered_ms, validate
from llm_observe.paths import write_json


def test_host_coverage_clips_crossing_intervals_and_does_not_double_count():
    spans = [
        {"startTime": start, "duration": duration}
        for start, duration in [(0, 15), (12, 10), (30, 50), (90, 5)]
    ]
    assert covered_ms(spans, 10, 40) == 0.022


@pytest.mark.parametrize("warm_mismatch", [False, True])
def test_only_matched_warm_conditions_require_same_output_ids(tmp_path, warm_mismatch):
    counts = {
        "vllm:prefix_cache_hits_total": 32,
        "vllm:prefix_cache_queries_total": 33,
        "vllm:prompt_tokens_total": 33,
        "vllm:generation_tokens_total": 41,
    }
    cases = ["cold"] + ["full", "minimal", "minimal", "full"] * 2 + ["batch4"] * 4
    rows = [
        {
            "case": case,
            "prompt_ids_sha256": "same-input",
            "output_ids_sha256": "warm" if case in {"full", "minimal"} else "other-shape",
            "metric_deltas": counts,
            "max_shared_request_count": 4 if case == "batch4" else 1,
        }
        for case in cases
    ]
    if warm_mismatch:
        rows[2]["output_ids_sha256"] = "different-control-output"
    write_json(tmp_path / "observations.json", rows)
    (tmp_path / "00-metrics-before.txt").write_text("vllm:request_success_total 0\n")
    metrics = "".join(
        f'metal_host_probe_success{{probe="{name}"}} 1\n'
        f'metal_host_probe_last_success_timestamp_seconds{{probe="{name}"}} 100\n'
        for name in ("vm_stat", "ioreg", "process", "system")
    )
    (tmp_path / "host-window.jsonl").write_text(
        json.dumps({"epoch_ns": 101_000_000_000, "metrics": metrics}) + "\n"
    )
    if warm_mismatch:
        with pytest.raises(RuntimeError, match="Matched warm"):
            validate(tmp_path)
    else:
        report = validate(tmp_path)
        assert report["matched_warm_same_output_ids"]
        assert report["cross_condition_output_variants"] == 2


def test_control_rejects_wall_monotonic_divergence(tmp_path, monkeypatch):
    write_json(
        tmp_path / "summary.json",
        {
            "usage": {},
            "output_token_ids": [2],
            "started_ns": 0,
            "first_token_ns": 50_000_000,
            "done_ns": 100_000_000,
        },
    )
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"data": json.dumps({"prompt_token_ids": [1]})}) + "\n"
    )
    spans = [
        {"operationName": name, "tags": [], "duration": 300_000}
        for name in ["client.request", "http.server", "llm_request"]
    ]
    monkeypatch.setattr(
        controlled, "query_trace", lambda *args, **kwargs: {"data": [{"spans": spans}]}
    )
    with pytest.raises(RuntimeError, match="clocks diverged"):
        controlled.timing(
            {"artifact_dir": str(tmp_path), "trace_id": "synthetic"}, "off", 1, 512, 2
        )
    assert (tmp_path / "clock-divergence.json").exists()
