"""CLI interface for Daily DB Radar."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Optional
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
from dbradar.summarizer import summarize_items, Summarizer, SummaryResult
from dbradar.writer import write_html_report, write_reports
from dbradar.storage import DuckDBStore, StorageItem

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
    default=150,
    type=int,
    help="Maximum number of items to process",
)
@click.option(
    "--top-k",
    default=25,
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
@click.option(
    "--no-crawler",
    is_flag=True,
    default=False,
    help="Disable smart crawler for non-RSS sources.",
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
    no_crawler: bool,
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

    # Use smart crawler for non-RSS sources to avoid duplicates
    if not no_crawler:
        try:
            from dbradar.crawler_integration import extract_with_crawler, dedupe_extracted_items

            items = extract_with_crawler(results, enable_crawler=True)
            items = dedupe_extracted_items(items)
            click.echo(f"  Extracted {len(items)} items from web sources (with smart crawler)")
        except Exception as e:
            # Fallback to original extraction if crawler fails
            click.echo(f"  Crawler failed ({e}), falling back to standard extraction")
            items = extract_items(results)
            click.echo(f"  Extracted {len(items)} items from web sources")
    else:
        items = extract_items(results)
        click.echo(f"  Extracted {len(items)} items from web sources (crawler disabled)")

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

    # Always mark articles as seen (both incremental and full mode)
    if normalized:
        seen_tracker = get_seen_tracker()
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
    default=True,
    help="Only process new (unseen) articles (default: True)",
)
@click.option(
    "--full",
    "-f",
    is_flag=True,
    default=False,
    help="Process all articles, ignoring seen status (disables incremental)",
)
@click.pass_obj
def fetch(config: Config, days: int, no_cache: bool, language: str, incremental: bool, full: bool):
    """Fetch content from sources without generating summary."""
    # Get interests and use_feeds from context
    interests: Optional[InterestsConfig] = getattr(config, "_interests", None)
    use_feeds: bool = getattr(config, "_use_feeds", False)

    # --full flag disables incremental mode
    is_incremental = incremental and not full

    click.echo(f"Fetching sources (days={days}, incremental={is_incremental})...")

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
    if is_incremental:
        seen_tracker = get_seen_tracker()
        original_count = len(normalized)
        normalized = seen_tracker.filter_new(normalized)
        click.echo(f"New articles: {len(normalized)} / {original_count}")

    # Always mark articles as seen (both incremental and full mode)
    if normalized:
        seen_tracker = get_seen_tracker()
        seen_tracker.mark_seen_batch([
            {"url": item.url, "title": item.title, "published_at": item.published_at}
            for item in normalized
        ])

    ranked = rank_items(normalized, days=days, interests=interests)

    # Save to DuckDB storage
    click.echo("Saving to DuckDB storage...")
    store = DuckDBStore(config.output_dir.parent / "data")

    storage_items = []
    for r in ranked:
        # Parse published_at date
        pub_date = None
        if r.item.published_at:
            try:
                pub_date = datetime.fromisoformat(r.item.published_at.replace("Z", "+00:00")).date()
            except (ValueError, AttributeError):
                pass

        item = StorageItem(
            id=store._generate_id(r.item.url),
            url=r.item.url,
            title=r.item.title,
            original_title=r.item.title,  # Will be updated by summarizer
            published_date=pub_date,
            product=r.item.product,
            content_type=r.item.content_type if hasattr(r.item, 'content_type') else 'blog',
            summary="",  # Will be filled by summarizer
            tags=[],
            sources=r.item.sources if hasattr(r.item, 'sources') else [r.item.url],
        )
        storage_items.append(item)

    inserted = store.insert(storage_items)
    store.close()
    click.echo(f"  Saved {inserted} items to DuckDB")

    # Also save to JSON for backward compatibility
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
                    "new": is_incremental,
                }
                for r in ranked
            ],
            indent=2,
        )
    )
    click.echo(f"  Saved {len(ranked)} items to JSON (backup)")
    click.echo("")
    click.echo(f"Done! Fetched {len(ranked)} items.")


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
@click.option(
    "--days",
    default=30,
    type=int,
    help="Number of days to look back for bootstrap (default: 30)",
)
@click.option(
    "--max-items",
    default=500,
    type=int,
    help="Maximum number of items to collect",
)
@click.option(
    "--summarize-days",
    default=7,
    type=int,
    help="Only generate LLM summary for items within last N days (default: 7)",
)
@click.option(
    "--language",
    "-l",
    default="zh",
    type=click.Choice(["en", "zh"], case_sensitive=False),
    help="Output language (en=English, zh=中文)",
)
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Skip using cached content",
)
@click.pass_obj
def bootstrap(
    config: Config,
    days: int,
    max_items: int,
    summarize_days: int,
    language: str,
    no_cache: bool,
):
    """Bootstrap mode: collect all items without ranking, group by date.

    This mode is designed for initial content population:
    - Collects all items without score-based filtering
    - Groups items by their published date
    - Only generates LLM summaries for recent items (last N days)
    - Items without dates are placed in today's report
    """
    config.language = language.lower()

    # Get interests and use_feeds from context
    interests: Optional[InterestsConfig] = getattr(config, "_interests", None)
    use_feeds: bool = getattr(config, "_use_feeds", False)

    click.echo(f"Bootstrap Mode - Starting at {datetime.now(timezone.utc).isoformat()}")
    click.echo(f"  Days: {days}, Max items: {max_items}")
    click.echo(f"  LLM summary for last {summarize_days} days only")
    click.echo("")

    # Step 1: Load sources
    click.echo("Step 1: Loading sources...")
    if use_feeds:
        feeds = get_feeds()
        click.echo(f"  Found {len(feeds)} feed sources")
    else:
        sources = get_sources()
        click.echo(f"  Found {len(sources)} sources")
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

    # Step 3: Extract items
    click.echo("Step 3: Extracting items...")
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
            click.echo(f"  Added {len(enhanced_extracted)} items from enhanced sources")

    click.echo(f"  Total extracted: {len(items)} items")
    click.echo("")

    # Step 4: Normalize and deduplicate
    click.echo("Step 4: Normalizing and deduplicating...")
    normalized = normalize_items(items)
    click.echo(f"  After deduplication: {len(normalized)} unique items")
    click.echo("")

    # Step 5: Group items by date
    click.echo("Step 5: Grouping items by date...")
    from collections import defaultdict
    from datetime import timedelta

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=summarize_days)

    # Group items by their published date
    date_groups: Dict[str, List[NormalizedItem]] = defaultdict(list)
    no_date_items: List[NormalizedItem] = []

    for item in normalized:
        if item.published_at:
            try:
                dt = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                date_groups[date_str].append(item)
            except (ValueError, AttributeError):
                no_date_items.append(item)
        else:
            no_date_items.append(item)

    # Items without dates go to today
    if no_date_items:
        date_groups[today_str].extend(no_date_items)
        click.echo(f"  {len(no_date_items)} items without date -> placed in today ({today_str})")

    click.echo(f"  Grouped into {len(date_groups)} date files")
    for date_str in sorted(date_groups.keys(), reverse=True):
        click.echo(f"    {date_str}: {len(date_groups[date_str])} items")
    click.echo("")

    # Step 6: Generate reports for each date
    click.echo("Step 6: Generating reports by date...")

    from dbradar.summarizer import Summarizer, SummaryResult
    from dbradar.writer import Writer

    writer = Writer(config.output_dir, language=config.language)

    # Initialize summarizer (only used for recent items)
    summarizer = None
    if config.api_key:
        summarizer = Summarizer(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            language=config.language,
        )

    generated_dates = []
    for date_str in sorted(date_groups.keys(), reverse=True):
        items_for_date = date_groups[date_str]

        # Check if this date needs LLM summary
        try:
            date_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            needs_summary = (datetime.now(timezone.utc) - date_dt).days <= summarize_days
        except ValueError:
            needs_summary = False

        # Create ranked items (without actual ranking/scoring)
        ranked_items = []
        for i, item in enumerate(items_for_date):
            from dbradar.ranker import RankedItem
            ranked_items.append(
                RankedItem(
                    item=item,
                    score=0.5,  # Neutral score
                    rank=i + 1,
                    reasons=[],
                )
            )

        # Generate summary only for recent dates
        if needs_summary and summarizer:
            click.echo(f"  {date_str}: {len(items_for_date)} items - generating LLM summary...")
            try:
                summary = summarizer.summarize(ranked_items, top_k=min(25, len(ranked_items)))
            except Exception as e:
                click.echo(f"    Warning: LLM summary failed: {e}")
                # Fallback to empty summary
                summary = SummaryResult(
                    executive_summary=[f"Collected {len(items_for_date)} items"],
                    top_updates=[],
                    release_notes=[],
                    themes=[],
                    action_items=[],
                )
        else:
            click.echo(f"  {date_str}: {len(items_for_date)} items - links only (no LLM summary)")
            # Create a minimal summary with just the links
            summary = SummaryResult(
                executive_summary=[f"Collected {len(items_for_date)} items"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response="",
            )

        # Build top_updates from items (even without LLM summary)
        top_updates = []
        for item in items_for_date:
            update = {
                "product": item.product,
                "title": item.title,
                "what_changed": [],
                "why_it_matters": [],
                "sources": item.sources,
                "published_date": item.published_at,
            }
            top_updates.append(update)

        # Override summary top_updates with all items for bootstrap mode
        summary.top_updates = top_updates

        # Write report
        report = writer.write_report(
            summary=summary,
            ranked_items=ranked_items,
            fetch_failures=fetch_failures if date_str == today_str else [],
            date=date_str,
            interests=interests,
            write_html=False,
        )
        generated_dates.append(date_str)
        click.echo(f"    Written: {report[0].name}, {report[1].name}")

    if summarizer:
        summarizer.client.close()

    click.echo("")
    click.echo(f"Bootstrap complete! Generated {len(generated_dates)} date files:")
    for date_str in generated_dates[:5]:
        click.echo(f"  - {date_str}.json/md")
    if len(generated_dates) > 5:
        click.echo(f"  ... and {len(generated_dates) - 5} more")
    click.echo("")
    click.echo(f"Run 'dbradar serve' to view the results at http://localhost:5000")


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


# Sync command group
@cli.group()
def sync():
    """OSS sync commands for data synchronization between Mac and server."""
    pass


@sync.command("export")
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]),
    default=None,
    help="Export data since this date/time (default: last sync time)",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="data/sync",
    help="Output directory for sync files",
)
@click.pass_obj
def sync_export(config: Config, since: Optional[datetime], output_dir: Path):
    """Export incremental data to Parquet file (Mac side)."""
    from dbradar.sync import export_incremental
    from dbradar.storage import DuckDBStore

    store = DuckDBStore(Path("data"))

    try:
        parquet_path, metadata = export_incremental(
            store=store,
            since=since,
            output_dir=output_dir,
        )

        if metadata.item_count > 0:
            click.echo(f"Exported {metadata.item_count} items to {parquet_path}")
            click.echo(f"  File size: {metadata.file_size:,} bytes")
            click.echo(f"  Date range: {metadata.date_range}")
            click.echo(f"  Checksum: {metadata.checksum}")
        else:
            click.echo("No new data to export")

    finally:
        store.close()


@sync.command("push")
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]),
    default=None,
    help="Export data since this date/time (default: last sync time)",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="data/sync",
    help="Output directory for sync files",
)
@click.option(
    "--delete-local",
    is_flag=True,
    default=False,
    help="Delete local files after successful upload",
)
@click.pass_obj
def sync_push(config: Config, since: Optional[datetime], output_dir: Path, delete_local: bool):
    """Export and upload incremental data to OSS (Mac side)."""
    from dbradar.sync import export_incremental, upload_sync_file, update_sync_status
    from dbradar.storage import DuckDBStore

    store = DuckDBStore(Path("data"))

    try:
        # Export
        click.echo("Exporting incremental data...")
        parquet_path, metadata = export_incremental(
            store=store,
            since=since,
            output_dir=output_dir,
        )

        if metadata.item_count == 0:
            click.echo("No new data to push")
            return

        click.echo(f"Exported {metadata.item_count} items")

        # Upload to OSS
        click.echo("Uploading to OSS...")
        try:
            parquet_url, metadata_url = upload_sync_file(
                parquet_path=parquet_path,
                metadata=metadata,
                config=config,
                delete_local=delete_local,
            )
            click.echo(f"Uploaded to OSS:")
            click.echo(f"  Parquet: {parquet_url}")
            click.echo(f"  Metadata: {metadata_url}")

            # Update sync status
            update_sync_status(metadata)
            click.echo("Sync complete!")

        except ImportError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Install oss2: pip install oss2", err=True)
            raise click.Abort()
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Set OSS credentials via environment variables:", err=True)
            click.echo("  DB_RADAR_OSS_ACCESS_KEY_ID", err=True)
            click.echo("  DB_RADAR_OSS_ACCESS_KEY_SECRET", err=True)
            raise click.Abort()

    finally:
        store.close()


@sync.command("status")
def sync_status():
    """Show sync status (Mac side)."""
    from dbradar.sync import get_last_sync_time
    from dbradar.sync.models import SyncStatus

    last_sync = get_last_sync_time()
    status = SyncStatus.load(Path("data/sync_status.json"))

    click.echo("Sync Status:")
    if last_sync:
        click.echo(f"  Last sync: {last_sync.isoformat()}")
    else:
        click.echo("  Last sync: Never")
    click.echo(f"  Total syncs: {status.sync_count}")
    click.echo(f"  Total synced items: {status.total_synced_items:,}")
    if status.last_sync_file:
        click.echo(f"  Last sync file: {status.last_sync_file}")


@sync.command("pull")
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="data/sync/incoming",
    help="Directory to save downloaded files",
)
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    default=False,
    help="Download all available sync files, not just the latest",
)
@click.pass_obj
def sync_pull(config: Config, output_dir: Path, download_all: bool):
    """Download sync files from OSS (server side)."""
    from dbradar.sync import list_sync_files, download_sync_file

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        sync_files = list_sync_files(config)
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Install oss2: pip install oss2", err=True)
        raise click.Abort()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

    if not sync_files:
        click.echo("No sync files found in OSS")
        return

    click.echo(f"Found {len(sync_files)} sync file(s) in OSS")

    files_to_download = sync_files if download_all else sync_files[:1]

    for metadata in files_to_download:
        click.echo(f"\nDownloading {metadata.file_name}...")
        click.echo(f"  Exported at: {metadata.exported_at.isoformat()}")
        click.echo(f"  Items: {metadata.item_count}")

        parquet_path = download_sync_file(metadata, output_dir, config)
        if parquet_path:
            click.echo(f"  Saved to: {parquet_path}")
        else:
            click.echo(f"  Failed to download", err=True)


@sync.command("import")
@click.argument("parquet_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--metadata-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to metadata JSON file (optional)",
)
@click.option(
    "--delete-after",
    is_flag=True,
    default=False,
    help="Delete Parquet file after successful import",
)
def sync_import(parquet_file: Path, metadata_file: Optional[Path], delete_after: bool):
    """Import a sync file into DuckDB (server side)."""
    from dbradar.sync import import_incremental
    from dbradar.storage import DuckDBStore

    store = DuckDBStore(Path("data"))

    try:
        if metadata_file:
            from dbradar.sync.models import SyncMetadata
            metadata = SyncMetadata.load(metadata_file)
            count = import_incremental(store, parquet_file, metadata)
        else:
            from dbradar.sync.importer import import_from_parquet
            count = import_from_parquet(store, parquet_file, delete_after)

        click.echo(f"Successfully imported {count} items")

        if delete_after and metadata_file:
            metadata_file.unlink()
            click.echo(f"Deleted {metadata_file}")

    finally:
        store.close()


@sync.command("pull-import")
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="data/sync/incoming",
    help="Directory to save downloaded files",
)
@click.option(
    "--delete-after",
    is_flag=True,
    default=False,
    help="Delete files after successful import",
)
@click.pass_obj
def sync_pull_import(config: Config, output_dir: Path, delete_after: bool):
    """Pull latest sync file from OSS and import it (server side, one command)."""
    from dbradar.sync import (
        get_latest_sync_metadata,
        download_sync_file,
        import_incremental,
    )
    from dbradar.sync.importer import get_import_status
    from dbradar.storage import DuckDBStore

    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if we already have the latest
    import_status = get_import_status()

    try:
        latest = get_latest_sync_metadata(config)
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Install oss2: pip install oss2", err=True)
        raise click.Abort()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

    if not latest:
        click.echo("No sync files found in OSS")
        return

    # Check if already up to date
    if import_status.last_sync_at and latest.exported_at <= import_status.last_sync_at:
        click.echo("Already up to date")
        click.echo(f"  Last import: {import_status.last_sync_at.isoformat()}")
        click.echo(f"  Latest available: {latest.exported_at.isoformat()}")
        return

    click.echo(f"Found new sync: {latest.file_name}")
    click.echo(f"  Exported at: {latest.exported_at.isoformat()}")
    click.echo(f"  Items: {latest.item_count}")

    # Download
    click.echo("\nDownloading...")
    parquet_path = download_sync_file(latest, output_dir, config)
    if not parquet_path:
        click.echo("Download failed", err=True)
        raise click.Abort()
    click.echo(f"Downloaded to: {parquet_path}")

    # Import
    click.echo("\nImporting...")
    store = DuckDBStore(Path("data"))
    try:
        count = import_incremental(store, parquet_path, latest)
        click.echo(f"Imported {count} items")
    finally:
        store.close()

    # Cleanup
    if delete_after:
        parquet_path.unlink()
        click.echo(f"Deleted {parquet_path}")

    click.echo("\nPull-import complete!")


@sync.command("server-status")
def sync_server_status():
    """Show import status on server side."""
    from dbradar.sync.importer import get_import_status

    status = get_import_status()

    click.echo("Server Import Status:")
    if status.last_sync_at:
        click.echo(f"  Last import: {status.last_sync_at.isoformat()}")
    else:
        click.echo("  Last import: Never")
    click.echo(f"  Total imports: {status.sync_count}")
    click.echo(f"  Total imported items: {status.total_synced_items:,}")
    if status.last_sync_file:
        click.echo(f"  Last imported file: {status.last_sync_file}")


if __name__ == "__main__":
    cli()
