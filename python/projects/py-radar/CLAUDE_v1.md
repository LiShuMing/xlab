# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Running

```bash
# Install (editable)
pip install -e .

# Required env vars (can be set in ~/.env)
export LLM_API_KEY="..."
export LLM_BASE_URL="..."   # optional, e.g., https://coding.dashscope.aliyuncs.com/v1
export LLM_MODEL="..."      # optional, e.g., qwen3.5-plus

# Optional: Enhanced data sources (Google Custom Search, NewsAPI)
export GOOGLE_API_KEY="..."   # Google Custom Search API key
export GOOGLE_CX="..."        # Google Custom Search Engine ID
export NEWSAPI_KEY="..."      # NewsAPI.org API key

# Check configuration (validate API keys)
python -m dbradar check

# Full pipeline
python -m dbradar run --days 7 --top-k 10

# Fetch only (no LLM call)
python -m dbradar fetch --days 7

# Summarize previously fetched data
python -m dbradar summarize --date YYYY-MM-DD

# Output in Chinese
python -m dbradar run --days 7 --language zh

# Common flags
--no-cache        # bypass HTTP cache, refetch all
--max-items 80    # cap items before ranking
--websites-file   # override default websites.txt path
--language, -l    # output language: en (default) or zh
```

## Development

```bash
# Lint
ruff check dbradar/
black --check dbradar/

# Format
black dbradar/

# Tests (if present)
pytest tests/
```

Line length: 100. Target: Python 3.11+.

## Architecture

Deterministic pipeline — each stage is a pure function with a convenience wrapper:

```
sources.py → fetcher.py → extractor.py → normalize.py → ranker.py → summarizer.py → writer.py
```

**Data flow types:**
- `sources.py`: parses `websites.txt` → `List[Source]`
- `fetcher.py`: `List[Source]` → `List[FetchResult]` (HTTP + cache)
- `extractor.py`: `List[FetchResult]` → `List[ExtractedItem]` (HTML/RSS parsing)
- `normalize.py`: `List[ExtractedItem]` → `List[NormalizedItem]` (dedupe, date parse)
- `ranker.py`: `List[NormalizedItem]` → `List[RankedItem]` (score by recency + content type + keywords)
- `summarizer.py`: `List[RankedItem]` → `SummaryResult` (Anthropic call, JSON response)
- `writer.py`: `SummaryResult` + `List[RankedItem]` → `out/YYYY-MM-DD.{md,json}`

**Config** (`config.py`): global singleton via `get_config()`/`set_config()`. Set by CLI before any module runs. Automatically loads `~/.env` file on import.

**Cache** (`cache.py`): file-based, stored in `./cache/`. Keyed by URL hash. Respects ETag/Last-Modified.

## LLM Usage

The LLM (configured via `LLM_MODEL`, defaults to `qwen3.5-plus`) is called only in `summarizer.py`. It receives pre-ranked item snippets and returns a structured JSON object. It must never be used for fetching or searching — only classification and summarization of already-fetched content.

## Key Conventions

- Each module exposes a convenience function (e.g., `fetch_sources`, `extract_items`, `normalize_items`, `rank_items`, `summarize_items`, `write_reports`) in addition to its class.
- `websites.txt` supports pipe-separated (`Product | url1 | url2`) and space-separated formats; lines starting with `#` and blank lines are ignored.
- Fetch failures are collected and passed through the pipeline to appear in the report's "Fetch Failures" section — never silently dropped.
- `out/fetched_items.json` is the intermediate artifact written by `dbradar fetch` and consumed by `dbradar summarize`.
