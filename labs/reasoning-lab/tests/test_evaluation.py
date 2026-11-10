import json
from dataclasses import replace

import pytest

from reasoning_lab.config import Config
from reasoning_lab.data import write_json, write_jsonl
from reasoning_lab.evaluation import compare, summarize
from reasoning_lab.report import render
from reasoning_lab.runtime import Monitor


def test_question_cluster_comparison_and_budget_mismatch(tmp_path):
    protocol = {
        "backend": "pytorch",
        "dtype": "float32",
        "temperature": 0.7,
        "samples_per_question": 4,
    }
    for name, correct in [("old", False), ("new", True)]:
        directory = tmp_path / name
        directory.mkdir()
        rows = [
            {"task_id": str(i), "candidate": j, "seed": j, "correct": correct}
            for i in range(20)
            for j in range(4)
        ]
        write_jsonl(directory / "responses.jsonl", rows)
        write_json(
            directory / "summary.json",
            {"complete": True, "protocol": protocol, "seconds": 1, "generated_tokens": 80},
        )
    result = compare(tmp_path / "old", tmp_path / "new", tmp_path / "comparison.json")
    assert result["questions"] == 20
    assert result["delta"] == 1 and result["paired_95_ci"] == [1, 1]
    assert result["decision"] == "accept"
    report = json.loads((tmp_path / "new" / "summary.json").read_text())
    report["protocol"]["samples_per_question"] = 1
    write_json(tmp_path / "new" / "summary.json", report)
    with pytest.raises(ValueError, match="identical protocols"):
        compare(tmp_path / "old", tmp_path / "new", tmp_path / "bad.json")


def test_partial_evaluation_is_explicit():
    result = summarize([], expected=8)
    assert not result["complete"] and result["single_success_rate"] is None


def test_training_cannot_select_on_test_or_ood():
    for split in ["test", "ood"]:
        with pytest.raises(ValueError, match="checkpoint selection"):
            replace(Config(), stage="sft", split=split).validate()
    with pytest.raises(TypeError):
        Config(unknown_parameter=True)


def test_monitor_trace_and_report_escapes_model_output(tmp_path):
    with Monitor(tmp_path / "system.jsonl", "cpu", interval=0.01) as monitor:
        with monitor.phase("test", {}):
            pass
    trace = json.loads((tmp_path / "trace.json").read_text())
    assert len(trace["traceEvents"]) == 1
    assert trace["traceEvents"][0]["dur"] >= 0
    write_jsonl(tmp_path / "responses.jsonl", [{"output": "<script>alert(1)</script>"}])
    result = render(tmp_path).read_text()
    assert "<script>alert(1)</script>" not in result and "&lt;script&gt;" in result
