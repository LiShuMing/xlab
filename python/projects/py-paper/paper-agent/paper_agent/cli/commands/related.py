"""related command: related work expansion."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from paper_agent.utils.logging import configure_logging, set_correlation_id

console = Console()


def register(app: typer.Typer) -> None:
    """Register the related command with the CLI app."""

    @app.command()
    def related(
        run_dir: Path = typer.Argument(..., help="Path to run directory"),
        max_papers: int = typer.Option(10, "--max-papers"),
        verbose: bool = typer.Option(False, "--verbose", "-v"),
        debug: bool = typer.Option(False, "--debug"),
    ) -> None:
        """Find related work for an analyzed paper. [Stage 4]"""
        set_correlation_id()
        configure_logging(verbose=verbose, debug=debug)

        console.print(
            "[yellow]related command is not yet implemented (Stage 4).[/yellow]"
        )
        raise typer.Exit(0)
