"""Main entry point for the pia CLI application."""

from __future__ import annotations

import typer
from rich.console import Console

from pia.cli import analyze, digest, product, sync, versions
from pia.store.db import init_db

console = Console()

app = typer.Typer(
    name="pia",
    help=(
        "pia — Product Intelligence Agent\n\n"
        "Track official release notes for database and big-data products,\n"
        "analyze them with LLM, and build a persistent report library."
    ),
    no_args_is_help=True,
    add_completion=True,
)

app.add_typer(product.app, name="product", help="Manage tracked products.")
app.add_typer(sync.app, name="sync", help="Sync releases from product sources.")
app.add_typer(versions.app, name="versions", help="List versions for a product.")
app.add_typer(analyze.app, name="analyze", help="Analyze product releases with LLM.")
app.add_typer(digest.app, name="digest", help="Generate multi-product digest reports.")


def _startup() -> None:
    try:
        init_db()
        from pia.services.product_service import ProductService
        ProductService().sync_products_from_disk()
    except Exception as e:
        console.print(f"[yellow]Warning: startup failed: {e}[/yellow]")


def main() -> None:
    _startup()
    app()


if __name__ == "__main__":
    main()
