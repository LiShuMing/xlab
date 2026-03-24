# Changelogs

All notable changes to this project will be documented in this file.

## [2026-03-24] - Web UI Enhancement & Incremental Mode

### Added

#### Web UI Redesign (`dbradar/web/templates/index.html`)
- **Date-grouped layout**: News organized by date (今天/昨天/3月22日 周日)
- **Pagination**: Each page shows 3 days, with navigation controls
- **Hacker News style**: Orange header, clean link list design
- **Rich link display**:
  - Chinese title with original English title below
  - Content type tags (发布/基准测试/博客/新闻/教程)
  - Product tags and technology tags
  - Summary excerpt (up to 600 characters)
  - Additional sources indicator

#### Server Updates (`dbradar/server.py`)
- **Pagination support**: `/page/<n>` routes for browsing historical reports
- **Date display**: "今天", "昨天", or "3月22日 周日" format
- **Content type detection**: Auto-detect release/benchmark/blog/news/tutorial
- **Tag extraction**: Extract relevant tags from content (Parquet, OLAP, 性能, etc.)

#### CLI Improvements (`dbradar/cli.py`)
- **Increased defaults**: `--max-items 150`, `--top-k 25` (from 80/10)
- **Incremental mode fix**: Always mark articles as seen in both modes
- **Language support**: `--language zh` for Chinese output

#### Data Sources (`feeds.json`)
- **Expanded from 23 to 46 RSS sources**:
  - Vendor blogs: Timescale, ClickHouse, MongoDB, Redis, Snowflake, Databricks, etc.
  - Industry newsletters: PostgreSQL Weekly, DB Weekly, Data Engineering Weekly
  - Tech blogs: Uber, Netflix, Meta, Google Cloud
  - Community aggregation: Hacker News, Reddit r/Database, Lobste.rs

#### Automation (`scripts/cron_fetch.sh`)
- **Cron script for scheduled fetching**
- **Usage**: `0 8 * * * /path/to/scripts/cron_fetch.sh`
- **Logging**: Output to `logs/fetch.log`

#### Writer Updates (`dbradar/writer.py`)
- **`original_title` field**: Preserves original English title
- **`published_date` field**: Article publication date
- **`content_type` field**: Auto-detected content type
- **`detect_content_type()` function**: Classifies articles

#### Configuration (`dbradar/config.py`)
- **LLM timeout increased**: 120s → 300s for better reliability

### Changed
- Summary now combines `what_changed` + `why_it_matters` + `evidence`
- Template path uses absolute path for reliability

### Usage

```bash
# Run with new defaults
python -m dbradar run --html --language zh

# Incremental mode (only new articles)
python -m dbradar run --html --language zh --incremental

# Start web server
python -m dbradar serve --port 8080

# Setup daily cron job
crontab -e
# Add: 0 8 * * * cd /path/to/py-radar && python -m dbradar run --html --language zh --incremental
```

---

## [2026-03-23] - Web Server for Viewing Reports

### Added

#### Web Server (`dbradar/server.py`)
- Flask-based web server for viewing reports in browser
- `dbradar serve` CLI command to start the server
- Options: `--host`, `--port`, `--debug`
- Auto-refresh every 5 minutes

#### Web Template (`dbradar/web/templates/index.html`)
- Hacker News style UI for displaying news
- Executive Summary section with key highlights
- Intelligence Analysis section:
  - Trend Analysis (emerging/declining topics)
  - Competition Analysis (per-product insights)
- Action Items checklist
- Expandable detail panels for each news item
- Tags auto-extracted from content
- Responsive design for mobile

#### API Endpoints
- `GET /` - Main web page with latest report
- `GET /api/news` - JSON API for latest news
- `GET /api/history` - List historical reports
- `GET /api/report/<date>` - Get specific report by date

### Usage
```bash
# Start web server
python -m dbradar serve

# Custom port
python -m dbradar serve --port 8080

# Debug mode
python -m dbradar serve --debug
```

### Dependencies
- Added `flask>=3.0.0` to pyproject.toml

---

## [2026-03-23] - Intelligence Module (Trend Detection & Competitive Analysis)

### Added

#### Intelligence Module (`dbradar/intelligence/`)
- **`types.py`** - Type definitions for intelligence analysis
  - `AnalysisMode` enum: BASIC, TRENDS, COMPETITION, INTELLIGENCE
  - `AnalysisOptions` dataclass for configuring analysis
  - `TrendResult` with emerging/declining topics and trend velocity
  - `CompetitiveInsight` with recent_moves, positioning_changes, threats, opportunities
  - `ToolResult` wrapper with `ok()` and `fail()` factory methods
  - `IntelligenceReport` as final synthesized output

- **`trends.py`** - Trend detection analyzer
  - `TrendAnalyzer` class that reads historical `out/*.json` files
  - `get_historical_summaries()` loads JSON files within date window
  - `has_history()` checks if enough data exists for analysis
  - `analyze()` uses LLM to identify semantic trends across time
  - Graceful degradation: returns empty result if no history

- **`competition.py`** - Competitive analysis
  - `CompetitionAnalyzer` class for generating competitive insights
  - `analyze()` generates per-product insights:
    - Recent moves (announcements, releases)
    - Positioning changes in market
    - Competitive threats from rivals
    - Opportunities to exploit
  - Requires 2+ products for meaningful analysis

- **`agent.py`** - Orchestration layer
  - `IntelligenceAgent` orchestrates all tools
  - `analyze()` runs summarize first (must succeed), then optional tools
  - `_run_parallel_analysis()` uses ThreadPoolExecutor for concurrent execution
  - Returns `IntelligenceReport` with all results

#### CLI Integration (`dbradar/cli.py`)
- New flags for `run` command:
  - `--intelligence` - Enable full intelligence (trends + competition)
  - `--trends` - Enable trend detection only
  - `--analyze-competition` - Enable competitive analysis only
  - `--history-days N` - Days of history for trend analysis (default: 14)

#### Writer Updates (`dbradar/writer.py`)
- `Report` dataclass extended with:
  - `trends: Optional[TrendResult]`
  - `competition: List[CompetitiveInsight]`
- `to_dict()` includes `intelligence` section when present
- `write_markdown()` renders intelligence sections:
  - Trend Analysis (emerging/declining topics)
  - Competitive Analysis (per-product insights)
- `write_report()` accepts optional `trends` and `competition` params

#### Tests (`tests/`)
- `conftest.py` - Shared fixtures for testing
- `test_trends.py` - 15 tests for TrendAnalyzer
- `test_competition.py` - 13 tests for CompetitionAnalyzer
- `test_agent.py` - 13 tests for IntelligenceAgent
- All 41 tests pass

### Technical Details

#### Architecture
- **Agent-based design**: IntelligenceAgent orchestrates specialized tools
- **Graceful degradation**: If optional tool fails, continue without it
- **JSON-based history**: Uses existing `out/*.json` files (no separate storage)
- **Parallel execution**: ThreadPoolExecutor for concurrent LLM calls
- **Sync codebase**: No asyncio, consistent with existing code

#### LLM Prompts
- Trend analysis: Historical summaries + current day → emerging/declining topics
- Competition analysis: Updates by product → competitive insights per product
- Output format: JSON array/object with structured fields

### Usage
```bash
# Basic summary (default)
python -m dbradar run --html

# With trend detection
python -m dbradar run --trends --html

# With competitive analysis
python -m dbradar run --analyze-competition --html

# Full intelligence mode
python -m dbradar run --intelligence --html

# Custom history window for trends
python -m dbradar run --trends --history-days 30 --html
```

---

## [2026-03-23] - Documentation Rules Update

### Changed
#### `CLAUDE.md`
- Added "File Modification Rules" section with three constraints:
  - Do NOT modify configuration files without user approval
  - Only modify files within project directory
  - Confirm THREE times before modifying files outside this directory

---

## [2026-03-23] - Incremental Subscription Support

### Added
- **`dbradar/seen_tracker.py`** - New module for tracking seen articles
  - `SeenTracker` class to persist seen article URLs in `cache/seen_articles.json`
  - `filter_new()` method to filter out already-seen articles
  - `mark_seen_batch()` to mark articles as processed
  - `cleanup_old()` to remove stale entries (configurable days)
  - `get_stats()` for tracking statistics

### Changed
#### `dbradar/cli.py`
- New `--incremental` / `-i` flag for both `run` and `fetch` commands
- When enabled:
  - Filters articles to only new (unseen) ones
  - Marks all new articles as seen after processing
  - Displays "Mode: Incremental (new articles only)" in output
- Reports now only contain new articles when incremental mode is active

### Technical Details
- **Seen tracking**: Uses SHA256 hash of URL (first 16 chars) as key
- **Persistence**: Stored in `cache/seen_articles.json` with metadata:
  - `url`: Original article URL
  - `title`: Article title
  - `first_seen`: ISO timestamp when first encountered
  - `last_seen`: ISO timestamp when last encountered
  - `published_at`: Article publication date (if available)
- **Incremental workflow**:
  1. Fetch all feeds
  2. Extract and normalize articles
  3. Filter to new articles only (`filter_new`)
  4. Mark all new articles as seen (`mark_seen_batch`)
  5. Rank and generate reports

### Usage
```bash
# Incremental mode - only process new articles
python -m dbradar run -i --html --open

# Fetch only new articles without summarizing
python -m dbradar fetch -i
```

---

## [2026-03-23] - Personalized HTML Briefing & feeds.json Support

### Added

#### Personalization System
- **`dbradar/interests.py`** - New module for loading user interests configuration
  - `InterestsConfig` dataclass with `products` and `keywords` weight mappings
  - YAML parsing with error handling and fallback to defaults
  - `raw_yaml` field to preserve original config for sidebar display

- **`interests.yaml`** - User configuration file for personalized ranking
  - Product priorities (e.g., DuckDB: 2.0, Iceberg: 1.8)
  - Keyword boosts (e.g., lakehouse: 1.6, REST catalog: 1.6)

#### HTML Output
- **`dbradar/templates/briefing.html.j2`** - Jinja2 HTML template
  - Responsive two-column layout
  - Score visualization bars (normalized to max_score)
  - "★ boosted" badges for personalized items
  - Sidebar showing active interests profile
  - Source breakdown and statistics

#### feeds.json Support
- **`dbradar/feeds.py`** - New module for RSS/Atom feed management
  - `FeedSource` dataclass with `title`, `url`, `filter_tags` fields
  - `parse_feeds_file()` for JSON feed list parsing
  - `matches_tags()` for article filtering by tags

### Changed

#### `dbradar/ranker.py`
- `RankedItem` dataclass extended with:
  - `boosted: bool` - whether item received personalization boost
  - `boost_reason: Optional[str]` - description of boost reason
- `Ranker.__init__()` now accepts `interests: Optional[InterestsConfig]`
- `rank()` applies product boost (multiply content_score) and keyword weights
- `rank_items()` convenience function updated with `interests` parameter
- `_calculate_content_score()` uses personalized keywords when available
- `_get_product_boost()` implements "first match wins" rule for product detection

#### `dbradar/writer.py`
- `write_html()` method for HTML generation using Jinja2
- `write_report()` now accepts `interests` and `write_html` parameters
- Returns tuple of `(md_path, json_path, html_path)` when HTML enabled
- `_get_jinja_env()` for lazy Jinja2 environment initialization
- `write_html_report()` convenience function added

#### `dbradar/fetcher.py`
- `FetchResult` extended with `filter_tags: List[str]` field
- `fetch_feed()` method for single feed fetching with filter support
- `fetch_feeds()` method for batch feed fetching
- `fetch_feeds()` convenience function added

#### `dbradar/config.py`
- Added `feeds_file: Path` parameter
- Supports both `website_file` (legacy) and `feeds_file` (preferred)

#### `dbradar/cli.py`
- New CLI flags:
  - `--feeds-file` - path to feeds.json (auto-detects ./feeds.json)
  - `--interests-file` - path to interests.yaml (auto-detects ./interests.yaml)
  - `--html` - generate HTML report
  - `--open` - open HTML in browser after generation
- Auto-detection priority: `--feeds-file` > `--websites-file` > `./feeds.json` > `./websites.txt`
- `_open_in_browser()` helper for cross-platform browser opening (macOS/Linux)
- Updated `run` and `fetch` commands to use feed-based workflow

#### Dependencies
- Added `pyyaml>=6.0` to `requirements.txt` and `pyproject.toml`
- Added `jinja2>=3.1.0` to `requirements.txt` and `pyproject.toml`

### Technical Details

#### Product Boost Algorithm
- Matches product name against `item.title.lower()` and `item.domain.lower()`
- Excludes `item.content` to avoid false positives from comparative articles
- "First match wins" based on YAML insertion order (dict preserves order in Python 3.7+)
- Multiplies `content_score` (type weight) by product weight

#### Keyword Scoring
- When `interests.keywords` is non-empty: replaces `HIGH_VALUE_KEYWORDS`
- Each match contributes `score += 0.05 * weight`
- When `interests.keywords` is empty/absent: falls back to default keywords with flat `+0.1`

#### Score Bar Normalization
- HTML displays `score / max_score_in_run * 100%`
- `max_score` passed as template variable for consistent visualization

### Compatibility
- Fully compatible with database-news-feeds `feeds.json` format
- Backward compatible with `websites.txt` format
- `filter_tags` support for article filtering

---

## Template

```markdown
## [YYYY-MM-DD] - Brief Description

### Added
- New features

### Changed
- Changes to existing features

### Fixed
- Bug fixes

### Removed
- Deprecated features removed
```