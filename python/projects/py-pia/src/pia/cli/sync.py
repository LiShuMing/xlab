"""CLI commands for syncing product releases."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from pia.exceptions import RateLimitError, ReleaseFetchError
from pia.services.product_service import ProductService
from pia.services.release_service import ReleaseService
from pia.telemetry import correlation_context

app = typer.Typer(help="Sync releases from product sources.")
console = Console()


@app.callback(invoke_without_command=True)
def sync(
    ctx: typer.Context,
    product_id: str = typer.Argument(..., help="Product ID, or 'all' to sync every product"),
) -> None:
    """Sync releases for one product (or all).

    Examples:

        pia sync duckdb

        pia sync all
    """
    if ctx.invoked_subcommand is not None:
        return

    product_svc = ProductService()
    release_svc = ReleaseService()

    if product_id.lower() == "all":
        products = product_svc.list_products()
        if not products:
            console.print("[yellow]No products found.[/yellow]")
            raise typer.Exit(0)
    else:
        product = product_svc.get_product(product_id)
        if not product:
            console.print(f"[red]Product '{product_id}' not found.[/red]")
            raise typer.Exit(1)
        products = [product]

    total_new = 0
    for product in products:
        with correlation_context():
            with Progress(
                SpinnerColumn(),
                TextColumn(f"Syncing [cyan]{product.name}[/cyan]..."),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("sync", total=None)
                try:
                    releases = asyncio.run(release_svc.sync_product(product))
                    console.print(
                        f"  [green]{product.name}[/green]: {len(releases)} releases fetched"
                    )
                    total_new += len(releases)
                except RateLimitError as e:
                    console.print(
                        f"  [red]{product.name}: GitHub rate limit exceeded.[/red]\n"
                        "  Add [cyan]GITHUB_TOKEN=ghp_...[/cyan] to ~/.env to raise the limit to 5000 req/hr.\n"
                        "  Get a token at: https://github.com/settings/tokens"
                    )
                except ReleaseFetchError as e:
                    console.print(f"  [red]{product.name}: sync failed — {e.message}[/red]")
                except Exception as e:
                    console.print(f"  [red]{product.name}: sync failed — {e}[/red]")

    console.print(f"\n[bold]Done.[/bold] Total releases fetched: {total_new}")
