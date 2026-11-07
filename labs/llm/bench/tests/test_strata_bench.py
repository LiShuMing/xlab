"""Regression tests for audited Strata evaluation and strict answer scoring."""

import json

import httpx
import pytest
from click.testing import CliRunner

from llm_benchmark.api.client import LLMClient
from llm_benchmark.cli import main
from llm_benchmark.config import ModelConfig
from llm_benchmark.metrics.code_metrics import compute_pass_at_k_scores, pass_at_k
from llm_benchmark.metrics.math_metrics import final_answer, gsm8k_score, math_score
from llm_benchmark.strata_bench import evaluate, load_data, make_report, select_indices


@pytest.mark.parametrize(
    "prediction,reference,score",
    [
        ("12 apples initially; #### 6", "12", 0),
        ("12 initially.\n#### 6", "6", 1),
        ("#### 9\nCorrection: #### 10", "10", 1),
        ("#### 1,234", "1234", 1),
        ("#### -3", "-3", 1),
        ("#### 42.0", "42", 1),
        ("42", "42", 1),
        ("The answer might be 42", "42", 0),
        ("####", "0", 0),
        ("#### NaN", "0", 0),
        ("#### 41.99999999", "42", 0),
        ("#### 42 or 43", "42", 0),
    ],
)
def test_strict_score(prediction, reference, score):
    assert gsm8k_score(prediction, reference) == score


def test_legacy_metric_no_intermediate_or_symbolic_false_positive():
    assert math_score("Started with 12; final answer is 6", "12") == 0
    assert math_score("\\boxed{3x + 5}", "4x + 5") == 0
    assert final_answer("\\boxed{1}, corrected to \\boxed{2}") == "2"


def test_pass_k_never_invents_unavailable_samples():
    with pytest.raises(ValueError):
        pass_at_k(1, 1, 5)
    assert compute_pass_at_k_scores([[True], [True, False]], [1, 5]) == {1: 0.75}


def test_selection_is_reproducible_and_references_not_in_prompt(tmp_path):
    assert select_indices(1319, 8, 42) == [1309, 228, 51, 563, 501, 457, 285, 209]
    data = tmp_path / "data.jsonl"
    data.write_text(json.dumps({"question": "1+1?", "answer": "work #### 2"}) + "\n")
    rows, provenance = load_data(tmp_path, data)
    assert rows[0]["question"] == "1+1?"
    assert provenance["population"] == 1
    assert len(provenance["sha256"]) == 64
    with pytest.raises(ValueError):
        select_indices(1, 2, 42)


@pytest.mark.asyncio
async def test_keyless_payload_and_truncation_recorded(httpx_mock, tmp_path):
    base = "http://127.0.0.1:8080/v1"
    httpx_mock.add_response(url=base + "/models", json={"data": [{"id": "local"}]})
    httpx_mock.add_response(
        url=base + "/chat/completions",
        json={
            "choices": [
                {
                    "message": {"content": "#### 2", "reasoning_content": "reason"},
                    "finish_reason": "length",
                }
            ],
            "usage": {"total_tokens": 20, "prompt_tokens": 10, "completion_tokens": 10},
            "timings": {"predicted_per_second": 20},
        },
    )
    config = ModelConfig(
        name="local",
        base_url=base,
        api_key="",
        max_retries=0,
        trust_env=False,
        reasoning_effort="low",
    )
    rows = [{"question": "1+1?", "answer": "#### 2"}]
    details, elapsed = await evaluate(config, rows, [0], 1, tmp_path)
    assert details[0]["score"] == 0
    assert details[0]["reasoning_content"] == "reason"
    req = httpx_mock.get_requests()[-1]
    assert "authorization" not in req.headers
    body = json.loads(req.content)
    assert body["reasoning_effort"] == "low"
    assert "#### 2" not in body["messages"][0]["content"]
    report = make_report(config, {"sha256": "test"}, [0], 1, details, elapsed)
    assert report["meta"]["completed"] is True
    assert report["results"]["truncated"] == 1
    assert report["results"]["overall_score"] == 0
    assert "api_key" not in report["meta"]["model_config"]


@pytest.mark.asyncio
async def test_ambiguous_timeout_is_not_retried_or_queued(httpx_mock, tmp_path):
    base = "http://127.0.0.1:8080/v1"
    httpx_mock.add_response(url=base + "/models", json={"data": [{"id": "local"}]})
    httpx_mock.add_exception(httpx.ReadTimeout("late"), url=base + "/chat/completions")
    config = ModelConfig(name="local", base_url=base, max_retries=0, trust_env=False)
    rows = [{"question": "1+1?", "answer": "#### 2"}] * 2
    details, elapsed = await evaluate(config, rows, [0, 1], 1, tmp_path)
    assert len(details) == 1 and "error" in details[0]
    assert len(httpx_mock.get_requests()) == 2
    assert (tmp_path / "samples.jsonl").read_text()
    report = make_report(config, {"sha256": "test"}, [0, 1], 1, details, elapsed)
    assert report["meta"]["completed"] is False
    assert report["results"]["transport_errors"] == 1


@pytest.mark.asyncio
async def test_local_client_proxy_is_disabled():
    client = LLMClient(ModelConfig(name="local", trust_env=False))
    try:
        http = await client._ensure_client()
        assert http._trust_env is False
    finally:
        await client.close()


def test_strata_cli_rejects_empty_sample_count():
    result = CliRunner().invoke(main, ["strata", "--max-samples", "0"])
    assert result.exit_code != 0
