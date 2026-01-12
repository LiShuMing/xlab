"""CLI interface for Daily DB Radar."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from dbradar.config import Config, get_config, set_config
from dbradar.extractor import extract_items
from dbradar.fetcher import fetch_sources
from dbradar.normalize import normalize_items
from dbradar.ranker import rank_items
from dbradar.sources import get_sources
from dbradar.summarizer import summarize_items
from dbradar.writer import write_reports


@click.group()
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
)
@click.option(
    "--base-url",
    envvar="ANTHROPIC_BASE_URL",
    help="Anthropic API base URL (optional)",
)
@click.option(
    "--cache-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="cache",
    help="Cache directory",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="out",
    help="Output directory",
)
@click.option(
    "--websites-file",
    type=click.Path(exists=True, path_type=Path),
    default="websites.txt",
    help="Path to websites.txt",
)
@click.pass_context
def cli(
    ctx: click.Context,
    api_key: Optional[str],
    base_url: Optional[str],
    cache_dir: Path,
    output_dir: Path,
    websites_file: Path,
):
    """Daily DB Radar - Collect and summarize DB/OLAP industry updates."""
    # Ensure output directories exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up config
    config = Config(
        api_key=api_key,
        base_url=base_url,
        cache_dir=cache_dir,
        output_dir=output_dir,
        website_file=websites_file,
    )
    set_config(config)
    ctx.obj = config


@cli.command()
@click.option(
    "--days",
    default=7,
    type=int,
    help="Number of days to look back for updates",
)
@click.option(
    "--max-items",
    default=80,
    type=int,
    help="Maximum number of items to process",
)
@click.option(
    "--top-k",
    default=10,
    type=int,
    help="Number of top items to include in summary",
)
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Skip using cached content, fetch fresh from all sources",
)
@click.pass_obj
def run(
    config: Config,
    days: int,
    max_items: int,
    top_k: int,
    no_cache: bool,
):
    """Run the complete pipeline: fetch, extract, summarize, and write reports."""
    click.echo(f"Daily DB Radar - Starting at {datetime.now(timezone.utc).isoformat()}")
    click.echo(f"  Days: {days}, Max items: {max_items}, Top-K: {top_k}")
    click.echo(f"  Websites file: {config.website_file}")
    click.echo("")

    # Step 1: Load sources
    click.echo("Step 1: Loading sources...")
    sources = get_sources()
    click.echo(f"  Found {len(sources)} sources")
    for s in sources[:5]:
        click.echo(f"    - {s.product}: {len(s.urls)} URLs")
    if len(sources) > 5:
        click.echo(f"    ... and {len(sources) - 5} more")
    click.echo("")

    # Step 2: Fetch content
    click.echo("Step 2: Fetching content...")
    fetch_failures = []
    results = fetch_sources(sources, use_cache=not no_cache)
    success_count = sum(1 for r in results if r.status_code and r.status_code < 400)
    click.echo(f"  Fetched {success_count}/{len(results)} URLs successfully")
    for r in results:
        if r.status_code and r.status_code >= 400:
            fetch_failures.append({"url": r.url, "reason": f"HTTP {r.status_code}"})
        elif r.error_message:
            fetch_failures.append({"url": r.url, "reason": r.error_message})
    click.echo(f"  {len(fetch_failures)} failures")
    click.echo("")

    # Step 3: Extract items
    click.echo("Step 3: Extracting items...")
    items = extract_items(results)
    click.echo(f"  Extracted {len(items)} items")
    click.echo("")

    # Step 4: Normalize and deduplicate
    click.echo("Step 4: Normalizing and deduplicating...")
    normalized = normalize_items(items)
    click.echo(f"  After deduplication: {len(normalized)} unique items")
    click.echo("")

    # Step 5: Rank items
    click.echo("Step 5: Ranking items...")
    ranked = rank_items(normalized, days=days, max_items=max_items)
    click.echo(f"  Ranked {len(ranked)} items")
    click.echo("")

    # Step 6: Generate summary
    click.echo("Step 6: Generating summary with Anthropic...")
    summary = summarize_items(ranked, top_k=top_k)
    click.echo(f"  Executive summary: {len(summary.executive_summary)} bullets")
    click.echo(f"  Top updates: {len(summary.top_updates)} items")
    click.echo(f"  Themes: {len(summary.themes)} items")
    click.echo(f"  Action items: {len(summary.action_items)} items")
    click.echo("")

    # Step 7: Write reports
    click.echo("Step 7: Writing reports...")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md_path, json_path = write_reports(
        summary=summary,
        ranked_items=ranked,
        fetch_failures=fetch_failures,
        output_dir=config.output_dir,
        date=date_str,
    )
    click.echo(f"  Markdown: {md_path}")
    click.echo(f"  JSON: {json_path}")
    click.echo("")

    click.echo(f"Done! Report written to {config.output_dir}/")


@cli.command()
@click.option(
    "--days",
    default=7,
    type=int,
    help="Number of days to look back",
)
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Skip using cached content",
)
@click.pass_obj
def fetch(config: Config, days: int, no_cache: bool):
    """Fetch content from sources without generating summary."""
    click.echo(f"Fetching sources (days={days}, cache=not {no_cache})...")

    sources = get_sources()
    results = fetch_sources(sources, use_cache=not no_cache)

    success_count = sum(1 for r in results if r.status_code and r.status_code < 400)
    click.echo(f"Fetched {success_count}/{len(results)} URLs successfully")

    # Extract and save raw items
    items = extract_items(results)
    normalized = normalize_items(items)
    ranked = rank_items(normalized, days=days)

    output_file = config.output_dir / "fetched_items.json"
    import json
    output_file.write_text(
        json.dumps(
            [
                {
                    "product": r.item.product,
                    "title": r.item.title,
                    "url": r.item.url,
                    "date": r.item.published_at,
                    "score": r.score,
                }
                for r in ranked
            ],
            indent=2,
        )
    )
    click.echo(f"Saved {len(ranked)} items to {output_file}")


@cli.command()
@click.argument("date", required=False)
@click.option(
    "--top-k",
    default=10,
    type=int,
    help="Number of top items to summarize",
)
@click.pass_obj
def summarize(config: Config, date: Optional[str], top_k: int):
    """Generate summary from previously fetched data."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    input_file = config.output_dir / "fetched_items.json"

    if not input_file.exists():
        click.echo(f"Error: No fetched data found. Run 'fetch' first.", err=True)
        return

    import json

    data = json.loads(input_file.read_text())

    # Convert to RankedItem format
    from dbradar.ranker import Ranker, RankedItem
    from dbradar.normalize import NormalizedItem, Normalizer

    ranked = []
    for i, item in enumerate(data):
        norm = NormalizedItem(
            url=item["url"],
            product=item["product"],
            title=item["title"],
            content="",
            published_at=item.get("date"),
            normalized_title=item["title"].lower(),
            domain="",
            date_hash="unknown",
            content_type="other",
            confidence=0.5,
            sources=[item["url"]],
            snippets=[],
        )
        ranked.append(
            RankedItem(
                item=norm,
                score=item.get("score", 0.5),
                rank=i + 1,
                reasons=[],
            )
        )

    summary = summarize_items(ranked, top_k=top_k)

    # Write report
    md_path, json_path = write_reports(
        summary=summary,
        ranked_items=ranked,
        fetch_failures=[],
        output_dir=config.output_dir,
        date=date,
    )

    click.echo(f"Summary written to:")
    click.echo(f"  Markdown: {md_path}")
    click.echo(f"  JSON: {json_path}")


if __name__ == "__main__":
    cli()
