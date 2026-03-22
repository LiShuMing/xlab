"""analyze command: full pipeline (parse -> chunk -> extract -> report)."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from paper_agent.core.config import RunConfig
from paper_agent.core.paths import RunPaths
from paper_agent.core.state import RunState, Stage
from paper_agent.utils.hashing import sha256_file
from paper_agent.utils.io import write_json
from paper_agent.utils.logging import configure_logging

console = Console()


def register(app: typer.Typer) -> None:

    @app.command()
    def analyze(
        pdf: Path = typer.Argument(..., help="Path to PDF file"),
        output: Path = typer.Option(Path("./runs"), "--output", "-o"),
        run_name: Optional[str] = typer.Option(None, "--run-name"),
        template: str = typer.Option("deep-dive", "--template", "-t",
                                     help="Report template: summary | deep-dive"),
        model: Optional[str] = typer.Option(None, "--model", help="LLM model name"),
        from_stage: Optional[str] = typer.Option(None, "--from-stage",
                                                  help="Start from stage: parse|chunk|extract|bind_evidence|report"),
        to_stage: Optional[str] = typer.Option(None, "--to-stage",
                                               help="Stop after stage"),
        resume: bool = typer.Option(False, "--resume", help="Skip completed stages"),
        force: bool = typer.Option(False, "--force", help="Overwrite existing output"),
        skip_references: bool = typer.Option(False, "--skip-references"),
        chunk_size: int = typer.Option(1200, "--chunk-size"),
        chunk_overlap: int = typer.Option(150, "--chunk-overlap"),
        config_file: Optional[Path] = typer.Option(None, "--config"),
        save_trace: bool = typer.Option(False, "--save-trace"),
        verbose: bool = typer.Option(False, "--verbose", "-v"),
        debug: bool = typer.Option(False, "--debug"),
    ) -> None:
        """Run full analysis pipeline on a PDF: parse → extract → report."""
        configure_logging(verbose=verbose, debug=debug)

        if not pdf.exists():
            console.print(f"[red]Error:[/red] File not found: {pdf}")
            raise typer.Exit(1)

        cfg = RunConfig.load(
            config_file=config_file,
            run_name=run_name,
            template=template,
            model=model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            skip_references=skip_references,
            save_trace=save_trace,
            verbose=verbose,
            debug=debug,
        )

        run_name_resolved = cfg.run_name or pdf.stem
        run_dir = output / run_name_resolved
        paths = RunPaths(run_dir)

        # Check existing
        if run_dir.exists() and not resume and not force:
            console.print(
                f"[yellow]Warning:[/yellow] {run_dir} already exists.\n"
                "Use --resume to continue or --force to overwrite."
            )
            raise typer.Exit(1)

        paths.ensure_dirs()

        sha256 = sha256_file(pdf)
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, sha256))

        if paths.metadata.exists() and resume and not force:
            state = RunState(paths.metadata)
            console.print(f"[blue]Resuming:[/blue] {run_dir}")
        else:
            state = RunState.create(
                paths.metadata,
                document_id=document_id,
                filename=pdf.name,
                sha256=sha256,
                config=cfg.model_dump(mode="json"),
            )
            console.print(f"[green]Starting analysis:[/green] {run_dir}")

        # Store pdf_path in state so runner can find the original file
        state._data["pdf_path"] = str(pdf.resolve())
        state._save()

        write_json(paths.config, cfg.model_dump(mode="json"))

        # Resolve stage range
        from paper_agent.core.state import STAGE_ORDER
        fs = Stage(from_stage) if from_stage else Stage.PARSE
        ts = Stage(to_stage) if to_stage else Stage.REPORT

        from paper_agent.core.runner import PipelineRunner
        runner = PipelineRunner(paths, state, cfg)

        t0 = time.time()
        try:
            runner.run(from_stage=fs, to_stage=ts, resume=resume)
        except Exception as e:
            console.print(f"\n[red]Pipeline failed:[/red] {e}")
            raise typer.Exit(1)

        elapsed = time.time() - t0
        console.print(f"\n[bold green]Done[/bold green] in {elapsed:.1f}s")
        console.print(f"Output: {run_dir}")

        # Show report paths
        reports_dir = paths.reports_dir
        if reports_dir.exists():
            for md in reports_dir.glob("*.md"):
                console.print(f"  [blue]Report:[/blue] {md}")
