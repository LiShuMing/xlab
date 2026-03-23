"""CLI commands for generating multi-product digest reports."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from pia.config.settings import get_settings
from pia.exceptions import ConfigurationError
from pia.services.digest_service import DigestService
from pia.telemetry import correlation_context

app = typer.Typer(help="Generate multi-product digest reports.")
console = Console()


def _require_api_key() -> None:
    """Abort with a helpful message if LLM_API_KEY is not configured."""
    settings = get_settings()
    if not settings.llm_api_key:
        raise ConfigurationError(
            "LLM_API_KEY is not set.\nAdd it to ~/.env:\n  LLM_API_KEY=sk-..."
        )


def _parse_product_ids(products_str: str) -> list[str]:
    """Parse a comma-separated list of product IDs.

    Args:
        products_str: Comma-separated product ID string.

    Returns:
        List of stripped product ID strings.
    """
    return [p.strip() for p in products_str.split(",") if p.strip()]


@app.command("weekly")
def weekly_digest(
    products: str = typer.Option(
        ..., "--products", "-p", help="Comma-separated product IDs"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print report to terminal"),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o", help="Directory to save report (overrides default)"
    ),
) -> None:
    """Generate a weekly digest for the specified products.

    Example:
        pia digest weekly --products starrocks,clickhouse,duckdb
    """
    try:
        _require_api_key()
    except ConfigurationError as e:
        console.print(f"[red]{e.message}[/red]")
        raise typer.Exit(1)

    product_ids = _parse_product_ids(products)
    if not product_ids:
        console.print("[red]No product IDs provided.[/red]")
        raise typer.Exit(1)

    console.print(
        f"Generating [bold]weekly digest[/bold] for: {', '.join(product_ids)}"
    )

    svc = DigestService(model=model)

    with correlation_context():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Generating digest...", total=None)
            try:
                digest = asyncio.run(svc.generate_weekly_digest(product_ids))
            except Exception as e:
                console.print(f"[red]Digest generation failed: {e}[/red]")
                raise typer.Exit(1)

    settings = get_settings()
    filename = f"digest_weekly_{digest.id[:8]}.md"
    if output_dir:
        from pathlib import Path

        report_path = Path(output_dir).expanduser() / filename
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(digest.content_md, encoding="utf-8")
    else:
        report_path = settings.reports_dir / filename

    console.print(
        f"\n[green]Digest generated.[/green] Saved to: [dim]{report_path}[/dim]\n"
    )

    if show:
        console.print(Markdown(digest.content_md))


@app.command("monthly")
def monthly_digest(
    products: str = typer.Option(
        ..., "--products", "-p", help="Comma-separated product IDs"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print report to terminal"),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o", help="Directory to save report (overrides default)"
    ),
) -> None:
    """Generate a monthly digest for the specified products.

    Example:
        pia digest monthly --products starrocks,clickhouse,duckdb,doris,trino
    """
    try:
        _require_api_key()
    except ConfigurationError as e:
        console.print(f"[red]{e.message}[/red]")
        raise typer.Exit(1)

    product_ids = _parse_product_ids(products)
    if not product_ids:
        console.print("[red]No product IDs provided.[/red]")
        raise typer.Exit(1)

    console.print(
        f"Generating [bold]monthly digest[/bold] for: {', '.join(product_ids)}"
    )

    svc = DigestService(model=model)

    with correlation_context():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Generating digest...", total=None)
            try:
                digest = asyncio.run(svc.generate_monthly_digest(product_ids))
            except Exception as e:
                console.print(f"[red]Digest generation failed: {e}[/red]")
                raise typer.Exit(1)

    settings = get_settings()
    filename = f"digest_monthly_{digest.id[:8]}.md"
    if output_dir:
        from pathlib import Path

        report_path = Path(output_dir).expanduser() / filename
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(digest.content_md, encoding="utf-8")
    else:
        report_path = settings.reports_dir / filename

    console.print(
        f"\n[green]Digest generated.[/green] Saved to: [dim]{report_path}[/dim]\n"
    )

    if show:
        console.print(Markdown(digest.content_md))
