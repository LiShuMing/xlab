# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the Daily DB Radar project.

## Code Style

### Python Standards

- **Python Version**: 3.12+
- **Type Hints**: Strict typing required for all functions and methods
  - Use modern syntax: `str | None` instead of `Optional[str]`
  - Use `|` for unions instead of `Union[]`
  - Use `list[T]` instead of `List[T]`
- **String Formatting**: Use f-strings exclusively
- **Path Handling**: Use `pathlib.Path` instead of `os.path`
- **Imports**: Group imports (stdlib, third-party, local) with blank lines between

### Formatting and Linting

```bash
# Format code
ruff format dbradar/

# Run linter
ruff check dbradar/

# Type checking
mypy dbradar/
```

## Architecture Principles

### AI Agent Design

1. **Separation of Concerns**
   - Separate deterministic business logic from non-deterministic LLM interactions
   - Use clear interfaces between components

2. **Data Validation**
   - Use Pydantic v2 for all data validation and serialization
   - Never use raw dictionaries for complex state passing

3. **Observability**
   - Use structured logging (`structlog` or `loguru`) - never `print()`
   - Inject context variables (`correlation_id`, `session_id`) for tracing
   - Log exact LLM payloads and responses at DEBUG level

4. **Error Handling**
   - Implement retries for external API calls using `tenacity`
   - Design graceful degradation and fallback mechanisms
   - Raise descriptive custom exceptions for invalid states

### State Management

- Design agents around State Machines or DAGs
- Keep state immutable where possible
- Pass state explicitly between components
- Ensure state is easily serializable

### Concurrency

- Use `asyncio` for I/O-bound tasks (network requests, LLM calls)
- Ensure thread safety when using ThreadPoolExecutor
- Avoid blocking the event loop

## Testing Requirements

### Test Structure

```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_*.py            # Unit tests
└── integration/         # Integration tests
```

### Test Standards

- Use `pytest` as the test framework
- Mock external API calls using `unittest.mock` or `pytest-mock`
- Write tests for deterministic logic
- Add evaluation tests for LLM outputs
- Target 80%+ coverage for core modules

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dbradar

# Run specific test file
pytest tests/test_agent.py -v
```

## Configuration Management

### Environment Variables

Use `.env` file or environment variables for configuration:

```bash
# LLM API Configuration
DB_RADAR_API_KEY=your_api_key_here
DB_RADAR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DB_RADAR_MODEL=qwen-max
DB_RADAR_TIMEOUT=60

# Storage Configuration
DB_RADAR_STORAGE_PATH=./data/items.duckdb

# Cache Configuration
DB_RADAR_CACHE_DIR=./cache
```

### Configuration Pattern

Use Pydantic Settings for configuration:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4"

    class Config:
        env_prefix = "DB_RADAR_"
        env_file = ".env"
```

## Documentation Requirements

### Code Documentation

- All public functions must have docstrings
- Include `Args`, `Returns`, and `Raises` sections
- Use Google-style docstrings

```python
def fetch_items(source: FeedSource, limit: int = 10) -> list[Item]:
    """Fetch items from a feed source.

    Args:
        source: The feed source to fetch from.
        limit: Maximum number of items to fetch.

    Returns:
        List of fetched items.

    Raises:
        FetchError: If the fetch operation fails.
    """
```

### Change Documentation

- Update `CHANGELOG.md` for every code change
- Use format: `YYYY-MM-DD - Brief description`
- Include technical details for significant changes

## Project Structure

```
dbradar/
├── __init__.py
├── cli.py              # CLI commands
├── config.py           # Configuration management
├── fetcher.py          # RSS/feed fetching
├── parser.py           # Content parsing
├── server.py           # Web server
├── feeds.py            # Feed source definitions
├── interests.py        # Interest configuration
├── ranker.py           # Content ranking
├── writer.py           # Output generation
├── cache.py            # Caching layer
├── normalize.py        # Content normalization
├── seen_tracker.py     # Deduplication
├── storage/            # Storage backends
│   ├── __init__.py
│   ├── base.py
│   └── duckdb_store.py
├── intelligence/       # AI/LLM modules
│   ├── __init__.py
│   ├── agent.py
│   ├── types.py
│   ├── trends.py
│   └── competition.py
└── web/                # Web interface
    └── templates/
```

## Prohibited Actions

1. **DO NOT** use `print()` statements - use structured logging
2. **DO NOT** hardcode prompts - use external prompt files or templates
3. **DO NOT** skip CHANGELOG.md updates
4. **DO NOT** modify config files (feeds.json, interests.yaml) without explicit approval
5. **DO NOT** modify files outside the project directory without 3x confirmation

## Commit Message Convention

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(fetcher): add support for RSS feeds
fix(storage): resolve duckdb connection leak
docs(readme): update installation instructions
```

## Dependencies

### Core Dependencies

- `pydantic` >= 2.0 - Data validation
- `pydantic-settings` - Configuration management
- `structlog` - Structured logging
- `tenacity` - Retry logic
- `duckdb` - Storage backend
- `flask` - Web server
- `jinja2` - Templating
- `feedparser` - RSS feed parsing
- `requests` - HTTP client

### Development Dependencies

- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `ruff` - Linting and formatting
- `mypy` - Type checking
- `types-requests` - Type stubs for requests

## File Modification Rules

1. **Config files**: Do NOT modify without explicit user approval
2. **Scope limit**: Only modify files within this project directory
3. **External changes**: Confirm THREE times before modifying external files

## LLM Integration Rules

### Prompt Engineering

- Keep prompts in external files (Jinja2 templates or text files)
- Version control prompts alongside code
- Include examples in prompts (few-shot prompting)
- Validate LLM outputs with Pydantic models

### Error Handling

- Always wrap LLM calls in try-except blocks
- Implement retry logic with exponential backoff
- Provide fallback behavior when LLM fails
- Log full request/response for debugging

### Token Management

- Be mindful of token limits
- Implement context truncation when needed
- Use summary techniques for long content
- Monitor token usage and costs

## Performance Guidelines

- Use connection pooling for HTTP requests
- Implement caching for expensive operations
- Use batching for database operations
- Profile code before optimizing
- Prefer lazy loading over eager loading
