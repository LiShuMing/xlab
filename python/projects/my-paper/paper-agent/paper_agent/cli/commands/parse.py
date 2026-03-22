"""parse command: PDF parsing only, no LLM calls."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from paper_agent.core.config import RunConfig
from paper_agent.core.paths import RunPaths
from paper_agent.core.state import RunState, Stage
from paper_agent.parser.chunker import chunk_blocks
from paper_agent.parser.pdf_parser import parse_pdf
from paper_agent.parser.section_detector import assign_section_to_blocks, detect_sections
from paper_agent.utils.hashing import sha256_file
from paper_agent.utils.io import write_json, write_jsonl
from paper_agent.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


def run_parse(
    pdf_path: Path,
    output_dir: Path,
    config: RunConfig,
    resume: bool = False,
    force: bool = False,
) -> RunPaths:
    """
    Execute parse pipeline: PDF -> pages.json, sections.json, chunks.jsonl.

    Returns RunPaths for the output directory.
    """
    if not pdf_path.exists():
        console.print(f"[red]Error:[/red] File not found: {pdf_path}")
        raise typer.Exit(1)

    run_name = config.run_name or pdf_path.stem
    run_dir = output_dir / run_name
    paths = RunPaths(run_dir)

    # Handle existing run
    if run_dir.exists() and not resume and not force:
        console.print(
            f"[yellow]Warning:[/yellow] Output directory already exists: {run_dir}\n"
            "Use --resume to continue or --force to overwrite."
        )
        raise typer.Exit(1)

    paths.ensure_dirs()

    sha256 = sha256_file(pdf_path)
    document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, sha256))

    # Initialize or load state
    if paths.metadata.exists() and resume:
        state = RunState(paths.metadata)
        console.print(f"[blue]Resuming run:[/blue] {run_dir}")
    else:
        state = RunState.create(
            paths.metadata,
            document_id=document_id,
            filename=pdf_path.name,
            sha256=sha256,
            config=config.model_dump(mode="json"),
        )
        console.print(f"[green]Starting run:[/green] {run_dir}")

    # Save config
    write_json(paths.config, config.model_dump(mode="json"))

    t_start = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # Stage: PARSE
        if state.should_skip(Stage.PARSE, resume):
            console.print("[dim]Skipping parse (already completed)[/dim]")
        else:
            task = progress.add_task("Parsing PDF...", total=None)
            state.mark_in_progress(Stage.PARSE)
            try:
                pages_data = parse_pdf(pdf_path)
                write_json(paths.pages, pages_data)
                state.mark_completed(Stage.PARSE)
                progress.update(task, description=f"[green]Parsed {pages_data['total_pages']} pages[/green]")
            except Exception as e:
                state.mark_failed(Stage.PARSE, str(e))
                console.print(f"[red]Parse failed:[/red] {e}")
                raise typer.Exit(1)

        # Stage: CHUNK (section detection + chunking)
        if state.should_skip(Stage.CHUNK, resume):
            console.print("[dim]Skipping chunk (already completed)[/dim]")
        else:
            task = progress.add_task("Detecting sections and chunking...", total=None)
            state.mark_in_progress(Stage.CHUNK)
            try:
                pages_data = _load_pages(paths)
                sections = detect_sections(pages_data)
                write_json(paths.sections, sections)

                annotated_blocks = assign_section_to_blocks(pages_data, sections)
                chunks = chunk_blocks(
                    annotated_blocks,
                    document_id=document_id,
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap,
                    skip_references=config.skip_references,
                )
                write_jsonl(paths.chunks, chunks)

                # Placeholder outputs
                write_json(paths.figures, [])
                write_json(paths.tables, [])

                state.mark_completed(Stage.CHUNK)
                progress.update(
                    task,
                    description=f"[green]{len(sections)} sections, {len(chunks)} chunks[/green]",
                )
            except Exception as e:
                state.mark_failed(Stage.CHUNK, str(e))
                console.print(f"[red]Chunking failed:[/red] {e}")
                raise typer.Exit(1)

    elapsed = time.time() - t_start
    console.print(f"\n[bold green]Done[/bold green] in {elapsed:.1f}s → {run_dir}")
    return paths


def _load_pages(paths: RunPaths) -> dict:
    from paper_agent.utils.io import read_json
    return read_json(paths.pages)


def register(app: typer.Typer) -> None:
    """Register the parse command onto the given typer app."""

    @app.command()
    def parse(
        pdf: Path = typer.Argument(..., help="Path to the PDF file"),
        output: Path = typer.Option(Path("./runs"), "--output", "-o", help="Output directory"),
        run_name: Optional[str] = typer.Option(None, "--run-name", help="Custom run name"),
        parser: str = typer.Option("pymupdf", "--parser", help="PDF parser: pymupdf"),
        chunk_size: int = typer.Option(1200, "--chunk-size", help="Max characters per chunk"),
        chunk_overlap: int = typer.Option(150, "--chunk-overlap", help="Overlap between chunks"),
        section_aware: bool = typer.Option(True, "--section-aware/--no-section-aware"),
        skip_references: bool = typer.Option(False, "--skip-references", help="Skip references section"),
        resume: bool = typer.Option(False, "--resume", help="Resume from last successful stage"),
        force: bool = typer.Option(False, "--force", help="Overwrite existing output"),
        config_file: Optional[Path] = typer.Option(None, "--config", help="Config YAML file"),
        verbose: bool = typer.Option(False, "--verbose", "-v"),
        debug: bool = typer.Option(False, "--debug"),
    ) -> None:
        """Parse a PDF into pages, sections, and chunks. No LLM calls."""
        from paper_agent.utils.logging import configure_logging
        configure_logging(verbose=verbose, debug=debug)

        cfg = RunConfig.load(
            config_file=config_file,
            run_name=run_name,
            parser=parser,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            section_aware=section_aware,
            skip_references=skip_references,
            verbose=verbose,
            debug=debug,
        )

        run_parse(pdf, output, cfg, resume=resume, force=force)
