"""Benchmark runner — orchestrates dataset loading, API calls, and evaluation."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from llm_benchmark.api.client import LLMClient
from llm_benchmark.config import BenchmarkConfig, get_model_config
from llm_benchmark.datasets.base import Dataset
from llm_benchmark.metrics.math_metrics import math_score
from llm_benchmark.metrics.code_metrics import compute_pass_at_k_scores
from llm_benchmark.runner.sandbox import CodeSandbox

logger = logging.getLogger(__name__)


@dataclass
class SampleResult:
    """Result for a single sample evaluation."""

    index: int
    prompt: str
    prediction: str
    reference: str
    score: float
    latency_ms: float
    token_usage: int
    metadata: dict = field(default_factory=dict)


@dataclass
class BenchmarkResults:
    """Aggregated results from a benchmark run."""

    dataset_name: str
    model_name: str
    category: str
    overall_score: float
    num_samples: int
    total_latency_ms: float
    total_tokens: int
    per_repeat: list[float] = field(default_factory=list)
    std_dev: float = 0.0
    by_difficulty: dict[str, float] = field(default_factory=dict)
    sample_results: list[SampleResult] = field(default_factory=list)


class BenchmarkRunner:
    """Orchestrates the full benchmark pipeline: load → prompt → API → evaluate → report."""

    def __init__(
        self,
        config: BenchmarkConfig,
        dataset: Dataset,
        client: LLMClient,
        sandbox: CodeSandbox | None = None,
        num_samples: int = 1,
    ):
        self._config = config
        self._dataset = dataset
        self._client = client
        self._sandbox = sandbox or CodeSandbox()
        self._num_samples = num_samples

    async def run(self, repeat: int = 1, checkpoint_path: str | None = None) -> BenchmarkResults:
        """Run the benchmark.

        Args:
            repeat: Number of times to repeat the evaluation (for stability).
            checkpoint_path: Optional path to save intermediate results.

        Returns:
            Aggregated BenchmarkResults.
        """
        per_repeat: list[float] = []
        all_sample_results: list[SampleResult] = []

        for r in range(repeat):
            logger.info("Repeat %d/%d for dataset '%s'", r + 1, repeat, self._dataset.name)
            sample_results = await self._run_once()
            score = self._aggregate_score(sample_results)
            per_repeat.append(score)
            all_sample_results.extend(sample_results)

            if checkpoint_path:
                self._save_checkpoint(checkpoint_path, r, score, sample_results)

        overall = sum(per_repeat) / len(per_repeat) if per_repeat else 0.0
        std_dev = 0.0
        if len(per_repeat) > 1:
            mean = overall
            variance = sum((s - mean) ** 2 for s in per_repeat) / len(per_repeat)
            std_dev = variance**0.5

        total_latency = sum(sr.latency_ms for sr in all_sample_results)
        total_tokens = sum(sr.token_usage for sr in all_sample_results)

        by_difficulty = self._compute_by_difficulty(all_sample_results)

        return BenchmarkResults(
            dataset_name=self._dataset.name,
            model_name=self._client._config.name,
            category=self._dataset.get_category(),
            overall_score=overall,
            num_samples=len(self._dataset),
            total_latency_ms=total_latency,
            total_tokens=total_tokens,
            per_repeat=per_repeat,
            std_dev=std_dev,
            by_difficulty=by_difficulty,
            sample_results=all_sample_results,
        )

    async def _run_once(self) -> list[SampleResult]:
        """Run one pass through all dataset samples."""
        results: list[SampleResult] = []
        semaphore = asyncio.Semaphore(self._client._config.max_concurrent)

        async def _eval_one(idx: int) -> SampleResult:
            async with semaphore:
                prompt = self._dataset.get_prompt(idx)
                reference = self._dataset.get_reference(idx)
                metadata = self._dataset.get_metadata(idx)

                api_resp = await self._client.chat(
                    messages=[{"role": "user", "content": prompt}],
                )

                prediction = api_resp.text

                if self._dataset.get_category() == "math":
                    score = math_score(prediction, reference)
                else:
                    # Code: evaluate each sample individually
                    # For code, we evaluate all n samples at the pass@k level
                    # Here we just check if this single sample passes
                    test_cases = self._get_test_cases(idx)
                    if test_cases:
                        passed = _evaluate_code_sample(prediction, test_cases, self._sandbox)
                        score = 1.0 if passed else 0.0
                    else:
                        # Fallback: use exact match
                        score = 1.0 if prediction.strip() == reference.strip() else 0.0

                return SampleResult(
                    index=idx,
                    prompt=prompt,
                    prediction=prediction,
                    reference=reference,
                    score=score,
                    latency_ms=api_resp.latency_ms,
                    token_usage=api_resp.token_usage,
                    metadata=metadata,
                )

        tasks = [_eval_one(i) for i in range(len(self._dataset))]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

        # Sort by index to maintain order
        results.sort(key=lambda r: r.index)
        return results

    def _get_test_cases(self, idx: int) -> list[str]:
        """Get test cases if the dataset supports them."""
        if hasattr(self._dataset, "get_test_cases"):
            return self._dataset.get_test_cases(idx)  # type: ignore[union-attr]
        return []

    def _aggregate_score(self, results: list[SampleResult]) -> float:
        """Aggregate individual sample scores into an overall score."""
        if not results:
            return 0.0
        return sum(r.score for r in results) / len(results)

    def _compute_by_difficulty(self, results: list[SampleResult]) -> dict[str, float]:
        """Compute scores grouped by difficulty level (for math datasets)."""
        groups: dict[str, list[float]] = {}
        for r in results:
            level = r.metadata.get("level", "unknown")
            if isinstance(level, int):
                level = f"Level {level}"
            elif isinstance(level, str) and level.isdigit():
                level = f"Level {int(level)}"
            groups.setdefault(str(level), []).append(r.score)

        return {k: sum(v) / len(v) for k, v in groups.items() if v}

    @staticmethod
    def _save_checkpoint(
        path: str, repeat_idx: int, score: float, results: list[SampleResult],
    ) -> None:
        """Save intermediate results as a checkpoint."""
        checkpoint = {
            "repeat": repeat_idx,
            "score": score,
            "results": [
                {
                    "index": r.index,
                    "score": r.score,
                    "prediction": r.prediction,
                    "reference": r.reference,
                }
                for r in results
            ],
        }
        Path(path).write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False))


def _evaluate_code_sample(code: str, test_cases: list[str], sandbox: CodeSandbox) -> bool:
    """Evaluate a single code sample against its test cases.

    Cleans the code output (strips markdown fences) before running.
    """
    # Strip markdown ```python fences
    clean_code = code.strip()
    if clean_code.startswith("```python"):
        clean_code = clean_code[9:]
    elif clean_code.startswith("```"):
        clean_code = clean_code[3:]
    if clean_code.endswith("```"):
        clean_code = clean_code[:-3]
    clean_code = clean_code.strip()

    from llm_benchmark.metrics.code_metrics import evaluate_solution

    return evaluate_solution(clean_code, test_cases, sandbox)