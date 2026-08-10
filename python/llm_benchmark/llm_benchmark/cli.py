"""CLI entry point for llm-benchmark.

Commands:
    llm-bench run      -- Run a benchmark evaluation
    llm-bench list     -- List available datasets
    llm-bench compare  -- Compare two result files
    llm-bench compare-models -- Compare multiple models on the same endpoint
    llm-bench report   -- Generate HTML report from a result file
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path

import click

from llm_benchmark import __version__
from llm_benchmark.api.client import LLMClient
from llm_benchmark.config import ModelConfig, get_model_config, load_config
from llm_benchmark.datasets import build_dataset, list_datasets
from llm_benchmark.metrics.code_metrics import compute_pass_at_k_scores
from llm_benchmark.metrics.math_metrics import math_score
from llm_benchmark.reporter.html_reporter import save_html_report
from llm_benchmark.reporter.json_reporter import build_result_json, diff_results, save_results
from llm_benchmark.runner.sandbox import CodeSandbox

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(__version__, prog_name="llm-bench")
def main():
    """LLM Benchmark — evaluate LLM math reasoning and coding ability."""


@main.command()
@click.option(
    "--dataset",
    "-d",
    default="all",
    help="Dataset name (math, gsm8k, humaneval, mbpp) or 'all'.",
)
@click.option("--model", "-m", default=None, help="Model name (from ~/.env config).")
@click.option("--repeat", "-r", default=3, type=int, help="Number of repeat runs for stability.")
@click.option("--max-samples", "-n", default=None, type=int, help="Max samples per dataset.")
@click.option("--num-samples", "-s", default=5, type=int, help="Samples per problem for pass@k.")
@click.option(
    "--max-concurrent",
    "-c",
    default=None,
    type=int,
    help="Max concurrent API requests. Defaults to LLM_MAX_CONCURRENT.",
)
@click.option("--output-dir", "-o", default="results", type=click.Path(), help="Output directory.")
def run(
    dataset: str,
    model: str | None,
    repeat: int,
    max_samples: int | None,
    num_samples: int,
    max_concurrent: int | None,
    output_dir: str,
):
    """Run benchmark evaluation on one or all datasets."""
    config = load_config()
    model_config = get_model_config(config, model)
    concurrency = _resolve_max_concurrent(model_config, max_concurrent)

    if dataset == "all":
        datasets = list_datasets()
    else:
        datasets = [dataset]

    click.echo(f"Model: {model_config.name} ({model_config.base_url})")
    click.echo(f"Datasets: {', '.join(datasets)}")
    click.echo(f"Repeat: {repeat}, Samples per problem: {num_samples}")
    click.echo(f"Max concurrent requests: {concurrency}")
    click.echo()

    for ds_name in datasets:
        click.echo(f"\n{'='*60}")
        click.echo(f"Running: {ds_name}")
        click.echo(f"{'='*60}")

        ds = build_dataset(ds_name, max_samples=max_samples)
        ds.load()
        click.echo(f"Loaded {len(ds)} samples")

        repeat_scores = []

        for r in range(repeat):
            score = asyncio.run(
                _run_single(
                    ds,
                    model_config,
                    num_samples,
                    r + 1,
                    repeat,
                    max_concurrent=concurrency,
                )
            )
            repeat_scores.append(score)

        # Save results
        result = build_result_json(
            benchmark_version=__version__,
            model=model_config.name,
            model_config={
                "base_url": model_config.base_url,
                "temperature": model_config.temperature,
                "seed": model_config.seed,
                "max_concurrent": concurrency,
            },
            dataset_name=ds_name,
            dataset_version="latest",
            num_samples=len(ds),
            repeat=repeat,
            overall_score=sum(repeat_scores) / len(repeat_scores) if repeat_scores else 0.0,
            metric_scores={},
            per_repeat=repeat_scores,
            std_dev=statistics.stdev(repeat_scores) if len(repeat_scores) > 1 else 0.0,
        )
        path = save_results(result, Path(output_dir))
        click.echo(f"Results saved to: {path}")

        # Generate HTML report
        html_path = save_html_report(
            dict(result),
            Path(output_dir) / f"{ds_name}_{model_config.name.replace('/', '_')}.html",
        )
        click.echo(f"HTML report: {html_path}")


@main.command("compare-models")
@click.option(
    "--models",
    default="qwen3.7-max,qwen3.8",
    help="Comma-separated model names to compare on the same endpoint.",
)
@click.option(
    "--endpoint-model",
    default=None,
    help="Configured model used only as the source of base_url/api_key. Defaults to LLM_MODEL.",
)
@click.option(
    "--dataset",
    "-d",
    default="all",
    help="Dataset name, comma-separated names, or 'all'.",
)
@click.option("--repeat", "-r", default=1, type=int, help="Repeat runs per model/dataset.")
@click.option(
    "--max-samples",
    "-n",
    default=10,
    type=int,
    help="Max samples per dataset. Defaults to 10 to avoid accidental full-cost runs.",
)
@click.option("--full", is_flag=True, help="Run full datasets; ignores --max-samples.")
@click.option("--num-samples", "-s", default=5, type=int, help="Samples per code problem.")
@click.option(
    "--max-concurrent",
    "-c",
    default=None,
    type=int,
    help="Max concurrent API requests per model. Defaults to LLM_MAX_CONCURRENT.",
)
@click.option(
    "--output-dir",
    "-o",
    default="results/qwen_plan_compare",
    type=click.Path(),
    help="Output directory for per-run files and comparison summary.",
)
def compare_models(
    models: str,
    endpoint_model: str | None,
    dataset: str,
    repeat: int,
    max_samples: int,
    full: bool,
    num_samples: int,
    max_concurrent: int | None,
    output_dir: str,
):
    """Compare models on the same OpenAI-compatible endpoint.

    This is intended for Qwen plan-code endpoint comparisons: it reuses the
    configured base_url/api_key and only changes the model field sent to the API.
    """
    model_names = _parse_csv(models)
    if len(model_names) < 2:
        raise click.ClickException("--models must contain at least two model names")
    if repeat < 1:
        raise click.ClickException("--repeat must be >= 1")
    if num_samples < 1:
        raise click.ClickException("--num-samples must be >= 1")

    config = load_config()
    endpoint_config = get_model_config(config, endpoint_model)
    if not endpoint_config.api_key:
        raise click.ClickException("No API key configured for the endpoint model")
    concurrency = _resolve_max_concurrent(endpoint_config, max_concurrent)

    sample_limit = None if full else max_samples
    dataset_names = list_datasets() if dataset == "all" else _parse_csv(dataset)
    model_configs = [_same_endpoint_model(endpoint_config, name) for name in model_names]

    output_root = Path(output_dir)
    runs_dir = output_root / "runs"
    baseline = model_names[0]
    rows = []

    click.echo(f"Endpoint: {endpoint_config.base_url}")
    click.echo(f"Models: {', '.join(model_names)}")
    click.echo(f"Datasets: {', '.join(dataset_names)}")
    click.echo(f"Repeat: {repeat}, Samples per code problem: {num_samples}")
    click.echo(f"Max concurrent requests per model: {concurrency}")
    click.echo(f"Max samples: {'full' if full else sample_limit}")

    for ds_name in dataset_names:
        click.echo(f"\n{'='*60}")
        click.echo(f"Benchmark: {ds_name}")
        click.echo(f"{'='*60}")

        try:
            ds = build_dataset(ds_name, max_samples=sample_limit)
            ds.load()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            click.echo(f"ERROR: failed to load dataset '{ds_name}': {error}")
            rows.append(
                {
                    "dataset": ds_name,
                    "num_samples": 0,
                    "scores": {name: None for name in model_names},
                    "per_repeat": {name: [] for name in model_names},
                    "delta_vs_baseline": {},
                    "winner": "",
                    "result_paths": {},
                    "errors": {"dataset": error},
                }
            )
            continue
        click.echo(f"Loaded {len(ds)} samples")

        scores_by_model = {}
        repeats_by_model = {}
        result_paths = {}
        errors_by_model = {}

        for model_config in model_configs:
            click.echo(f"\nModel: {model_config.name}")
            repeat_scores = []
            for r in range(repeat):
                try:
                    score = asyncio.run(
                        _run_single(
                            ds,
                            model_config,
                            num_samples,
                            r + 1,
                            repeat,
                            max_concurrent=concurrency,
                        )
                    )
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    errors_by_model[model_config.name] = error
                    click.echo(f"  ERROR: {error}")
                    break
                repeat_scores.append(score)

            if model_config.name in errors_by_model:
                scores_by_model[model_config.name] = None
                repeats_by_model[model_config.name] = repeat_scores
                continue

            overall = _mean(repeat_scores)
            scores_by_model[model_config.name] = overall
            repeats_by_model[model_config.name] = repeat_scores

            result = build_result_json(
                benchmark_version=__version__,
                model=model_config.name,
                model_config={
                    "base_url": model_config.base_url,
                    "temperature": model_config.temperature,
                    "seed": model_config.seed,
                    "max_concurrent": concurrency,
                },
                dataset_name=ds_name,
                dataset_version="latest",
                num_samples=len(ds),
                repeat=repeat,
                overall_score=overall,
                metric_scores={},
                per_repeat=repeat_scores,
                std_dev=statistics.stdev(repeat_scores) if len(repeat_scores) > 1 else 0.0,
            )
            result_path = save_results(result, runs_dir)
            html_path = save_html_report(
                dict(result),
                runs_dir / f"{ds_name}_{model_config.name.replace('/', '_')}.html",
            )
            result_paths[model_config.name] = {
                "json": str(result_path),
                "html": str(html_path),
            }
            click.echo(f"  Results: {result_path}")

        baseline_score = scores_by_model[baseline]
        deltas = {
            name: round(score - baseline_score, 6)
            for name, score in scores_by_model.items()
            if name != baseline and score is not None and baseline_score is not None
        }
        valid_scores = {
            name: score for name, score in scores_by_model.items() if score is not None
        }
        winner = max(valid_scores, key=valid_scores.get) if valid_scores else ""
        rows.append(
            {
                "dataset": ds_name,
                "num_samples": len(ds),
                "scores": scores_by_model,
                "per_repeat": repeats_by_model,
                "delta_vs_baseline": deltas,
                "winner": winner,
                "result_paths": result_paths,
                "errors": errors_by_model,
            }
        )

    summary = {
        "meta": {
            "benchmark_version": __version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint_base_url": endpoint_config.base_url,
            "endpoint_model": endpoint_config.name,
            "models": model_names,
            "baseline": baseline,
            "datasets": dataset_names,
            "repeat": repeat,
            "max_samples": None if full else sample_limit,
            "full": full,
            "num_samples": num_samples,
            "max_concurrent": concurrency,
        },
        "results": rows,
    }
    json_path, csv_path, md_path = _write_comparison_summary(summary, output_root)

    click.echo("\nComparison")
    _echo_comparison_table(rows, model_names, baseline)
    click.echo(f"\nSummary JSON: {json_path}")
    click.echo(f"Summary CSV: {csv_path}")
    click.echo(f"Summary Markdown: {md_path}")


async def _run_single(
    ds,
    model_config,
    num_samples: int,
    run_num: int,
    total_runs: int,
    *,
    max_concurrent: int | None = None,
) -> float:
    """Run a single evaluation pass on a dataset."""
    client = LLMClient(model_config)
    sandbox = CodeSandbox()
    concurrency = _resolve_max_concurrent(model_config, max_concurrent)
    semaphore = asyncio.Semaphore(concurrency)

    try:
        category = ds.get_category()

        if category == "math":
            async def evaluate_math_problem(i: int) -> bool:
                prompt = ds.get_prompt(i)
                reference = ds.get_reference(i)
                async with semaphore:
                    resp = await client.chat(
                        messages=[{"role": "user", "content": prompt}],
                    )
                return math_score(resp.text, reference) > 0

            problem_results = await asyncio.gather(
                *(evaluate_math_problem(i) for i in range(len(ds)))
            )
            score = sum(1 for passed in problem_results if passed) / len(problem_results)

        elif category == "code":
            async def evaluate_code_problem(i: int) -> list[bool]:
                prompt = ds.get_prompt(i)
                test_cases = ds.get_test_cases(i)
                test_code = "\n".join(test_cases)

                async def evaluate_sample() -> bool:
                    async with semaphore:
                        resp = await client.chat(
                            messages=[{"role": "user", "content": prompt}],
                        )
                        result = await asyncio.to_thread(
                            sandbox.run,
                            resp.text + "\n" + test_code,
                        )
                    return result.success

                return list(
                    await asyncio.gather(*(evaluate_sample() for _ in range(num_samples)))
                )

            results_per_problem = await asyncio.gather(
                *(evaluate_code_problem(i) for i in range(len(ds)))
            )
            scores = compute_pass_at_k_scores(results_per_problem, k_values=[1])
            score = scores[1]

        else:
            raise ValueError(f"Unknown dataset category: {category}")

        click.echo(
            f"  Run {run_num}/{total_runs}: score={score:.4f} "
            f"(concurrency={concurrency})"
        )
        return score

    finally:
        await client.close()


def _resolve_max_concurrent(model_config, override: int | None = None) -> int:
    concurrency = override if override is not None else getattr(model_config, "max_concurrent", 4)
    if concurrency < 1:
        raise click.ClickException("--max-concurrent must be >= 1")
    return concurrency


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _same_endpoint_model(endpoint_config: ModelConfig, model_name: str) -> ModelConfig:
    return ModelConfig(
        name=model_name,
        base_url=endpoint_config.base_url,
        api_key=endpoint_config.api_key,
        temperature=endpoint_config.temperature,
        seed=endpoint_config.seed,
        max_tokens=endpoint_config.max_tokens,
        max_concurrent=endpoint_config.max_concurrent,
        timeout=endpoint_config.timeout,
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _write_comparison_summary(summary: dict, output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = summary["meta"]["timestamp"].split("+")[0].split(".")[0].replace(":", "-")
    stem = f"comparison_{timestamp}"
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    md_path = output_dir / f"{stem}.md"

    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    models = summary["meta"]["models"]
    baseline = summary["meta"]["baseline"]
    fieldnames = ["dataset", "num_samples", *[f"score:{m}" for m in models]]
    fieldnames.extend(f"delta_vs_{baseline}:{m}" for m in models if m != baseline)
    fieldnames.append("winner")

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["results"]:
            csv_row = {
                "dataset": row["dataset"],
                "num_samples": row["num_samples"],
                "winner": row["winner"],
            }
            csv_row.update({f"score:{m}": row["scores"].get(m, "") for m in models})
            csv_row.update(
                {
                    f"delta_vs_{baseline}:{m}": row["delta_vs_baseline"].get(m, "")
                    for m in models
                    if m != baseline
                }
            )
            writer.writerow(csv_row)

    md_lines = [
        "# Model Comparison",
        "",
        f"- Endpoint: `{summary['meta']['endpoint_base_url']}`",
        f"- Baseline: `{baseline}`",
        f"- Repeat: `{summary['meta']['repeat']}`",
        f"- Max samples: `{summary['meta']['max_samples']}`",
        "",
    ]
    headers = ["Dataset", "Samples", *models]
    headers.extend(f"Delta vs {baseline}: {m}" for m in models if m != baseline)
    headers.append("Winner")
    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in summary["results"]:
        cells = [row["dataset"], str(row["num_samples"])]
        cells.extend(_fmt_score(row["scores"].get(m)) for m in models)
        cells.extend(
            _fmt_delta(row["delta_vs_baseline"].get(m))
            for m in models
            if m != baseline
        )
        cells.append(row["winner"])
        md_lines.append("| " + " | ".join(cells) + " |")
    md_path.write_text("\n".join(md_lines) + "\n")

    return json_path, csv_path, md_path


def _echo_comparison_table(rows: list[dict], models: list[str], baseline: str) -> None:
    headers = ["Dataset", "N", *models]
    headers.extend(f"d({m})" for m in models if m != baseline)
    headers.append("Winner")

    table = [headers]
    for row in rows:
        cells = [row["dataset"], str(row["num_samples"])]
        cells.extend(_fmt_score(row["scores"].get(m)) for m in models)
        cells.extend(
            _fmt_delta(row["delta_vs_baseline"].get(m))
            for m in models
            if m != baseline
        )
        cells.append(row["winner"])
        table.append(cells)

    widths = [max(len(r[i]) for r in table) for i in range(len(headers))]
    for idx, row in enumerate(table):
        click.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if idx == 0:
            click.echo("  ".join("-" * width for width in widths))


def _fmt_score(value: float | None) -> str:
    return "" if value is None else f"{value:.4f}"


def _fmt_delta(value: float | None) -> str:
    return "" if value is None else f"{value:+.4f}"


@main.command("list")
def list_cmd():
    """List all available datasets."""
    click.echo("Available datasets:")
    for name in list_datasets():
        click.echo(f"  - {name}")


@main.command()
@click.argument("a_path", type=click.Path(exists=True))
@click.argument("b_path", type=click.Path(exists=True))
def compare(a_path: str, b_path: str):
    """Compare two benchmark result JSON files."""
    diff = diff_results(Path(a_path), Path(b_path))
    click.echo(f"Dataset: {diff['dataset']}")
    click.echo(f"Model A ({diff['model_a']}): {diff['scores_a']:.4f}")
    click.echo(f"Model B ({diff['model_b']}): {diff['scores_b']:.4f}")
    click.echo(f"Delta: {diff['scores_b'] - diff['scores_a']:+.4f}")
    click.echo()
    click.echo("Per-metric diffs:")
    for key, val in diff["diffs"].items():
        if isinstance(val, (int, float)):
            click.echo(f"  {key}: {val:+.4f}")


@main.command()
@click.argument("result_path", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output HTML file path.")
def report(result_path: str, output: str | None):
    """Generate an HTML visualization report from a result JSON file."""
    path = Path(result_path)
    if output:
        output_path = Path(output)
    else:
        output_path = path.parent / f"{path.stem}.html"

    with open(path) as f:
        result = json.load(f)

    html_path = save_html_report(result, output_path)
    click.echo(f"HTML report generated: {html_path}")


if __name__ == "__main__":
    main()
