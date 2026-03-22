"""CLI interface for Daily DB Radar."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from dbradar.config import Config, get_config, set_config
from dbradar.enhanced_sources import get_enhanced_sources, validate_enhanced_sources
from dbradar.extractor import extract_items, extract_items_from_enhanced
from dbradar.fetcher import fetch_sources
from dbradar.normalize import NormalizedItem, normalize_items
from dbradar.ranker import RankedItem, rank_items
from dbradar.sources import get_sources
from dbradar.summarizer import summarize_items
from dbradar.writer import write_reports


@click.group()
@click.option(
    "--api-key",
    envvar="LLM_API_KEY",
    help="LLM API key (or set LLM_API_KEY env var, or in ~/.env)",
)
@click.option(
    "--base-url",
    envvar="LLM_BASE_URL",
    help="LLM API base URL (or set LLM_BASE_URL env var, or in ~/.env)",
)
@click.option(
    "--model",
    envvar="LLM_MODEL",
    help="LLM model name (or set LLM_MODEL env var, or in ~/.env)",
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
    model: Optional[str],
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
        model=model,
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
@click.option(
    "--language",
    "-l",
    default="en",
    type=click.Choice(["en", "zh"], case_sensitive=False),
    help="Output language (en=English, zh=中文)",
)
@click.pass_obj
def run(
    config: Config,
    days: int,
    max_items: int,
    top_k: int,
    no_cache: bool,
    language: str,
):
    """Run the complete pipeline: fetch, extract, summarize, and write reports."""
    # Set language in config
    config.language = language.lower()
    
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

    # Step 3: Extract items from web sources
    click.echo("Step 3: Extracting items...")
    items = extract_items(results)
    click.echo(f"  Extracted {len(items)} items from web sources")
    
    # Step 3b: Fetch from enhanced sources (Google Search, NewsAPI)
    click.echo("Step 3b: Fetching from enhanced sources...")
    enhanced_mgr = get_enhanced_sources()
    configured = enhanced_mgr.get_configured_sources()
    if configured:
        click.echo(f"  Configured sources: {', '.join(configured)}")
        products = [s.product for s in sources]
        enhanced_items = enhanced_mgr.fetch_all(
            products=products,
            days=days,
            max_items_per_source=20,
        )
        enhanced_mgr.close()
        if enhanced_items:
            enhanced_extracted = extract_items_from_enhanced(enhanced_items)
            items.extend(enhanced_extracted)
            click.echo(f"  Added {len(enhanced_extracted)} items from enhanced sources")
    else:
        click.echo("  No enhanced sources configured (set GOOGLE_API_KEY + GOOGLE_CX or NEWSAPI_KEY)")
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
    click.echo("Step 6: Generating summary with LLM...")
    summary = summarize_items(ranked, top_k=top_k, language=config.language)
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
        language=config.language,
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
@click.option(
    "--language",
    "-l",
    default="en",
    type=click.Choice(["en", "zh"], case_sensitive=False),
    help="Output language (en=English, zh=中文)",
)
@click.pass_obj
def fetch(config: Config, days: int, no_cache: bool, language: str):
    """Fetch content from sources without generating summary."""
    click.echo(f"Fetching sources (days={days}, cache=not {no_cache})...")

    sources = get_sources()
    results = fetch_sources(sources, use_cache=not no_cache)

    success_count = sum(1 for r in results if r.status_code and r.status_code < 400)
    click.echo(f"Fetched {success_count}/{len(results)} URLs successfully")

    # Extract and save raw items
    items = extract_items(results)
    
    # Fetch from enhanced sources
    enhanced_mgr = get_enhanced_sources()
    configured = enhanced_mgr.get_configured_sources()
    if configured:
        products = [s.product for s in sources]
        enhanced_items = enhanced_mgr.fetch_all(
            products=products,
            days=days,
            max_items_per_source=20,
        )
        enhanced_mgr.close()
        if enhanced_items:
            enhanced_extracted = extract_items_from_enhanced(enhanced_items)
            items.extend(enhanced_extracted)
            click.echo(f"Added {len(enhanced_extracted)} items from enhanced sources ({', '.join(configured)})")
    
    normalized = normalize_items(items)
    ranked = rank_items(normalized, days=days)

    output_file = config.output_dir / "fetched_items.json"
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
@click.option(
    "--language",
    "-l",
    default="en",
    type=click.Choice(["en", "zh"], case_sensitive=False),
    help="Output language (en=English, zh=中文)",
)
@click.pass_obj
def summarize(config: Config, date: Optional[str], top_k: int, language: str):
    """Generate summary from previously fetched data."""
    config.language = language.lower()
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    input_file = config.output_dir / "fetched_items.json"

    if not input_file.exists():
        click.echo("Error: No fetched data found. Run 'fetch' first.", err=True)
        return

    data = json.loads(input_file.read_text())

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

    summary = summarize_items(ranked, top_k=top_k, language=config.language)

    # Write report
    md_path, json_path = write_reports(
        summary=summary,
        ranked_items=ranked,
        fetch_failures=[],
        output_dir=config.output_dir,
        date=date,
        language=config.language,
    )

    click.echo(f"Summary written to:")
    click.echo(f"  Markdown: {md_path}")
    click.echo(f"  JSON: {json_path}")


@cli.command()
@click.pass_obj
def check(config: Config):
    """Check configuration and API connectivity."""
    click.echo("=" * 50)
    click.echo("Configuration Check")
    click.echo("=" * 50)
    click.echo("")
    
    # Check LLM config
    click.echo("LLM Configuration:")
    if config.api_key:
        click.echo(f"  ✓ LLM_API_KEY: {'*' * 10}{config.api_key[-4:]}")
    else:
        click.echo("  ✗ LLM_API_KEY: NOT SET (required)")
    click.echo(f"  → LLM_BASE_URL: {config.base_url or 'default'}")
    click.echo(f"  → LLM_MODEL: {config.model}")
    click.echo("")
    
    # Check enhanced sources
    click.echo("Enhanced Data Sources:")
    results = validate_enhanced_sources()
    
    for source, (is_valid, message) in results.items():
        status = "✓" if is_valid else "✗"
        click.echo(f"  {status} {source}: {message}")
    
    click.echo("")
    click.echo("-" * 50)
    
    # Summary
    all_valid = all(valid for valid, _ in results.values())
    if config.api_key and all_valid:
        click.echo("Status: All systems ready ✓")
    elif config.api_key:
        click.echo("Status: LLM ready, enhanced sources optional")
    else:
        click.echo("Status: LLM API key required!")
        raise click.Abort()


if __name__ == "__main__":
    cli()
