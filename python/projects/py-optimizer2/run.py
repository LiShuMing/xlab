#!/usr/bin/env python3
"""Main entry point for Optimizer Expert Analyzer Agent."""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from src.comparison import CanonicalNormalizer, DiffMatrixGenerator, ScoringEngine
from src.enumerator import RuleEnumerator
from src.harness import AnalysisHarness


DEFAULT_ENGINES = [
    "starrocks",
    "doris",
    "clickhouse",
    "gpdb_orca",
    "calcite",
    "cockroachdb",
    "postgres",
    "columbia",
]


def cmd_enumerate(args):
    """Task 1: Enumerate rules from engine source code."""
    print("=" * 60)
    print("Task 1: Rule Enumeration")
    print("=" * 60)

    engines_dir = Path("engines")
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    all_tasks = []

    for engine_id in args.engines:
        config_path = engines_dir / f"{engine_id}.yaml"
        if not config_path.exists():
            print(f"Warning: Config not found for {engine_id}, skipping")
            continue

        print(f"\nProcessing engine: {engine_id}")

        # Check if already enumerated
        file_index = data_dir / f"{engine_id}_file_index.json"
        if file_index.exists() and not args.force_rescan:
            print(f"  Found existing file index for {engine_id}, skipping (use --force-rescan to override)")
            with open(file_index) as f:
                scan_results_data = json.load(f)
            # Convert back to tasks
            for data in scan_results_data:
                from src.models import RuleCategory, Task, TaskStatus
                task = Task(
                    task_id=f"{engine_id}::{data['category']}::{data['rule_name']}",
                    engine_id=engine_id,
                    category=RuleCategory(data['category']),
                    rule_name=data['rule_name'],
                    source_file=data['source_file'],
                    source_snippet=data['source_snippet'],
                    optimizer_framework=data.get('optimizer_framework', 'cascades'),
                    language=data.get('language', 'cpp'),
                    status=TaskStatus.PENDING,
                    dsl_file=data.get('dsl_file'),
                    dsl_snippet=data.get('dsl_snippet'),
                )
                all_tasks.append(task)
            continue

        # Enumerate rules
        enumerator = RuleEnumerator(config_path, Path(args.source_root))
        scan_results = enumerator.enumerate_rules()

        print(f"  Found {len(scan_results)} rules")

        # Save file index
        scan_results_data = []
        for result in scan_results:
            scan_results_data.append({
                'rule_name': result.rule_name,
                'category': result.category,
                'source_file': str(result.source_file),
                'source_snippet': result.source_snippet,
                'dsl_file': str(result.dsl_file) if result.dsl_file else None,
                'dsl_snippet': result.dsl_snippet,
                'metadata': result.metadata,
            })

        with open(file_index, 'w') as f:
            json.dump(scan_results_data, f, indent=2)

        # Generate tasks
        tasks = enumerator.generate_tasks(scan_results)
        all_tasks.extend(tasks)

        # Estimate tokens
        total_tokens = sum(t.estimated_tokens for t in tasks)
        print(f"  Generated {len(tasks)} tasks, ~{total_tokens} tokens estimated")

    # Save task queue
    task_queue_path = data_dir / "task_queue.json"

    # Merge with existing queue if resuming
    if task_queue_path.exists() and args.resume:
        print(f"\nMerging with existing task queue...")
        with open(task_queue_path) as f:
            existing_tasks = json.load(f)

        existing_ids = {t['task_id'] for t in existing_tasks}
        new_tasks = [t for t in all_tasks if t.task_id not in existing_ids]

        # Add new tasks
        for task in new_tasks:
            existing_tasks.append({
                'task_id': task.task_id,
                'engine_id': task.engine_id,
                'category': task.category.value,
                'rule_name': task.rule_name,
                'source_file': task.source_file,
                'source_snippet': task.source_snippet,
                'dsl_file': task.dsl_file,
                'dsl_snippet': task.dsl_snippet,
                'optimizer_framework': task.optimizer_framework.value if hasattr(task.optimizer_framework, 'value') else task.optimizer_framework,
                'language': task.language.value if hasattr(task.language, 'value') else task.language,
                'status': task.status.value,
                'priority': task.priority,
                'estimated_tokens': task.estimated_tokens,
                'created_at': task.created_at,
                'analyzed_at': None,
                'retries': 0,
            })

        with open(task_queue_path, 'w') as f:
            json.dump(existing_tasks, f, indent=2)

        print(f"Added {len(new_tasks)} new tasks to existing queue")
        print(f"Total tasks in queue: {len(existing_tasks)}")
    else:
        # Create fresh queue
        tasks_data = []
        for task in all_tasks:
            tasks_data.append({
                'task_id': task.task_id,
                'engine_id': task.engine_id,
                'category': task.category.value,
                'rule_name': task.rule_name,
                'source_file': task.source_file,
                'source_snippet': task.source_snippet,
                'dsl_file': task.dsl_file,
                'dsl_snippet': task.dsl_snippet,
                'optimizer_framework': task.optimizer_framework.value if hasattr(task.optimizer_framework, 'value') else task.optimizer_framework,
                'language': task.language.value if hasattr(task.language, 'value') else task.language,
                'status': task.status.value,
                'priority': task.priority,
                'estimated_tokens': task.estimated_tokens,
                'created_at': task.created_at,
                'analyzed_at': None,
                'retries': 0,
            })

        with open(task_queue_path, 'w') as f:
            json.dump(tasks_data, f, indent=2)

        print(f"\nTotal tasks generated: {len(tasks_data)}")

    # Print summary
    total_tokens = sum(t.estimated_tokens for t in all_tasks)
    print(f"\n{'=' * 60}")
    print("Enumeration Summary")
    print(f"{'=' * 60}")
    print(f"Engines: {len(args.engines)}")
    print(f"Total rules: {len(all_tasks)}")
    print(f"Estimated tokens: ~{total_tokens:,}")
    print(f"Estimated API calls: {len(all_tasks)}")
    print(f"Task queue: {task_queue_path}")


def cmd_analyze(args):
    """Task 2: Analyze rules using LLM."""
    print("=" * 60)
    print("Task 2: Rule Analysis")
    print("=" * 60)

    data_dir = Path("data")
    task_queue_path = data_dir / "task_queue.json"

    if not task_queue_path.exists():
        print(f"Error: Task queue not found at {task_queue_path}")
        print("Run 'python run.py enumerate' first")
        sys.exit(1)

    # Use explicit args only - config will load from ~/.env in harness
    # Avoid using ANTHROPIC_* env vars which may conflict with LLM_* settings
    api_key = args.api_key if args.api_key else None
    base_url = args.base_url if args.base_url else None

    # Show info about config source
    if not api_key:
        print("No explicit API key provided, will use config from ~/.env")

    harness = AnalysisHarness(
        task_queue_path=task_queue_path,
        output_dir=data_dir,
        api_key=api_key,
        model=args.model,
        base_url=base_url,
    )

    stats = harness.run_analysis(
        engine_id=args.engine,
        max_tasks=args.max_tasks,
        resume=not args.no_resume,
    )

    print(f"\n{'=' * 60}")
    print("Analysis Summary")
    print(f"{'=' * 60}")
    print(f"Completed: {stats['completed']}")
    print(f"Needs review: {stats['needs_review']}")
    print(f"Failed: {stats['failed']}")


def cmd_normalize(args):
    """Task 2.5: Normalize canonical names."""
    print("=" * 60)
    print("Task 2.5: Canonical Name Normalization")
    print("=" * 60)

    data_dir = Path("data")

    # Check if already normalized
    map_file = data_dir / "canonical_name_map.json"
    if map_file.exists() and not args.force:
        print(f"Found existing canonical map at {map_file}")
        print("Use --force to re-normalize")
        return

    normalizer = CanonicalNormalizer(
        data_dir=data_dir,
        api_key=args.api_key or os.environ.get("ANTHROPIC_API_KEY"),
    )

    mapping = normalizer.normalize()

    total_mappings = sum(len(m) for m in mapping.values())
    print(f"\nGenerated {total_mappings} canonical name mappings")
    print(f"Saved to: {map_file}")


def cmd_compare(args):
    """Task 3: Generate comparison reports."""
    print("=" * 60)
    print("Task 3: Multi-Engine Comparison")
    print("=" * 60)

    data_dir = Path("data")

    # Generate diff matrix
    print("\nGenerating diff matrix...")
    diff_gen = DiffMatrixGenerator(data_dir)
    entries = diff_gen.generate()
    print(f"Generated {len(entries)} diff entries")

    # Calculate scores
    print("\nCalculating scores...")
    scoring = ScoringEngine(data_dir)
    scores = scoring.calculate_scores()

    print(f"\n{'=' * 60}")
    print("Engine Scores")
    print(f"{'=' * 60}")
    for engine, score_data in sorted(scores.items(), key=lambda x: x[1].get('overall_score', 0), reverse=True):
        overall = score_data.get('overall_score', 0)
        coverage = score_data.get('coverage_score', 0)
        print(f"{engine:20s} Overall: {overall:5.1f}  Coverage: {coverage:5.1f}%")


def cmd_report(args):
    """Generate Markdown reports."""
    print("=" * 60)
    print("Generating Reports")
    print("=" * 60)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    data_dir = Path("data")

    # TODO: Generate detailed markdown reports
    print("\nReports generated in output/")


def main():
    parser = argparse.ArgumentParser(
        description="Optimizer Expert Analyzer Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Enumerate command
    enumerate_parser = subparsers.add_parser(
        "enumerate",
        help="Task 1: Enumerate rules from engine source code",
    )
    enumerate_parser.add_argument(
        "--engines",
        nargs="+",
        default=DEFAULT_ENGINES,
        help="Engines to enumerate (default: all)",
    )
    enumerate_parser.add_argument(
        "--source-root",
        default=".",
        help="Root directory for engine source code",
    )
    enumerate_parser.add_argument(
        "--force-rescan",
        action="store_true",
        help="Force rescan even if file index exists",
    )
    enumerate_parser.add_argument(
        "--resume",
        action="store_true",
        help="Merge with existing task queue",
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Task 2: Analyze rules using LLM",
    )
    analyze_parser.add_argument(
        "--engine",
        help="Analyze only specific engine",
    )
    analyze_parser.add_argument(
        "--max-tasks",
        type=int,
        help="Maximum number of tasks to analyze",
    )
    analyze_parser.add_argument(
        "--api-key",
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )
    analyze_parser.add_argument(
        "--base-url",
        help="Anthropic API base URL (or set ANTHROPIC_BASE_URL env var)",
    )
    analyze_parser.add_argument(
        "--model",
        default="qwen3.5-plus",
        help="Model to use (default: qwen3.5-plus)",
    )
    analyze_parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't resume from previous run",
    )

    # Normalize command
    normalize_parser = subparsers.add_parser(
        "normalize",
        help="Task 2.5: Normalize canonical names across engines",
    )
    normalize_parser.add_argument(
        "--api-key",
        help="Anthropic API key",
    )
    normalize_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-normalization",
    )

    # Compare command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Task 3: Generate comparison reports",
    )

    # Report command
    report_parser = subparsers.add_parser(
        "report",
        help="Generate Markdown reports",
    )

    # Run all command
    runall_parser = subparsers.add_parser(
        "runall",
        help="Run all tasks (enumerate, analyze, normalize, compare, report)",
    )
    runall_parser.add_argument(
        "--engines",
        nargs="+",
        default=DEFAULT_ENGINES,
        help="Engines to process",
    )
    runall_parser.add_argument(
        "--source-root",
        default=".",
        help="Root directory for engine source code",
    )
    runall_parser.add_argument(
        "--api-key",
        help="Anthropic API key",
    )

    args = parser.parse_args()

    if args.command == "enumerate":
        cmd_enumerate(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "normalize":
        cmd_normalize(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "runall":
        print("Running all tasks...")
        args.force_rescan = False
        args.resume = True
        cmd_enumerate(args)
        cmd_analyze(args)
        args.force = False
        cmd_normalize(args)
        cmd_compare(args)
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
