# Changelogs

All notable changes to this project will be documented in this file.

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