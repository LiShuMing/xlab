"""related command: related work expansion."""

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:

    @app.command()
    def related(
        run_dir: str = typer.Argument(..., help="Path to run directory"),
        max_papers: int = typer.Option(10, "--max-papers"),
    ) -> None:
        """Find related work for an analyzed paper. [Stage 4]"""
        console.print("[yellow]related command is not yet implemented (Stage 4).[/yellow]")
        raise typer.Exit(0)
