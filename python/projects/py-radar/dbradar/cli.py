"""CLI interface for Daily DB Radar."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from dbradar.config import Config, get_config, set_config
from dbradar.enhanced_sources import get_enhanced_sources, validate_enhanced_sources
from dbradar.extractor import extract_items, extract_items_from_enhanced
from dbradar.feeds import FeedSource, get_feeds
from dbradar.fetcher import fetch_feeds, fetch_sources
from dbradar.interests import InterestsConfig
from dbradar.normalize import NormalizedItem, normalize_items
from dbradar.ranker import RankedItem, rank_items
from dbradar.seen_tracker import SeenTracker, get_seen_tracker
from dbradar.sources import get_sources
from dbradar.summarizer import summarize_items
from dbradar.writer import write_html_report, write_reports

# Intelligence module imports
from dbradar.intelligence import (
    AnalysisMode,
    AnalysisOptions,
    IntelligenceReport,
)
from dbradar.intelligence.agent import IntelligenceAgent


def _open_in_browser(path: Path) -> None:
    """
    Open a file in the default browser.

    Uses 'open' on macOS, 'xdg-open' on Linux. Silently skips if neither is available.
    """
    if shutil.which("open"):
        subprocess.run(["open", str(path)], check=False)
    elif shutil.which("xdg-open"):
        subprocess.run(["xdg-open", str(path)], check=False)


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
    default=None,
    help="Path to websites.txt (deprecated, use --feeds-file)",
)
@click.option(
    "--feeds-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to feeds.json (default: ./feeds.json if exists)",
)
@click.option(
    "--interests-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to interests.yaml (default: ./interests.yaml if exists)",
)
@click.pass_context
def cli(
    ctx: click.Context,
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
    cache_dir: Path,
    output_dir: Path,
    websites_file: Optional[Path],
    feeds_file: Optional[Path],
    interests_file: Optional[Path],
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
        feeds_file=feeds_file,
    )
    set_config(config)

    # Determine which source file to use
    # Priority: --feeds-file > --websites-file > ./feeds.json > ./websites.txt
    use_feeds = False
    if feeds_file:
        use_feeds = True
    elif websites_file:
        use_feeds = False
    else:
        # Auto-detect
        default_feeds_path = Path.cwd() / "feeds.json"
        if default_feeds_path.exists():
            use_feeds = True

    # Load interests configuration
    interests: Optional[InterestsConfig] = None
    if interests_file:
        interests = InterestsConfig.load(interests_file)
    else:
        # Auto-detect from current working directory
        default_interests_path = Path.cwd() / "interests.yaml"
        if default_interests_path.exists():
            interests = InterestsConfig.load(default_interests_path)

    ctx.obj = config
    ctx.obj._interests = interests  # type: ignore
    ctx.obj._use_feeds = use_feeds  # type: ignore


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
@click.option(
    "--html",
    is_flag=True,
    default=False,
    help="Generate HTML report in addition to Markdown and JSON",
)
@click.option(
    "--open",
    "-o",
    "open_browser",
    is_flag=True,
    default=False,
    help="Open HTML report in browser after generation (implies --html)",
)
@click.option(
    "--incremental",
    "-i",
    is_flag=True,
    default=False,
    help="Only process new (unseen) articles. Track seen articles in cache.",
)
@click.option(
    "--intelligence",
    is_flag=True,
    default=False,
    help="Enable full intelligence analysis (trends + competition).",
)
@click.option(
    "--trends",
    is_flag=True,
    default=False,
    help="Enable trend detection analysis.",
)
@click.option(
    "--analyze-competition",
    is_flag=True,
    default=False,
    help="Enable competitive analysis.",
)
@click.option(
    "--history-days",
    default=14,
    type=int,
    help="Days of history for trend analysis (default: 14).",
)
@click.pass_obj
def run(
    config: Config,
    days: int,
    max_items: int,
    top_k: int,
    no_cache: bool,
    language: str,
    html: bool,
    open_browser: bool,
    incremental: bool,
    intelligence: bool,
    trends: bool,
    analyze_competition: bool,
    history_days: int,
):
    """Run the complete pipeline: fetch, extract, summarize, and write reports.

    Intelligence modes:
    - Default: Basic summary only
    - --trends: Summary + trend detection
    - --analyze-competition: Summary + competitive analysis
    - --intelligence: Full intelligence (trends + competition)
    """
    # Set language in config
    config.language = language.lower()

    # Determine analysis mode
    if intelligence:
        mode = AnalysisMode.INTELLIGENCE
        mode_desc = "Intelligence (trends + competition)"
    elif trends and analyze_competition:
        mode = AnalysisMode.INTELLIGENCE
        mode_desc = "Intelligence (trends + competition)"
    elif trends:
        mode = AnalysisMode.TRENDS
        mode_desc = "Trends"
    elif analyze_competition:
        mode = AnalysisMode.COMPETITION
        mode_desc = "Competition"
    else:
        mode = AnalysisMode.BASIC
        mode_desc = "Basic"

    # Get interests and use_feeds from context
    interests: Optional[InterestsConfig] = getattr(config, "_interests", None)
    use_feeds: bool = getattr(config, "_use_feeds", False)

    # --open implies --html
    if open_browser:
        html = True

    click.echo(f"Daily DB Radar - Starting at {datetime.now(timezone.utc).isoformat()}")
    click.echo(f"  Days: {days}, Max items: {max_items}, Top-K: {top_k}")
    click.echo(f"  Mode: {'Incremental (new articles only)' if incremental else 'Full scan'}")
    click.echo(f"  Analysis: {mode_desc}")
    if mode != AnalysisMode.BASIC:
        click.echo(f"  History: {history_days} days for trend analysis")
    if use_feeds:
        click.echo(f"  Feeds file: {config.feeds_file}")
    else:
        click.echo(f"  Websites file: {config.website_file}")
    if interests:
        click.echo(f"  Interests: {len(interests.products)} products, {len(interests.keywords)} keywords")
    click.echo("")

    # Step 1: Load sources
    click.echo("Step 1: Loading sources...")
    if use_feeds:
        feeds = get_feeds()
        click.echo(f"  Found {len(feeds)} feed sources")
        for f in feeds[:5]:
            filter_info = f" (filter: {', '.join(f.filter_tags)})" if f.filter_tags else ""
            click.echo(f"    - {f.title}{filter_info}")
        if len(feeds) > 5:
            click.echo(f"    ... and {len(feeds) - 5} more")
    else:
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
    if use_feeds:
        results = fetch_feeds(feeds, use_cache=not no_cache)
    else:
        results = fetch_sources(sources, use_cache=not no_cache)
    success_count = sum(1 for r in results if r.status_code and r.status_code < 400)
    click.echo(f"  Fetched {success_count}/{len(results)} sources successfully")
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
        if use_feeds:
            products = [f.title for f in feeds]
        else:
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

    # Step 4b: Filter to new articles (incremental mode)
    if incremental:
        click.echo("Step 4b: Filtering to new articles...")
        seen_tracker = get_seen_tracker()
        original_count = len(normalized)
        normalized = seen_tracker.filter_new(normalized)
        click.echo(f"  New articles: {len(normalized)} / {original_count}")
        # Mark all seen articles to update their last_seen timestamp
        if normalized:
            seen_tracker.mark_seen_batch([
                {"url": item.url, "title": item.title, "published_at": item.published_at}
                for item in normalized
            ])
    click.echo("")

    # Step 5: Rank items
    click.echo("Step 5: Ranking items...")
    ranked = rank_items(normalized, days=days, max_items=max_items, interests=interests)
    boosted_count = sum(1 for r in ranked if r.boosted)
    click.echo(f"  Ranked {len(ranked)} items ({boosted_count} boosted)")
    click.echo("")

    # Step 6: Generate summary with intelligence analysis
    click.echo("Step 6: Generating summary with LLM...")

    # Initialize intelligence data containers
    report_trends = None
    report_competition = None

    if mode == AnalysisMode.BASIC:
        # Basic mode: use existing summarizer directly
        from dbradar.summarizer import Summarizer
        summarizer = Summarizer(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            language=config.language,
        )
        summary = summarizer.summarize(ranked, top_k=top_k)
        summarizer.client.close()

        click.echo(f"  Executive summary: {len(summary.executive_summary)} bullets")
        click.echo(f"  Top updates: {len(summary.top_updates)} items")
        click.echo(f"  Themes: {len(summary.themes)} items")
        click.echo(f"  Action items: {len(summary.action_items)} items")
    else:
        # Intelligence mode: use IntelligenceAgent
        agent = IntelligenceAgent(config=config)
        options = AnalysisOptions(
            mode=mode,
            top_k=top_k,
            history_days=history_days,
            enable_trends=mode in (AnalysisMode.TRENDS, AnalysisMode.INTELLIGENCE),
            enable_competition=mode in (AnalysisMode.COMPETITION, AnalysisMode.INTELLIGENCE),
        )
        intel_report = agent.analyze(ranked, options)
        agent.close()

        click.echo(f"  Executive summary: {len(intel_report.executive_summary)} bullets")
        click.echo(f"  Top updates: {len(intel_report.top_updates)} items")
        click.echo(f"  Themes: {len(intel_report.themes)} items")
        click.echo(f"  Action items: {len(intel_report.action_items)} items")
        click.echo(f"  Tools used: {', '.join(intel_report.tools_used)}")

        # Extract intelligence data for report
        report_trends = intel_report.trends
        report_competition = intel_report.competition

        # Convert IntelligenceReport to summary-compatible format for writer
        # The writer expects a SummaryResult, so we create a wrapper
        from dbradar.summarizer import SummaryResult
        summary = SummaryResult(
            executive_summary=intel_report.executive_summary,
            top_updates=intel_report.top_updates,
            release_notes=intel_report.release_notes,
            themes=intel_report.themes,
            action_items=intel_report.action_items,
        )
    click.echo("")

    # Step 7: Write reports
    click.echo("Step 7: Writing reports...")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    from dbradar.writer import Writer
    writer = Writer(config.output_dir, language=config.language)

    report = writer.write_report(
        summary=summary,
        ranked_items=ranked,
        fetch_failures=fetch_failures,
        date=date_str,
        interests=interests,
        write_html=html,
        trends=report_trends,
        competition=report_competition,
    )
    md_path, json_path, html_path = report

    click.echo(f"  Markdown: {md_path}")
    click.echo(f"  JSON: {json_path}")
    if html_path:
        click.echo(f"  HTML: {html_path}")
    click.echo("")

    # Open in browser if requested
    if open_browser and html_path:
        _open_in_browser(html_path)

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
@click.option(
    "--incremental",
    "-i",
    is_flag=True,
    default=False,
    help="Only process new (unseen) articles",
)
@click.pass_obj
def fetch(config: Config, days: int, no_cache: bool, language: str, incremental: bool):
    """Fetch content from sources without generating summary."""
    # Get interests and use_feeds from context
    interests: Optional[InterestsConfig] = getattr(config, "_interests", None)
    use_feeds: bool = getattr(config, "_use_feeds", False)

    click.echo(f"Fetching sources (days={days}, incremental={incremental})...")

    if use_feeds:
        feeds = get_feeds()
        results = fetch_feeds(feeds, use_cache=not no_cache)
        click.echo(f"Found {len(feeds)} feed sources")
    else:
        sources = get_sources()
        results = fetch_sources(sources, use_cache=not no_cache)

    success_count = sum(1 for r in results if r.status_code and r.status_code < 400)
    click.echo(f"Fetched {success_count}/{len(results)} sources successfully")

    # Extract and save raw items
    items = extract_items(results)

    # Fetch from enhanced sources
    enhanced_mgr = get_enhanced_sources()
    configured = enhanced_mgr.get_configured_sources()
    if configured:
        if use_feeds:
            products = [f.title for f in feeds]
        else:
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

    # Filter to new articles (incremental mode)
    if incremental:
        seen_tracker = get_seen_tracker()
        original_count = len(normalized)
        normalized = seen_tracker.filter_new(normalized)
        click.echo(f"New articles: {len(normalized)} / {original_count}")
        # Mark all new articles as seen
        if normalized:
            seen_tracker.mark_seen_batch([
                {"url": item.url, "title": item.title, "published_at": item.published_at}
                for item in normalized
            ])

    ranked = rank_items(normalized, days=days, interests=interests)

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
                    "new": incremental,
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


@cli.command()
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind the server to",
)
@click.option(
    "--port",
    default=5000,
    type=int,
    help="Port to bind the server to",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug mode",
)
def serve(host: str, port: int, debug: bool):
    """Start the web server to view reports in browser.

    The server serves the latest generated report as a web page.
    Access it at http://localhost:PORT

    API endpoints:
    - /api/news - Get latest news as JSON
    - /api/history - Get list of historical reports
    - /api/report/<date> - Get specific report by date
    """
    from dbradar.server import run_server

    click.echo(f"Starting DB Radar web server...")
    click.echo(f"  URL: http://{host}:{port}")
    click.echo(f"  API: http://{host}:{port}/api/news")
    click.echo("")
    click.echo("Press Ctrl+C to stop")
    click.echo("")

    run_server(host=host, port=port, debug=debug)


if __name__ == "__main__":
    cli()
