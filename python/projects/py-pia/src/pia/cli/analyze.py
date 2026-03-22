"""CLI commands for analyzing product releases."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from pia.services.analysis_service import AnalysisService
from pia.services.product_service import ProductService
from pia.services.release_service import ReleaseService

app = typer.Typer(help="Analyze product releases using LLM.")
console = Console()


def _require_api_key() -> None:
    """Abort with a helpful message if LLM_API_KEY is not configured."""
    from pia.config.settings import get_settings
    settings = get_settings()
    if not settings.llm_api_key:
        console.print(
            "[red]Error: LLM_API_KEY is not set.[/red]\n"
            "Add it to ~/.env:\n"
            "  LLM_API_KEY=sk-..."
        )
        raise typer.Exit(1)


def _get_product_and_release(
    product_id: str,
    version: str | None,
    product_svc: ProductService,
    release_svc: ReleaseService,
):
    """Resolve and validate product + release, printing errors and exiting on failure."""
    product = product_svc.get_product(product_id)
    if not product:
        console.print(
            f"[red]Product '{product_id}' not found.[/red]\n"
            f"Run: pia product list"
        )
        raise typer.Exit(1)

    if version is None:
        release = release_svc.get_latest(product_id)
        if not release:
            console.print(
                f"[red]No releases found for '{product_id}'.[/red]\n"
                f"Run: pia sync product {product_id}"
            )
            raise typer.Exit(1)
    else:
        release = release_svc.get_by_version(product_id, version)
        if not release:
            console.print(
                f"[red]Version '{version}' not found for '{product_id}'.[/red]\n"
                f"Run: pia versions list {product_id}"
            )
            raise typer.Exit(1)

    return product, release


@app.command("latest")
def analyze_latest(
    product_id: str = typer.Argument(..., help="Product ID"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model override"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass cache and re-analyze"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print report to terminal"),
) -> None:
    """Analyze the latest release of a product.

    Checks the report cache first. Use --force to regenerate.
    """
    _require_api_key()

    product_svc = ProductService()
    release_svc = ReleaseService()
    product, release = _get_product_and_release(product_id, None, product_svc, release_svc)

    console.print(
        f"Analyzing [bold cyan]{product.name}[/bold cyan] "
        f"version [bold]{release.version}[/bold]..."
    )

    svc = AnalysisService(model=model)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Running analysis pipeline...", total=None)
        try:
            report = asyncio.run(svc.analyze(product, release, force=force))
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            raise typer.Exit(1)

    from pia.config.settings import get_settings
    settings = get_settings()
    report_path = settings.reports_dir / product.id / f"{release.version}.md"

    console.print(f"\n[green]Report generated.[/green] Saved to: [dim]{report_path}[/dim]\n")

    if show:
        console.print(Markdown(report.content_md))


@app.command("version")
def analyze_version(
    product_id: str = typer.Argument(..., help="Product ID"),
    version: str = typer.Argument(..., help="Version string to analyze"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model override"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass cache and re-analyze"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print report to terminal"),
) -> None:
    """Analyze a specific version of a product.

    Checks the report cache first. Use --force to regenerate.

    Example:
        pia analyze version clickhouse 25.1.1
    """
    _require_api_key()

    product_svc = ProductService()
    release_svc = ReleaseService()
    product, release = _get_product_and_release(product_id, version, product_svc, release_svc)

    console.print(
        f"Analyzing [bold cyan]{product.name}[/bold cyan] "
        f"version [bold]{release.version}[/bold]..."
    )

    svc = AnalysisService(model=model)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Running analysis pipeline...", total=None)
        try:
            report = asyncio.run(svc.analyze(product, release, force=force))
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            raise typer.Exit(1)

    from pia.config.settings import get_settings
    settings = get_settings()
    report_path = settings.reports_dir / product.id / f"{release.version}.md"

    console.print(f"\n[green]Report generated.[/green] Saved to: [dim]{report_path}[/dim]\n")

    if show:
        console.print(Markdown(report.content_md))
