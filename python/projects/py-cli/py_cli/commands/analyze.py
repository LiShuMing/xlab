"""Analyze command for py-cli."""

from __future__ import annotations

from pathlib import Path

import click

from py_cli.config import Config
from py_cli.core.analyzer import Analyzer
from py_cli.exceptions import ConfigError, AnalysisError
from py_cli.llm.prompts import list_prompts
from py_cli.utils import parse_date


@click.command(name="analyze")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to git repository (default: current directory)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (default: auto-generated)",
)
@click.option(
    "--since",
    "-s",
    help="Start date (YYYY-MM-DD format, default: 30 days ago)",
)
@click.option(
    "--until",
    "-u",
    help="End date (YYYY-MM-DD format, default: today)",
)
@click.option(
    "--prompt",
    "-p",
    default="default",
    help="Prompt template to use",
    type=click.Choice(list_prompts()),
)
@click.option(
    "--max-commits",
    "-m",
    type=int,
    default=100,
    help="Maximum number of commits to analyze",
)
def analyze_command(
    repo: Path | None,
    output: Path | None,
    since: str | None,
    until: str | None,
    prompt: str,
    max_commits: int,
) -> None:
    """Analyze git commits and generate a report.

    Analyzes commits in the specified date range using LLM
    and generates a structured technical report.

    Examples:
        py-cli analyze                    # Analyze current repo, last 30 days
        py-cli analyze -r /path/to/repo   # Analyze specific repository
        py-cli analyze -s 2024-01-01      # Start from specific date
        py-cli analyze -o report.md       # Custom output file
        py-cli analyze -p clickhouse      # Use ClickHouse prompt
    """
    try:
        # Validate and parse dates
        since_date = parse_date(since) if since else None
        until_date = parse_date(until) if until else None

        # Load configuration
        config = Config.load()

        # Override max_commits in config
        object.__setattr__(config.analyzer, "max_commits", max_commits)

        # Create analyzer
        analyzer = Analyzer(config)

        # Run analysis
        analyzer.analyze(
            repo_path=repo,
            output_path=output,
            since=since_date,
            until=until_date,
            prompt_name=prompt,
        )

    except ConfigError as e:
        raise click.ClickException(f"Configuration error: {e}")
    except AnalysisError as e:
        raise click.ClickException(f"Analysis failed: {e}")
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}")
