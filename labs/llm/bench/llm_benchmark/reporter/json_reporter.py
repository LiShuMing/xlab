"""JSON result reporter — versioned output for reproducibility and diff comparison."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_commit_hash() -> str:
    """Get the current git commit hash, or 'unknown' if not available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _default_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def build_result_json(
    *,
    benchmark_version: str,
    model: str,
    model_config: dict[str, Any],
    dataset_name: str,
    dataset_version: str,
    num_samples: int,
    repeat: int,
    overall_score: float,
    metric_scores: dict[str, float],
    per_repeat: list[float],
    std_dev: float,
    by_difficulty: dict[str, float] | None = None,
    details: list[dict[str, Any]] | None = None,
    latencies_ms: list[float] | None = None,
    total_tokens: int = 0,
) -> dict[str, Any]:
    """Build a versioned benchmark result JSON structure.

    Returns a dict ready for serialization with json.dump.
    """
    timestamp = datetime.now(timezone.utc)
    commit_hash = _get_commit_hash()

    return {
        "meta": {
            "benchmark_version": benchmark_version,
            "timestamp": timestamp.isoformat(),
            "model": model,
            "model_config": model_config,
            "dataset": dataset_name,
            "dataset_version": dataset_version,
            "num_samples": num_samples,
            "repeat": repeat,
            "commit_hash": commit_hash,
        },
        "results": {
            "overall_score": overall_score,
            "metric_scores": metric_scores,
            "per_repeat": per_repeat,
            "std_dev": std_dev,
            "by_difficulty": by_difficulty or {},
            "latencies_ms": latencies_ms or [],
            "total_tokens": total_tokens,
            "details": details or [],
        },
    }


def save_results(result: dict[str, Any], results_dir: Path) -> Path:
    """Save benchmark results to a versioned JSON file.

    Returns the path to the saved file.
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    meta = result["meta"]
    dataset = meta["dataset"]
    model = meta["model"].replace("/", "_")

    timestamp = meta["timestamp"].split("+")[0].split(".")[0].replace(":", "-")
    filename = f"{dataset}_{model}_{timestamp}.json"
    filepath = results_dir / filename

    with open(filepath, "w") as f:
        json.dump(result, f, indent=2, default=_default_serializer, ensure_ascii=False)

    return filepath


def diff_results(a_path: Path, b_path: Path) -> dict[str, Any]:
    """Compare two benchmark result JSON files and return a diff.

    Returns a dict with scores_a, scores_b, and diffs.
    """
    with open(a_path) as f:
        a = json.load(f)
    with open(b_path) as f:
        b = json.load(f)

    a_results = a["results"]
    b_results = b["results"]

    diffs = {}
    for key in set(a_results) | set(b_results):
        if key in ("details", "by_difficulty", "latencies_ms"):
            continue
        a_val = a_results.get(key)
        b_val = b_results.get(key)
        if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)):
            diffs[key] = round(b_val - a_val, 6)
        else:
            diffs[key] = {"a": a_val, "b": b_val}

    return {
        "model_a": a["meta"]["model"],
        "model_b": b["meta"]["model"],
        "dataset": a["meta"]["dataset"],
        "scores_a": a_results["overall_score"],
        "scores_b": b_results["overall_score"],
        "diffs": diffs,
    }