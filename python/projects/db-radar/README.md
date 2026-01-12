# Daily DB Radar

A deterministic, extensible system for collecting and summarizing DB/OLAP industry updates from curated sources.

## What It Does

1. Reads source URLs from `websites.txt`
2. Fetches and caches content from all sources
3. Extracts structured items (titles, dates, content)
4. Normalizes and deduplicates items
5. Ranks by relevance, recency, and authority
6. Generates structured summaries using Anthropic
7. Outputs Markdown and JSON reports

## Quick Start

```bash
# Install dependencies
pip install -e .

# Set Anthropic API key
export ANTHROPIC_API_KEY="your-api-key"

# Run the complete pipeline
python -m dbradar run --days 7 --top-k 10
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `dbradar run --days 7 --top-k 10` | Full pipeline: fetch → extract → summarize → write |
| `dbradar fetch --days 7` | Fetch content only, save for later |
| `dbradar summarize --date 2025-01-11` | Summarize previously fetched data |

Options:
- `--days` - Look back period (default: 7)
- `--top-k` - Items to include in summary (default: 10)
- `--no-cache` - Skip cache, fetch fresh

## Configuration

### Environment Variables

```bash
ANTHROPIC_API_KEY      # Required for summarization
ANTHROPIC_BASE_URL     # Optional: custom API endpoint
```

### websites.txt Format

```text
# Pipe-separated: Product | url1 | url2 | url3
DuckDB | https://duckdb.org/news/ | https://github.com/duckdb/duckdb/releases

# Space-separated also supported
ClickHouse https://clickhouse.com/blog/ https://github.com/ClickHouse/ClickHouse/releases

# Comments and blank lines ignored
# This is a comment
```

## Output

Reports are written to `out/YYYY-MM-DD.md` and `out/YYYY-MM-DD.json`:

```markdown
# Daily DB Radar - 2025-01-12

## Executive Summary
- Item 1
- Item 2

## Top Updates
### [Product] Title
**What changed:**
- Change 1
- Change 2

**Why it matters:**
- Reason 1
- Reason 2

**Source(s):**
- https://...

**Evidence:**
> Snippet from content
```

## Architecture

```
┌─────────────┐
│ websites.txt│
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   sources   │────▶│   fetcher   │
│   (parse)   │     │  (HTTP +    │
└─────────────┘     │   cache)    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  extractor  │────▶│  normalize  │
                    │ (HTML/RSS)  │     │(dedupe +    │
                    └─────────────┘     │ normalize)  │
                                       └──────┬──────┘
                                              │
                                              ▼
                                       ┌─────────────┐     ┌─────────────┐
                                       │   ranker    │────▶│ summarizer  │
                                       │(relevance)  │     │  (Anthropic)│
                                       └─────────────┘     └──────┬──────┘
                                                                  │
                                                                  ▼
                                                           ┌─────────────┐
                                                           │   writer    │
                                                           │ (MD + JSON) │
                                                           └──────┬──────┘
                                                                  │
                                                                  ▼
                                                           ┌─────────────┐
                                                           │ out/        │
                                                           │ YYYY-MM-DD  │
                                                           └─────────────┘
```

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `config.py` | Configuration holder (API key, paths, defaults) |
| `sources.py` | Parse `websites.txt` into `Source` objects |
| `cache.py` | File-based HTTP cache with ETag/Last-Modified |
| `fetcher.py` | Fetch URLs, handle errors, respect cache |
| `extractor.py` | Parse HTML/RSS into `ExtractedItem` |
| `normalize.py` | Deduplicate, normalize titles, extract dates |
| `ranker.py` | Score by relevance, recency, authority |
| `summarizer.py` | Call Anthropic for structured summary |
| `writer.py` | Write Markdown and JSON reports |
| `cli.py` | Click CLI with run/fetch/summarize commands |

## Design Principles

1. **Deterministic Pipeline**: Fetch → Extract → Normalize → Rank → Summarize → Write
2. **LLM Constraints**: Used only for classification and summarization, never for search
3. **Extensibility**: Each module is focused and can be extended/replaced
4. **No Fact Invention**: All summaries grounded in fetched content with citations
5. **Caching**: Avoid refetching with ETag/Last-Modified support
6. **Deduplication**: Exact URL + similarity-based (normalized title + domain + date)

## Ranking Rules

- **Release notes, GitHub releases, engineering blogs**: Higher weight
- **Within 7 days**: Higher weight
- **Performance, execution engine, storage, optimizer**: Higher weight
- **Official sources (github.com, docs.*)**: Higher weight

## Extending the System

### Adding New Output Formats

Subclass `Writer` and override `write_report()`:

```python
class CustomWriter(Writer):
    def write_report(self, report: Report, filename: str = None):
        # Your custom format
```

### Adding New Source Types

Extend `Extractor` class:

```python
class CustomExtractor(Extractor):
    def extract_custom(self, result: FetchResult) -> List[ExtractedItem]:
        # Your custom extraction logic
```

### Adding New Ranking Criteria

Modify `Ranker._calculate_*` methods:

```python
class CustomRanker(Ranker):
    def _calculate_custom_score(self, item: NormalizedItem) -> float:
        # Your custom scoring logic
```

## Dependencies

```
anthropic>=0.34.0      # LLM client
httpx>=0.27.0          # HTTP client
beautifulsoup4>=4.12.0 # HTML parsing
lxml>=5.0.0            # XML/HTML backend
readability-lxml>=0.8.1 # Article extraction
feedparser>=6.0.11     # RSS/Atom parsing
click>=8.1.0           # CLI framework
python-dateutil>=2.8.2 # Date parsing
tqdm>=4.66.0           # Progress bars
```

## License

MIT
