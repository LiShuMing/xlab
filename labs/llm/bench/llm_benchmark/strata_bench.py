"""Auditable, sequential GSM8K/HumanEval evaluation of the local Strata API.

HumanEval requires namespace isolation; no ~/.env credentials are read.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import math
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

import click
import httpx

from llm_benchmark import __version__
from llm_benchmark.api.client import LLMClient
from llm_benchmark.config import ModelConfig
from llm_benchmark.isolated_python import IsolatedPython, grade_candidate
from llm_benchmark.metrics.math_metrics import final_answer, gsm8k_score
from llm_benchmark.reporter.html_reporter import save_html_report
from llm_benchmark.reporter.json_reporter import build_result_json, save_results

GSM8K_REVISION = "3101c7d5072418e28b9008a6636bde82a006892c"
GSM8K_SHA256 = "3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14"
HUMANEVAL_REVISION = "6d43fb980f9fee3c892a914eda09951f772ad10d"
HUMANEVAL_SHA256 = "b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef"
HUMANEVAL_URL = (
    "https://raw.githubusercontent.com/openai/human-eval/"
    f"{HUMANEVAL_REVISION}/data/HumanEval.jsonl.gz"
)
GSM8K_URL = (
    "https://raw.githubusercontent.com/openai/grade-school-math/"
    f"{GSM8K_REVISION}/grade_school_math/data/test.jsonl"
)
MODEL = "qwen3.8-flash-next-coder-iq1_m"


def load_data(
    cache_dir: Path,
    data_path: Path | None = None,
    dataset: str = "gsm8k",
) -> tuple[list[dict], dict]:
    """Load immutable-source data, recording its digest even for user-supplied files."""
    revision = GSM8K_REVISION if dataset == "gsm8k" else HUMANEVAL_REVISION
    url = GSM8K_URL if dataset == "gsm8k" else HUMANEVAL_URL
    count = 1319 if dataset == "gsm8k" else 164
    suffix = ".jsonl" if dataset == "gsm8k" else ".jsonl.gz"
    path = data_path or cache_dir / f"{dataset}-{revision}{suffix}"
    if data_path is None and not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        with request.urlopen(url, timeout=60) as response:
            payload = response.read(4_000_001)
        if len(payload) > 4_000_000:
            raise ValueError("Unexpectedly large dataset download")
        rows = parse_data(gzip.decompress(payload) if path.suffix == ".gz" else payload, dataset)
        if len(rows) != count:
            raise ValueError(f"Pinned {dataset} source does not contain {count} questions")
        with path.open("xb") as handle:
            handle.write(payload)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    expected_digest = GSM8K_SHA256 if dataset == "gsm8k" else HUMANEVAL_SHA256
    if data_path is None and digest != expected_digest:
        raise ValueError("Dataset source/cache SHA256 mismatch; preserving the file")
    rows = parse_data(gzip.decompress(payload) if path.suffix == ".gz" else payload, dataset)
    if data_path is None and len(rows) != count:
        raise ValueError(
            "Incomplete/corrupt dataset cache; preserve it and inspect before retrying"
        )
    return rows, {
        "dataset": dataset,
        "source": url if data_path is None else "user-supplied-jsonl",
        "revision": revision if data_path is None else None,
        "sha256": digest,
        "population": len(rows),
    }


def parse_data(payload: bytes, dataset: str = "gsm8k") -> list[dict]:
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Dataset is empty")
    for row in rows:
        if dataset == "humaneval":
            required = ("task_id", "entry_point", "prompt", "canonical_solution", "test")
            if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in required):
                raise ValueError("HumanEval row lacks required fields")
            if not row["entry_point"].isidentifier():
                raise ValueError("Invalid HumanEval entry point")
            continue
        if not isinstance(row, dict) or not isinstance(row.get("question"), str):
            raise ValueError("Dataset row lacks a question string")
        if not isinstance(row.get("answer"), str) or "####" not in row["answer"]:
            raise ValueError("Dataset row lacks a #### reference answer")
        if gsm8k_score(final_answer(row["answer"]), final_answer(row["answer"])) != 1:
            raise ValueError("Reference final answer is not a finite number")
    return rows


def select_indices(population: int, count: int, seed: int) -> list[int]:
    if not 1 <= count <= population:
        raise ValueError(f"max-samples must be between 1 and {population}")
    return random.Random(seed).sample(range(population), count)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)] if ordered else 0.0


async def evaluate(
    config: ModelConfig,
    rows: list[dict],
    indices: list[int],
    repeat: int,
    run_dir: Path,
    dataset: str = "gsm8k",
    sandbox: IsolatedPython | None = None,
) -> tuple[list[dict], float]:
    """Exactly one in-flight POST; append every result before starting the next one."""
    client = LLMClient(config)
    details: list[dict] = []
    started_run = time.monotonic()
    try:
        models = await client.models()
        available = [model.get("id") for model in models.get("data", [])]
        if config.name not in available:
            raise ValueError(f"Requested model is not listed by the endpoint: {config.name}")
        with (run_dir / "samples.jsonl").open("x", encoding="utf-8") as checkpoint:
            for run in range(repeat):
                for position, index in enumerate(indices, 1):
                    row = rows[index]
                    prompt = (
                        (
                            f"Question: {row['question']}\n\n"
                            "Solve the problem. End with the numeric final answer "
                            "on a line: #### number."
                        )
                        if dataset == "gsm8k"
                        else (
                            "Implement this Python function. Return only complete Python code, "
                            "including the function signature and necessary imports, "
                            "without prose or tests.\n\n" + row["prompt"]
                        )
                    )
                    detail = {
                        "index": index,
                        "repeat": run + 1,
                        "question": row["question"] if dataset == "gsm8k" else row["prompt"],
                        "task_id": row.get("task_id", str(index)),
                        "reference": final_answer(row["answer"])
                        if dataset == "gsm8k"
                        else row["canonical_solution"],
                        "score": 0.0,
                    }
                    started = time.monotonic()
                    abort = False
                    try:
                        response = await client.chat(messages=[{"role": "user", "content": prompt}])
                        complete = response.finish_reason == "stop"
                        detail.update(
                            {
                                "prediction": response.text,
                                "reasoning_content": response.reasoning_content,
                                "extracted_answer": final_answer(response.text)
                                if dataset == "gsm8k"
                                else None,
                                "finish_reason": response.finish_reason,
                                "complete": complete,
                                "score": gsm8k_score(response.text, detail["reference"])
                                if complete and dataset == "gsm8k"
                                else 0.0,
                                "latency_ms": response.latency_ms,
                                "total_tokens": response.token_usage,
                                "prompt_tokens": response.prompt_tokens,
                                "completion_tokens": response.completion_tokens,
                                "timings": response.timings,
                            }
                        )
                        if complete and dataset == "humaneval":
                            if sandbox is None:
                                raise RuntimeError("Missing isolated code evaluator")
                            execution_started = time.monotonic()
                            execution = grade_candidate(response.text, row, sandbox)
                            detail["execution"] = execution
                            detail["execution_ms"] = (time.monotonic() - execution_started) * 1000
                            detail["score"] = float(execution["passed"])
                    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
                        detail.update(
                            {
                                "error": str(exc),
                                "complete": False,
                                "latency_ms": (time.monotonic() - started) * 1000,
                            }
                        )
                        abort = (
                            True  # Do not enqueue more work after an ambiguous transport failure.
                        )
                    details.append(detail)
                    checkpoint.write(json.dumps(detail, ensure_ascii=False) + "\n")
                    checkpoint.flush()
                    click.echo(
                        f"repeat={run + 1}/{repeat} item={position}/{len(indices)} id={index} "
                        f"score={detail['score']:.0f} "
                        f"finish={detail.get('finish_reason', 'error')} "
                        f"seconds={detail['latency_ms'] / 1000:.1f}",
                    )
                    if abort:
                        return details, time.monotonic() - started_run
    finally:
        await client.close()
    return details, time.monotonic() - started_run


def make_report(
    config: ModelConfig,
    provenance: dict,
    indices: list[int],
    repeat: int,
    details: list[dict],
    wall_seconds: float,
) -> dict:
    planned = len(indices) * repeat
    finished = len(details) == planned and not any("error" in row for row in details)
    scores = [
        sum(row["score"] for row in details if row["repeat"] == run + 1) / len(indices)
        for run in range(repeat)
    ]
    latencies = [row["latency_ms"] for row in details]
    completion = sum(row.get("completion_tokens", 0) for row in details)
    correct = sum(row["score"] for row in details)
    dataset = provenance.get("dataset", "gsm8k")
    metric = "strict_final_numeric_accuracy" if dataset == "gsm8k" else "pass@1"
    result = build_result_json(
        benchmark_version=__version__,
        model=config.name,
        model_config={
            "base_url": config.base_url,
            "temperature": config.temperature,
            "seed": config.seed,
            "reasoning_effort": config.reasoning_effort,
            "max_tokens": config.max_tokens,
            "timeout": config.timeout,
            "max_concurrent": 1,
            "max_retries": 0,
            "trust_env": False,
        },
        dataset_name=dataset,
        dataset_version=provenance["sha256"],
        num_samples=len(indices),
        repeat=repeat,
        overall_score=correct / planned,
        metric_scores={metric: correct / planned},
        per_repeat=scores,
        std_dev=statistics.stdev(scores) if repeat > 1 else 0,
        details=details,
        latencies_ms=latencies,
        total_tokens=sum(row.get("total_tokens", 0) for row in details),
    )
    result["meta"].update(
        {
            "dataset_provenance": provenance,
            "selected_indices": indices,
            "selection": "random.Random(seed).sample without replacement",
            "completed": finished,
            "planned_requests": planned,
            "attempted_requests": len(details),
            "prompt_protocol": "zero-shot-gsm8k-final-marker-v1"
            if dataset == "gsm8k"
            else "zero-shot-humaneval-full-function-v1",
            "code_execution": "none"
            if dataset == "gsm8k"
            else "bubblewrap namespaces; no network/home; RO runtime; 256MiB/5s CPU/10s wall",
        }
    )
    result["results"].update(
        {
            "correct": int(correct),
            "transport_errors": sum("error" in row for row in details),
            "truncated": sum(row.get("finish_reason") == "length" for row in details),
            "latency_mean_ms": statistics.mean(latencies) if latencies else 0,
            "latency_p50_ms": percentile(latencies, 0.5),
            "latency_p95_ms": percentile(latencies, 0.95),
            "wall_seconds": wall_seconds,
            "end_to_end_completion_tokens_per_second": completion / wall_seconds
            if wall_seconds
            else 0,
        }
    )
    result["limitations"] = (
        "Small selected subset, not the full benchmark. "
        "Greedy repeats are not independent samples. Latency includes queue, prompt and reasoning; "
        "end-to-end tokens/s is not engine decode speed. Truncated answers score zero. "
        "An incomplete run has only a lower-bound score and is not comparable. "
        "GSM8K executes no generated code; HumanEval uses a namespace boundary, not a VM, "
        "and is not intended as a service for deliberately hostile code."
    )
    return result


@click.command("strata")
@click.option("--dataset", type=click.Choice(["gsm8k", "humaneval"]), default="gsm8k")
@click.option("--base-url", default="http://127.0.0.1:8080/v1", show_default=True)
@click.option("--model", default=MODEL, show_default=True)
@click.option("--max-samples", type=click.IntRange(1, 1319), default=8, show_default=True)
@click.option("--repeat", type=click.IntRange(1, 100), default=1, show_default=True)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option("--effort", type=click.Choice(["none", "low", "medium", "high"]), default="none")
@click.option("--max-tokens", type=click.IntRange(1, 8192), default=2048)
@click.option("--timeout", type=click.FloatRange(min=1), default=600)
@click.option("--data-path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("results/strata"))
def strata(
    base_url: str,
    model: str,
    max_samples: int,
    repeat: int,
    seed: int,
    effort: str,
    max_tokens: int,
    timeout: float,
    data_path: Path | None,
    output_dir: Path,
    dataset: str,
) -> None:
    """Run pinned GSM8K/HumanEval against Strata with per-request checkpoints."""
    config = ModelConfig(
        name=model,
        base_url=base_url,
        api_key="",
        temperature=0,
        seed=seed,
        max_tokens=max_tokens,
        max_concurrent=1,
        timeout=timeout,
        reasoning_effort=effort,
        trust_env=False,
        max_retries=0,
    )
    try:
        rows, provenance = load_data(Path(".cache"), data_path, dataset)
        indices = select_indices(len(rows), max_samples, seed)
        sandbox = None
        if dataset == "humaneval":
            sandbox = IsolatedPython()
            sandbox.preflight()
            # Verify every selected official reference before scoring model output.
            for index in indices:
                task = rows[index]
                canonical = task["prompt"] + task["canonical_solution"]
                check = grade_candidate(canonical, task, sandbox)
                if not check["passed"]:
                    raise RuntimeError(
                        f"Canonical solution failed for {task['task_id']}: {check['stderr']}"
                    )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        run_dir = output_dir / f"{stamp}-{effort}"
        run_dir.mkdir(parents=True, exist_ok=False)
        click.echo(f"Model: {model}; dataset={dataset}; effort={effort}; indices={indices}")
        details, wall = asyncio.run(
            evaluate(config, rows, indices, repeat, run_dir, dataset, sandbox)
        )
        result = make_report(config, provenance, indices, repeat, details, wall)
        path = save_results(result, run_dir)
        save_html_report(result, run_dir / "report.html")
        click.echo(f"Accuracy: {result['results']['correct']}/{max_samples * repeat}")
        click.echo(f"JSON: {path}")
        click.echo(f"HTML: {run_dir / 'report.html'}")
        if not result["meta"]["completed"]:
            raise click.ClickException(
                "Run stopped after an API failure; partial evidence preserved"
            )
    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
        raise click.ClickException(str(exc)) from exc
