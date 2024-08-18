# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project documentation files: AGENTS.md, RULES.md, CHANGELOG.md
- Comprehensive test suite:
  - `tests/test_config.py` - Settings and configuration tests
  - `tests/test_email_filter.py` - Email filtering logic tests
  - `tests/test_thread_aggregator.py` - Thread aggregation tests
- 57 new tests (114 total, up from 57)

### Fixed
- Removed unused `_determine_msg_state` function from `gmail/sync.py`
- Fixed import order in `server/app.py`
- Fixed unused imports across multiple files
- All code passes ruff linting and formatting checks

## [0.2.0] - 2026-03-24

### Added
- Web inbox interface (FastAPI + Jinja2 + HTMX)
- Topic arc tracking with trend detection
- Project discovery from topic co-occurrence patterns
- Background scheduler for sync and cleanup tasks
- HTML digest rendering with responsive design
- Thread aggregation for related emails
- Email pre-filtering (StarRocks, auto-reply detection)

### Changed
- Migrated to Pydantic v2 `BaseSettings` with `frozen=True`
- Improved error handling with custom exception hierarchy
- Enhanced retry logic with `tenacity` for LLM calls
- Updated CLI with new commands: `topics`, `projects`

### Fixed
- JSON parsing errors in LLM output now handled gracefully
- Date filtering validation in sync operations

## [0.1.0] - 2026-03-19

### Added
- Initial release of my-email
- Gmail API integration with OAuth2
- Incremental sync using historyId
- HTML email cleaning (html2text + BeautifulSoup)
- LLM summarization with OpenAI-compatible APIs
- SQLite persistence with WAL mode
- Daily digest generation
- Click-based CLI interface
- Structured logging with structlog
- Configuration management with pydantic-settings

### Core Features
- Full and incremental Gmail sync
- Message deduplication
- Topic extraction and clustering
- Relevance scoring (high/medium/low)
- Digest export (JSON and HTML)
- Topic tracking across digests

[Unreleased]: https://github.com/lism/xlab/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/lism/xlab/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lism/xlab/releases/tag/v0.1.0
