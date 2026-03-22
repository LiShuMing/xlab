"""paper-agent CLI entry point."""

import typer
from rich.console import Console

from paper_agent.cli.commands import analyze, ask, parse, related, report

app = typer.Typer(
    name="paper-agent",
    help="A CLI tool for reading and analyzing academic papers.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

# Register all subcommands
parse.register(app)
analyze.register(app)
ask.register(app)
report.register(app)
related.register(app)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit."),
) -> None:
    """[bold]paper-agent[/bold] - Academic paper reading and analysis tool."""
    if version:
        from paper_agent import __version__
        console.print(f"paper-agent {__version__}")
        raise typer.Exit()
