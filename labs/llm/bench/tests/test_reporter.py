"""Tests for JSON and HTML reporters."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from llm_benchmark.reporter.json_reporter import (
    build_result_json,
    diff_results,
    save_results,
)
from llm_benchmark.reporter.html_reporter import generate_html_report, save_html_report


class TestBuildResultJSON:
    def test_build_basic(self):
        result = build_result_json(
            benchmark_version="0.1.0",
            model="test-model",
            model_config={"base_url": "https://api.example.com/v1"},
            dataset_name="math",
            dataset_version="latest",
            num_samples=100,
            repeat=3,
            overall_score=0.72,
            metric_scores={"exact_match": 0.68, "numeric_match": 0.76},
            per_repeat=[0.71, 0.72, 0.73],
            std_dev=0.01,
            by_difficulty={"level_1": 0.95, "level_2": 0.88},
            latencies_ms=[150.0, 200.0],
            total_tokens=5000,
        )

        assert result["meta"]["benchmark_version"] == "0.1.0"
        assert result["meta"]["model"] == "test-model"
        assert result["meta"]["dataset"] == "math"
        assert result["meta"]["num_samples"] == 100
        assert result["meta"]["repeat"] == 3
        assert "commit_hash" in result["meta"]
        assert "timestamp" in result["meta"]

        assert result["results"]["overall_score"] == 0.72
        assert result["results"]["std_dev"] == 0.01
        assert result["results"]["per_repeat"] == [0.71, 0.72, 0.73]
        assert result["results"]["by_difficulty"]["level_1"] == 0.95


class TestSaveResults:
    def test_save_and_load(self):
        result = build_result_json(
            benchmark_version="0.1.0",
            model="test-model",
            model_config={},
            dataset_name="math",
            dataset_version="latest",
            num_samples=10,
            repeat=1,
            overall_score=0.5,
            metric_scores={},
            per_repeat=[0.5],
            std_dev=0.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_results(result, Path(tmpdir))
            assert path.exists()
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["meta"]["model"] == "test-model"
            assert loaded["results"]["overall_score"] == 0.5


class TestDiffResults:
    def test_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = build_result_json(
                benchmark_version="0.1.0",
                model="model-a",
                model_config={},
                dataset_name="math",
                dataset_version="latest",
                num_samples=10,
                repeat=1,
                overall_score=0.72,
                metric_scores={"exact_match": 0.72},
                per_repeat=[0.72],
                std_dev=0.0,
            )
            b = build_result_json(
                benchmark_version="0.1.0",
                model="model-b",
                model_config={},
                dataset_name="math",
                dataset_version="latest",
                num_samples=10,
                repeat=1,
                overall_score=0.85,
                metric_scores={"exact_match": 0.85},
                per_repeat=[0.85],
                std_dev=0.0,
            )

            a_path = save_results(a, Path(tmpdir))
            b_path = save_results(b, Path(tmpdir))

            diff = diff_results(a_path, b_path)
            assert diff["model_a"] == "model-a"
            assert diff["model_b"] == "model-b"
            assert diff["scores_a"] == 0.72
            assert diff["scores_b"] == 0.85
            assert diff["diffs"]["overall_score"] == 0.13


class TestHTMLReporter:
    def test_generate_html(self):
        result = build_result_json(
            benchmark_version="0.1.0",
            model="test-model",
            model_config={},
            dataset_name="math",
            dataset_version="latest",
            num_samples=10,
            repeat=3,
            overall_score=0.72,
            metric_scores={"exact_match": 0.68, "numeric_match": 0.76},
            per_repeat=[0.71, 0.72, 0.73],
            std_dev=0.01,
            by_difficulty={"level_1": 0.95, "level_2": 0.88},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_html_report(result, Path(tmpdir) / "report.html")
            assert path.exists()
            content = path.read_text()
            assert "<!doctype html>" in content.lower()
            assert "chart.js" in content.lower()
            assert "test-model" in content
            assert "0.72" in content