"""Main CLI entry point for py-cli."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from py_cli.commands.analyze import analyze_command
from py_cli.commands.prompts import prompts_group
from py_cli.exceptions import PyCliError


@click.group()
@click.version_option(version="0.1.0", prog_name="py-cli")
def cli() -> None:
    """py-cli: LLM-powered Git repository code change analyzer.

    Generate structured technical reports from git commit history
    using Large Language Models.

    Examples:
        py-cli analyze                    # Analyze current repo
        py-cli analyze --repo /path/to/repo  # Analyze specific repo
        py-cli analyze --output report.md    # Custom output path
        py-cli prompts list               # List available prompts
    """
    pass


# Register commands
cli.add_command(analyze_command)
cli.add_command(prompts_group)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    try:
        cli()
        return 0
    except PyCliError as e:
        click.echo(f"Error: {e}", err=True)
        return 1
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
