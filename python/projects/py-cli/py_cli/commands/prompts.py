"""Prompts management commands for py-cli."""

from __future__ import annotations

import click

from py_cli.llm.prompts import list_prompts


@click.group(name="prompts")
def prompts_group() -> None:
    """Manage prompt templates."""
    pass


@prompts_group.command(name="list")
def list_command() -> None:
    """List available prompt templates."""
    prompts = list_prompts()

    click.echo("Available prompt templates:")
    click.echo()

    for name in prompts:
        description = _get_prompt_description(name)
        click.echo(f"  {name:15} - {description}")


def _get_prompt_description(name: str) -> str:
    """Get description for a prompt template."""
    descriptions = {
        "default": "General purpose code change analysis",
        "clickhouse": "ClickHouse/database kernel specific analysis (Chinese output)",
    }
    return descriptions.get(name, "No description available")


@prompts_group.command(name="show")
@click.argument("name")
def show_command(name: str) -> None:
    """Show details of a prompt template."""
    from py_cli.llm.prompts import get_prompt, PromptNotFoundError

    try:
        prompt_module = get_prompt(name)
    except PromptNotFoundError as e:
        raise click.ClickException(str(e))

    click.echo(f"Prompt: {name}")
    click.echo()
    click.echo("System Prompt:")
    click.echo("-" * 40)
    click.echo(prompt_module.SYSTEM_PROMPT)
    click.echo()
    click.echo("User Prompt Template:")
    click.echo("-" * 40)
    click.echo(prompt_module.USER_PROMPT_TEMPLATE[:500] + "...")
