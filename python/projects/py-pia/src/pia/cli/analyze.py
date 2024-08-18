"""CLI commands for analyzing product releases."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from pia.config.settings import get_settings
from pia.exceptions import (
    ConfigurationError,
    ProductNotFoundError,
    ReleaseNotFoundError,
)
from pia.services.analysis_service import AnalysisService
from pia.services.product_service import ProductService
from pia.services.release_service import ReleaseService
from pia.telemetry import correlation_context

app = typer.Typer(help="Analyze product releases using LLM.")
console = Console()


def _require_api_key() -> None:
    """Abort with a helpful message if LLM_API_KEY is not configured."""
    settings = get_settings()
    if not settings.llm_api_key:
        raise ConfigurationError(
            "LLM_API_KEY is not set.\nAdd it to ~/.env:\n  LLM_API_KEY=sk-..."
        )


def _get_product_and_release(
    product_id: str,
    version: str | None,
    product_svc: ProductService,
    release_svc: ReleaseService,
) -> tuple[ProductService, ReleaseService]:
    """Resolve and validate product + release."""
    from pia.models.product import Product
    from pia.models.release import Release

    product = product_svc.get_product(product_id)
    if not product:
        raise ProductNotFoundError(product_id)

    if version is None:
        release = release_svc.get_latest(product_id)
        if not release:
            raise ReleaseNotFoundError(product_id)
    else:
        release = release_svc.get_by_version(product_id, version)
        if not release:
            raise ReleaseNotFoundError(product_id, version)

    return product, release  # type: ignore[return-value]


@app.command("latest")
def analyze_latest(
    product_id: str = typer.Argument(..., help="Product ID"),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass cache and re-analyze"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print report to terminal"),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o", help="Directory to save report (overrides default)"
    ),
) -> None:
    """Analyze the latest release of a product.

    Checks the report cache first. Use --force to regenerate.
    """
    try:
        _require_api_key()
    except ConfigurationError as e:
        console.print(f"[red]{e.message}[/red]")
        raise typer.Exit(1)

    product_svc = ProductService()
    release_svc = ReleaseService()

    try:
        product, release = _get_product_and_release(
            product_id, None, product_svc, release_svc
        )
    except ProductNotFoundError as e:
        console.print(f"[red]Product '{e.product_id}' not found.[/red]\nRun: pia product list")
        raise typer.Exit(1)
    except ReleaseNotFoundError:
        console.print(
            f"[red]No releases found for '{product_id}'.[/red]\nRun: pia sync {product_id}"
        )
        raise typer.Exit(1)

    console.print(
        f"Analyzing [bold cyan]{product.name}[/bold cyan] "
        f"version [bold]{release.version}[/bold]..."
    )

    svc = AnalysisService(model=model)

    with correlation_context():
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

    settings = get_settings()
    if output_dir:
        report_path = Path(output_dir).expanduser() / f"{product.id}_{release.version}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.content_md, encoding="utf-8")
    else:
        report_path = settings.reports_dir / product.id / f"{release.version}.md"

    console.print(
        f"\n[green]Report generated.[/green] Saved to: [dim]{report_path}[/dim]\n"
    )

    if show:
        console.print(Markdown(report.content_md))


@app.command("version")
def analyze_version(
    product_id: str = typer.Argument(..., help="Product ID"),
    version: str = typer.Argument(..., help="Version string to analyze"),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass cache and re-analyze"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print report to terminal"),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o", help="Directory to save report (overrides default)"
    ),
) -> None:
    """Analyze a specific version of a product.

    Checks the report cache first. Use --force to regenerate.

    Example:
        pia analyze version clickhouse 25.1.1
    """
    try:
        _require_api_key()
    except ConfigurationError as e:
        console.print(f"[red]{e.message}[/red]")
        raise typer.Exit(1)

    product_svc = ProductService()
    release_svc = ReleaseService()

    try:
        product, release = _get_product_and_release(
            product_id, version, product_svc, release_svc
        )
    except ProductNotFoundError as e:
        console.print(f"[red]Product '{e.product_id}' not found.[/red]\nRun: pia product list")
        raise typer.Exit(1)
    except ReleaseNotFoundError as e:
        console.print(
            f"[red]Version '{e.version}' not found for '{e.product_id}'.[/red]\n"
            f"Run: pia versions list {e.product_id}"
        )
        raise typer.Exit(1)

    console.print(
        f"Analyzing [bold cyan]{product.name}[/bold cyan] "
        f"version [bold]{release.version}[/bold]..."
    )

    svc = AnalysisService(model=model)

    with correlation_context():
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

    settings = get_settings()
    if output_dir:
        report_path = Path(output_dir).expanduser() / f"{product.id}_{release.version}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.content_md, encoding="utf-8")
    else:
        report_path = settings.reports_dir / product.id / f"{release.version}.md"

    console.print(
        f"\n[green]Report generated.[/green] Saved to: [dim]{report_path}[/dim]\n"
    )

    if show:
        console.print(Markdown(report.content_md))
