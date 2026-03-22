"""CLI commands for product catalog management."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from pia.services.product_service import ProductService

app = typer.Typer(help="Manage tracked products.")
console = Console()


@app.command("list")
def list_products() -> None:
    """List all tracked products."""
    from pia.config.loader import load_all_products
    svc = ProductService()
    # Load from disk to include sources count; fall back to DB
    products = load_all_products() or svc.list_products()

    if not products:
        console.print("[yellow]No products found. Check your products/ directory.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Tracked Products", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Category", style="green")
    table.add_column("Sources", justify="right")
    table.add_column("Homepage")

    for p in products:
        table.add_row(
            p.id,
            p.name,
            p.category,
            str(len(p.sources)),
            p.homepage,
        )

    console.print(table)


@app.command("show")
def show_product(product_id: str = typer.Argument(..., help="Product ID")) -> None:
    """Show detailed information for a product."""
    svc = ProductService()
    product = svc.get_product(product_id)

    if not product:
        console.print(f"[red]Product '{product_id}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]{product.name}[/bold cyan] ({product.id})")
    console.print(f"  Category:    {product.category}")
    console.print(f"  Homepage:    {product.homepage}")
    console.print(f"  Description: {product.description}")
    console.print(f"  Config:      {product.config_path or 'N/A'}")

    if product.sources:
        console.print("\n[bold]Sources:[/bold]")
        for s in product.sources:
            console.print(f"  [{s.priority:3d}] {s.type:20s} {s.url}")

    if product.analysis.competitor_set:
        console.print(f"\n[bold]Competitors:[/bold] {', '.join(product.analysis.competitor_set)}")

    if product.analysis.audience:
        console.print(f"[bold]Audience:[/bold]     {', '.join(product.analysis.audience)}")

    console.print(f"[bold]Prompt profile:[/bold] {product.analysis.prompt_profile}")


@app.command("add")
def add_product(
    config: Path = typer.Option(..., "--config", "-c", help="Path to product YAML config"),
) -> None:
    """Add a new product from a YAML config file."""
    if not config.exists():
        console.print(f"[red]Config file not found: {config}[/red]")
        raise typer.Exit(1)

    svc = ProductService()
    try:
        product = svc.add_product(config)
        console.print(f"[green]Added product:[/green] {product.name} ({product.id})")
    except Exception as e:
        console.print(f"[red]Failed to add product: {e}[/red]")
        raise typer.Exit(1)


@app.command("validate")
def validate_product(
    product_id: str = typer.Argument(..., help="Product ID to validate"),
) -> None:
    """Check that a product's source URLs are reachable."""
    svc = ProductService()
    product = svc.get_product(product_id)

    if not product:
        console.print(f"[red]Product '{product_id}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"Validating sources for [bold]{product.name}[/bold]...")
    results = svc.validate_product(product_id)

    all_ok = True
    for url, ok in results.items():
        status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"  {status}  {url}")
        if not ok:
            all_ok = False

    if not results:
        console.print("[yellow]No sources configured.[/yellow]")
    elif all_ok:
        console.print("[green]All sources reachable.[/green]")
    else:
        console.print("[yellow]Some sources are unreachable.[/yellow]")
        raise typer.Exit(1)
