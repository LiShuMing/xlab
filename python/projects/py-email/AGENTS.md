# AGENTS.md

AI assistant work guide for the py-email project.

## Project Overview

**py-email** (package name: `my-email`) is a Gmail newsletter digest tool that:
- Pulls Apache mailing list / newsletter emails via Gmail API
- Summarizes them with a local LLM (Ollama/qwen) or OpenAI-compatible APIs
- Generates structured daily digests with topic clustering
- Provides a web-based inbox interface for browsing emails

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Python | CPython | 3.11+ |
| Gmail API | google-api-python-client | 2.120+ |
| HTML Parsing | html2text + BeautifulSoup4 | - |
| Database | SQLite (stdlib) | WAL mode |
| LLM Client | openai SDK | 1.30+ |
| Config | pydantic-settings | 2.3+ |
| CLI | Click | 8.1+ |
| Web Server | FastAPI + Uvicorn | 0.110+ |
| Logging | structlog | 24.1+ |

## Project Structure

```
src/my_email/
├── __init__.py
├── config.py              # Pydantic settings, env var mapping
├── cli.py                 # Click CLI commands
├── gmail/                 # Gmail API integration
│   ├── auth.py           # OAuth2 flow
│   ├── sync.py           # Incremental sync with historyId
│   └── __init__.py
├── parser/               # HTML email cleaning
│   ├── cleaner.py        # html2text + BS4 processing
│   └── __init__.py
├── db/                   # Database layer
│   ├── models.py         # Pydantic models for LLM I/O
│   ├── repository.py     # SQLite repository pattern
│   ├── topic_repository.py  # Topic arc tracking
│   └── __init__.py
├── llm/                  # LLM summarization
│   ├── summarizer.py     # OpenAI-compatible client
│   ├── email_filter.py   # Pre-summarization filtering
│   ├── thread_aggregator.py # Thread grouping
│   └── __init__.py
├── digest/               # Digest generation
│   ├── builder.py        # Aggregate summaries
│   ├── renderer.py       # Jinja2 HTML rendering
│   └── templates/        # Jinja2 templates
├── server/               # FastAPI web server
│   └── app.py
├── project/              # Project/topic discovery
│   ├── clusterer.py      # Topic co-occurrence clustering
│   ├── models.py         # Project models
│   └── __init__.py
└── scheduler/            # Background tasks
    ├── sync_task.py
    ├── cleanup_task.py
    └── __init__.py
```

## Build and Test Commands

### Development Setup

```bash
cd /home/lism/work/xlab/python/projects/py-email
source .venv/bin/activate
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/test_cleaner.py -v

# Run with coverage
pytest tests/ -v --cov=src/my_email --cov-report=term-missing
```

### Linting and Formatting

```bash
# Check code style
ruff check src/ tests/

# Format code
ruff format src/ tests/

# Type checking
mypy --strict src/
```

### Running the Application

```bash
# Development server (with auto-reload)
my-email server --host 127.0.0.1 --port 8080 --reload

# CLI workflow
my-email sync                    # Full/incremental sync
my-email summarize --date 2026-04-01
my-email digest --date 2026-04-01 --html --open
my-email show --date 2026-04-01
```

## Code Style Guidelines

### Python Style

- **Type hints**: Use modern Python 3.11+ syntax (`str | None` instead of `Optional[str]`)
- **String quotes**: Single quotes for strings, double quotes for docstrings
- **Line length**: 100 characters (configured in pyproject.toml)
- **Imports**: Group by stdlib, third-party, local; sort alphabetically within groups

### Error Handling

- Use custom exception classes for domain-specific errors
- Retry logic with `tenacity` for external API calls
- Fail fast at boundaries (user input, external APIs)

### Logging

- Use `structlog` exclusively - never use `print()`
- Structured logging with context binding

### Database

- SQLite with WAL mode enabled
- Connection-per-request pattern
- Standard SQL (no SQLite-specific types for portability)

## Important Files and Directories

| File/Directory | Purpose |
|----------------|---------|
| `src/my_email/config.py` | Central configuration with pydantic-settings |
| `src/my_email/db/repository.py` | Main data access layer |
| `src/my_email/llm/summarizer.py` | LLM integration with retry logic |
| `src/my_email/digest/builder.py` | Digest aggregation logic |
| `data/` | SQLite database files (gitignored) |
| `tests/` | pytest test suite |
| `.env` | Environment configuration (gitignored) |

## Configuration

Configuration is managed via `pydantic-settings` with priority:
1. Environment variables (highest)
2. Local `.env` file
3. Global `~/.env` file (for shared LLM settings)

Key environment variables:
- `GMAIL_CREDENTIALS_FILE` - OAuth credentials path
- `GMAIL_TOKEN_FILE` - OAuth token storage path
- `GMAIL_FILTER_QUERY` - Gmail search filter
- `LLM_BASE_URL` - OpenAI-compatible API endpoint
- `LLM_API_KEY` - API key for LLM service
- `LLM_MODEL` - Model name (e.g., qwen2.5:7b)

## Testing Notes

- Tests use `pytest-mock` to isolate LLM network calls
- Gmail OAuth and actual LLM calls are not covered by unit tests
- Database tests use temporary SQLite files
- Run `pytest tests/ -v` before claiming completion

## Common Patterns

### Adding a New CLI Command

1. Add command function in `src/my_email/cli.py`
2. Use `@click.command()` decorator
3. Use `structlog` for logging
4. Add tests in `tests/test_cli.py`

### Adding a New Repository Method

1. Add method to `src/my_email/db/repository.py`
2. Use type hints for all parameters and return values
3. Add comprehensive docstrings
4. Add corresponding tests in `tests/test_repository.py`

### LLM Structured Output

All LLM I/O uses Pydantic v2 models in `src/my_email/db/models.py`:
- `EmailSummary` - Individual email summary
- `DailyDigest` - Aggregated digest
- `TopicArc` - Topic tracking
