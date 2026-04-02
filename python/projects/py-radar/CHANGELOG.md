# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-03-23

### Added
- Support for `feeds.json` format subscription sources
  - New `dbradar/feeds.py` module with `FeedSource` dataclass
  - Updated `config.py` to use `feeds_file` instead of `website_file`
  - Updated `fetcher.py` to support `FeedSource` type
  - CLI now uses `--feeds-file` parameter, auto-detects `./feeds.json`
  - Default to feeds.json format, deprecating websites.txt
  - Added `dbradar/templates/briefing.html.j2` HTML template

- Personalized HTML Briefing feature
  - New `dbradar/interests.py` module supporting `interests.yaml` configuration
  - Updated `ranker.py` with product weights and keyword boosting
  - New `writer.py` for HTML output using Jinja2 templates
  - CLI adds `--html`, `--open`, `--interests-file` parameters
  - HTML output includes score bars, boosted badges, and interest sidebar

- API configuration validation command
  - New `dbradar check` command to verify all API configurations
  - Added `validate()` methods to all APIs for connectivity testing
  - Test results: NewsAPI working, Google API Key needs verification

- Improved Chinese content generation
  - `Summarizer._build_prompt()` now generates content in English
  - New `Summarizer._translate_to_chinese()` method for translation
  - Added `_translate_update_to_chinese()` and `_translate_release_note_to_chinese()`
  - When `language="zh"`, content is generated in English then translated to Chinese

### Changed
- CLI arguments: `--websites-file` replaced with `--feeds-file`
- Default feed source format changed from websites.txt to feeds.json
- Summarizer now generates English first, then translates for Chinese output

### Deprecated
- `websites.txt` format (still supported but not recommended)

## [0.1.0] - 2026-03-20

### Added
- Initial release of Daily DB Radar
- Hacker News-inspired web interface with orange header
- Date-grouped news display with daily counts
- Async summary loading via API endpoints
- Pagination for browsing historical items
- Responsive design for desktop and mobile

- Multi-source data aggregation
  - Support for RSS feeds from database vendors
  - DuckDB unified storage for all items
  - URL-based duplicate detection
  - Automatic content type classification (release, benchmark, blog, news, tutorial)

- AI-powered summarization
  - Background summary generation using LLM
  - Thread pool with 3 workers for parallel processing
  - On-demand summary fetching via `/api/item/<id>/summary`
  - Support for OpenAI-compatible APIs (DashScope/Qwen tested)

- REST API endpoints
  - `GET /` - Main page with paginated news
  - `GET /page/<n>` - Specific page of results
  - `GET /date/<YYYY-MM-DD>` - Items for specific date
  - `GET /api/news` - Recent 7 days of news (JSON)
  - `GET /api/items?page=N&per_page=M` - Paginated items (JSON)
  - `GET /api/stats` - Storage statistics
  - `GET /api/item/<id>/summary` - Get item summary

- Storage layer
  - `DuckDBStore` with unified storage in `data/items.duckdb`
  - Schema with metadata (title, URL, date, product, tags, summary, raw_content)
  - Indexes optimized for date, product, and content type queries

- Background task system
  - ThreadPoolExecutor with 3 concurrent workers
  - Per-thread DuckDB connections to avoid lock conflicts
  - Graceful shutdown with timeout handling

- Intelligence modules
  - `dbradar/intelligence/agent.py` - AI agent for analysis
  - `dbradar/intelligence/types.py` - Type definitions
  - `dbradar/intelligence/trends.py` - Trend analysis
  - `dbradar/intelligence/competition.py` - Competitive analysis

- Caching layer
  - File-based JSON cache for HTTP responses
  - Cache key based on URL hash
  - Configurable cache directory

- Seen tracker
  - URL-based deduplication
  - Persistent storage of seen URLs
  - Configurable deduplication strategy

- CLI commands
  - `dbradar fetch` - Fetch updates from all sources
  - `dbradar fetch -v` - Verbose fetch output
  - `dbradar.server` - Start web server
  - Support for custom port and debug mode

- Migration utility
  - `scripts/migrate_to_duckdb.py` - Migrate JSON data to DuckDB
  - Dry-run mode for testing

- Configuration management
  - Environment variable support via `.env` file
  - Pydantic-based configuration
  - Support for DB_RADAR_* prefixed variables

- Testing infrastructure
  - pytest configuration
  - Test fixtures in `conftest.py`
  - Unit tests for intelligence modules

### Project Structure
```
dbradar/
├── __init__.py
├── cli.py
├── config.py
├── fetcher.py
├── parser.py
├── server.py
├── feeds.py
├── interests.py
├── ranker.py
├── writer.py
├── generate_summary.py
├── cache.py
├── normalize.py
├── seen_tracker.py
├── sources.py
├── enhanced_sources.py
├── storage/
│   ├── __init__.py
│   ├── base.py
│   └── duckdb_store.py
├── intelligence/
│   ├── __init__.py
│   ├── agent.py
│   ├── types.py
│   ├── trends.py
│   └── competition.py
└── web/
    └── templates/
        ├── index.html
        └── briefing.html.j2
```

## [0.0.1] - 2026-03-15

### Added
- Project initialization
- Basic project structure
- README.md with project overview
- requirements.txt with dependencies
- .env.example for configuration
