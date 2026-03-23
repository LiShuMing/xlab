"""report command: generate reports from existing analysis."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from paper_agent.core.paths import RunPaths
from paper_agent.extraction.paper_schema import PaperSchema
from paper_agent.llm.client import LLMClient
from paper_agent.report.writer import generate_report
from paper_agent.utils.io import read_json, read_jsonl, write_text
from paper_agent.utils.logging import configure_logging, set_correlation_id

console = Console()

_TEMPLATES: list[str] = ["summary", "deep-dive", "blog", "interview-note"]


def register(app: typer.Typer) -> None:
    """Register the report command with the CLI app."""

    @app.command()
    def report(
        run_dir: Path = typer.Argument(..., help="Path to run directory"),
        template: str = typer.Option(
            "deep-dive",
            "--template",
            "-t",
            help=f"Template: {' | '.join(_TEMPLATES)}",
        ),
        model: str | None = typer.Option(None, "--model"),
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            help="Output file path (default: run_dir/reports/<template>.md)",
        ),
        verbose: bool = typer.Option(False, "--verbose", "-v"),
        debug: bool = typer.Option(False, "--debug"),
    ) -> None:
        """Generate a report from an existing analysis."""
        set_correlation_id()
        configure_logging(verbose=verbose, debug=debug)

        paths = RunPaths(run_dir)

        if not paths.paper_schema.exists():
            console.print(
                f"[red]Error:[/red] No paper schema found in {run_dir}. Run analyze first."
            )
            raise typer.Exit(1)

        chunks = read_jsonl(paths.chunks) if paths.chunks.exists() else []
        schema_data = read_json(paths.paper_schema)
        schema = PaperSchema.from_dict(schema_data)
        evidence = read_json(paths.evidence) if paths.evidence.exists() else []

        cfg_data = read_json(paths.config) if paths.config.exists() else {}
        resolved_model = model or cfg_data.get("model", "qwen3.5-plus")
        timeout = cfg_data.get("timeout", 300)

        llm = LLMClient(
            model=resolved_model, max_tokens=3000, temperature=0.1, timeout=timeout
        )

        console.print(
            f"[blue]Generating {template} report for:[/blue] {schema.title[:60]!r}"
        )

        report_md = generate_report(schema, evidence, chunks, llm, template=template)

        out_path = output or paths.report(template.replace("-", "_"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_text(out_path, report_md)

        console.print(f"[green]Report saved:[/green] {out_path}")
        console.print("\n[dim]Preview (first 500 chars):[/dim]")
        console.print(report_md[:500])
