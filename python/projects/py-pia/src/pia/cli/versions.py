"""CLI commands for listing product versions."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from pia.exceptions import ProductNotFoundError
from pia.services.product_service import ProductService
from pia.services.release_service import ReleaseService
from pia.store.repositories import ReportRepository

app = typer.Typer(help="List available versions for a product.")
console = Console()


@app.callback(invoke_without_command=True)
def versions(
    ctx: typer.Context,
    product_id: str = typer.Argument(..., help="Product ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum versions to show"),
) -> None:
    """Show available versions for a product with analysis status.

    Examples:

        pia versions duckdb

        pia versions clickhouse --limit 30
    """
    if ctx.invoked_subcommand is not None:
        return

    product_svc = ProductService()
    release_svc = ReleaseService()
    report_repo = ReportRepository()

    product = product_svc.get_product(product_id)
    if not product:
        console.print(f"[red]Product '{product_id}' not found.[/red]")
        raise typer.Exit(1)

    releases = release_svc.list_versions(product_id, limit=limit)
    if not releases:
        console.print(
            f"[yellow]No releases for '{product_id}'. Run: pia sync {product_id}[/yellow]"
        )
        raise typer.Exit(0)

    table = Table(title=f"{product.name} — Versions", show_lines=False)
    table.add_column("Version", style="cyan", no_wrap=True)
    table.add_column("Published", style="green")
    table.add_column("Source", overflow="fold")
    table.add_column("Analyzed", justify="center")

    for release in releases:
        published = (
            release.published_at.strftime("%Y-%m-%d") if release.published_at else "unknown"
        )
        analyzed = (
            "[green]Y[/green]"
            if report_repo.list_by_release(release.id)
            else "[dim]N[/dim]"
        )
        table.add_row(release.version, published, release.source_url, analyzed)

    console.print(table)
    console.print(f"\nTotal: {len(releases)} versions (limit={limit})")
