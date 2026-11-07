"""Tests for CLI benchmark orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from llm_benchmark import cli


class _FakeDataset:
    name = "fake"

    def load(self):
        pass

    def __len__(self):
        return 1


def test_run_records_repeat_scores(monkeypatch, tmp_path):
    """The persisted report should include scores returned by each repeat."""
    captured = {}
    scores = iter([0.25, 0.75])

    async def fake_run_single(
        ds,
        model_config,
        num_samples,
        run_num,
        total_runs,
        *,
        max_concurrent=None,
    ):
        assert max_concurrent == 4
        return next(scores)

    def fake_save_results(result, output_dir):
        captured["result"] = result
        return Path(output_dir) / "result.json"

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        cli,
        "get_model_config",
        lambda config, model: SimpleNamespace(
            name="test-model",
            base_url="https://api.example.com/v1",
            temperature=0.0,
            seed=42,
        ),
    )
    monkeypatch.setattr(cli, "build_dataset", lambda name, max_samples=None: _FakeDataset())
    monkeypatch.setattr(cli, "_run_single", fake_run_single)
    monkeypatch.setattr(cli, "save_results", fake_save_results)
    monkeypatch.setattr(cli, "save_html_report", lambda result, output: output)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "run",
            "--dataset",
            "gsm8k",
            "--repeat",
            "2",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    saved = captured["result"]["results"]
    assert saved["per_repeat"] == [0.25, 0.75]
    assert saved["overall_score"] == 0.5


def test_compare_models_writes_summary(monkeypatch, tmp_path):
    """compare-models should compare model names on one endpoint config."""
    calls = []

    async def fake_run_single(
        ds,
        model_config,
        num_samples,
        run_num,
        total_runs,
        *,
        max_concurrent=None,
    ):
        calls.append((model_config.name, model_config.base_url, max_concurrent))
        return {"qwen3.7-max": 0.4, "qwen3.8": 0.7}[model_config.name]

    def fake_save_results(result, output_dir):
        return Path(output_dir) / f"{result['meta']['dataset']}_{result['meta']['model']}.json"

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        cli,
        "get_model_config",
        lambda config, model: SimpleNamespace(
            name="qwen3.7-max",
            base_url="https://qwen.example.com/v1",
            api_key="sk-test",
            temperature=0.0,
            seed=42,
            max_tokens=1024,
            max_concurrent=4,
            timeout=30.0,
        ),
    )
    monkeypatch.setattr(cli, "build_dataset", lambda name, max_samples=None: _FakeDataset())
    monkeypatch.setattr(cli, "_run_single", fake_run_single)
    monkeypatch.setattr(cli, "save_results", fake_save_results)
    monkeypatch.setattr(cli, "save_html_report", lambda result, output: output)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "compare-models",
            "--dataset",
            "gsm8k",
            "--models",
            "qwen3.7-max,qwen3.8",
            "--repeat",
            "1",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("qwen3.7-max", "https://qwen.example.com/v1", 4),
        ("qwen3.8", "https://qwen.example.com/v1", 4),
    ]

    summaries = list(tmp_path.glob("comparison_*.json"))
    assert len(summaries) == 1

    import json

    summary = json.loads(summaries[0].read_text())
    row = summary["results"][0]
    assert row["dataset"] == "gsm8k"
    assert row["scores"] == {"qwen3.7-max": 0.4, "qwen3.8": 0.7}
    assert row["delta_vs_baseline"] == {"qwen3.8": 0.3}
    assert row["winner"] == "qwen3.8"


def test_compare_models_records_dataset_load_errors(monkeypatch, tmp_path):
    """A single unavailable HF dataset should not abort the whole comparison."""

    class BrokenDataset:
        def load(self):
            raise RuntimeError("dataset unavailable")

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        cli,
        "get_model_config",
        lambda config, model: SimpleNamespace(
            name="qwen3.7-max",
            base_url="https://qwen.example.com/v1",
            api_key="sk-test",
            temperature=0.0,
            seed=42,
            max_tokens=1024,
            max_concurrent=4,
            timeout=30.0,
        ),
    )
    monkeypatch.setattr(cli, "build_dataset", lambda name, max_samples=None: BrokenDataset())

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "compare-models",
            "--dataset",
            "math",
            "--models",
            "qwen3.7-max,qwen3.8",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0

    import json

    summary = json.loads(next(tmp_path.glob("comparison_*.json")).read_text())
    row = summary["results"][0]
    assert row["dataset"] == "math"
    assert row["num_samples"] == 0
    assert row["scores"] == {"qwen3.7-max": None, "qwen3.8": None}
    assert "dataset unavailable" in row["errors"]["dataset"]


@pytest.mark.asyncio
async def test_run_single_uses_concurrency_limit(monkeypatch):
    """_run_single should run math samples concurrently up to the configured limit."""
    state = SimpleNamespace(active=0, peak=0)

    class FakeResponse:
        text = "answer: 1"

    class FakeClient:
        def __init__(self, model_config):
            pass

        async def chat(self, messages):
            state.active += 1
            state.peak = max(state.peak, state.active)
            await asyncio.sleep(0.01)
            state.active -= 1
            return FakeResponse()

        async def close(self):
            pass

    class FakeMathDataset:
        def __len__(self):
            return 4

        def get_category(self):
            return "math"

        def get_prompt(self, idx):
            return f"problem {idx}"

        def get_reference(self, idx):
            return "1"

    monkeypatch.setattr(cli, "LLMClient", FakeClient)
    monkeypatch.setattr(cli, "math_score", lambda prediction, reference: 1.0)

    score = await cli._run_single(
        FakeMathDataset(),
        SimpleNamespace(max_concurrent=2),
        num_samples=1,
        run_num=1,
        total_runs=1,
    )

    assert score == 1.0
    assert state.peak == 2
