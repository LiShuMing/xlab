# Daily DB Radar

A deterministic, extensible system for collecting and summarizing DB/OLAP industry updates from curated sources.

It's inspired by websites below:
- https://database.news/

## Features

### Web Interface
- **Hacker News-inspired UI**: Clean, minimalist design with orange header and simple navigation
- **Date-grouped display**: News items organized by publication date with daily counts
- **Async summary loading**: Click "summary" to fetch AI-generated summaries on demand
- **Pagination**: Browse through historical items with simple prev/next navigation
- **Responsive design**: Works on desktop and mobile devices

### Data Collection
- **Multi-source aggregation**: Collects updates from database vendor blogs, release notes, and news sites
- **DuckDB storage**: Efficient unified storage for all items with fast querying
- **Duplicate detection**: URL-based deduplication prevents duplicate entries
- **Content type classification**: Automatically categorizes items (release, benchmark, blog, news, tutorial)

### AI-Powered Summarization
- **Background summary generation**: Automatically generates summaries for new items using LLM
- **Concurrent processing**: Thread pool with 3 workers for parallel summary generation
- **On-demand loading**: Frontend fetches summaries asynchronously via API
- **Configurable LLM**: Supports OpenAI-compatible APIs (tested with DashScope/Qwen)

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main page with paginated news list |
| `GET /page/<n>` | Specific page of results |
| `GET /date/<YYYY-MM-DD>` | Items for a specific date |
| `GET /api/news` | Recent 7 days of news (JSON) |
| `GET /api/items?page=N&per_page=M` | Paginated items (JSON) |
| `GET /api/stats` | Storage statistics |
| `GET /api/item/<id>/summary` | Get summary for a specific item |

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd py-radar

# Install dependencies
pip install -r requirements.txt

# Optional: Install DuckDB for storage
pip install duckdb
```

## Configuration

Create a `.env` file or set environment variables:

```bash
# LLM API Configuration (for summary generation)
DB_RADAR_API_KEY=your_api_key_here
DB_RADAR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DB_RADAR_MODEL=qwen-max

# Optional: Timeout for LLM requests (seconds)
DB_RADAR_TIMEOUT=60
```

Supported LLM providers:
- **DashScope (Alibaba)**: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **OpenAI**: `https://api.openai.com/v1`
- **Other OpenAI-compatible APIs**: Any compatible endpoint

## Usage

### Fetch Data

```bash
# Fetch latest updates from all sources
python -m dbradar fetch

# Fetch with verbose output
python -m dbradar fetch -v
```

### Start Web Server

```bash
# Start server on default port (5000)
python -m dbradar.server

# Start on custom port
python -m dbradar.server --port 5001

# Start with debug mode
python -m dbradar.server --debug

# Start without background summary generation
python -m dbradar.server --no-background
```

### Data Migration (JSON to DuckDB)

If you have existing JSON data from an older version:

```bash
# Dry run to see what would be migrated
python scripts/migrate_to_duckdb.py --dry-run

# Perform migration
python scripts/migrate_to_duckdb.py
```

## Architecture

### Storage Layer
- **DuckDBStore**: Unified storage in `data/items.duckdb`
- **Schema**: Items stored with metadata (title, URL, date, product, tags, summary, raw_content)
- **Indexes**: Optimized queries by date, product, and content type

### Background Task System
- **ThreadPoolExecutor**: 3 concurrent workers for LLM API calls
- **Connection per thread**: Each worker creates independent DuckDB connection to avoid lock conflicts
- **Graceful shutdown**: Clean shutdown with timeout handling

### Summary Generation Flow
1. Server starts and launches background worker thread
2. Worker queries for items without summaries (batch of 10)
3. Each item submitted to thread pool for processing
4. LLM API generates concise 2-3 sentence summary
5. Summary saved to database immediately
6. Frontend fetches via `/api/item/<id>/summary` endpoint

## Project Structure

```
dbradar/
├── __init__.py
├── cli.py                 # CLI commands (fetch, etc.)
├── config.py             # Configuration management
├── fetcher.py            # RSS/feed fetching logic
├── parser.py             # Content parsing and classification
├── server.py             # Flask web server with background tasks
├── generate_summary.py   # Standalone summary generation utility
├── storage/              # Storage backends
│   ├── __init__.py
│   ├── base.py          # Abstract base class
│   └── duckdb_store.py  # DuckDB implementation
└── web/
    └── templates/
        └── index.html    # HN-style UI template

data/
└── items.duckdb         # Main storage file

scripts/
└── migrate_to_duckdb.py # Migration utility
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dbradar
```

### Code Style

```bash
# Format code
ruff format dbradar/

# Run linter
ruff check dbradar/

# Type checking
mypy dbradar/
```

## License

MIT License
