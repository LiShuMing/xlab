# AGENTS.md

## Project Overview

`py-cli` is a Python-based CLI tool designed for code repository analysis using Large Language Models (LLM). It generates structured technical reports from git commit history and code changes.

### Goals
- Provide automated code change analysis via CLI interface
- Generate Markdown reports (default) with customizable output formats
- Support extensible architecture for adding new CLI commands
- Enable LLM module reuse across different analysis features

## Tech Stack

### Core Technologies
- **Language**: Python 3.13+
- **CLI Framework**: Click (for extensible command structure)
- **LLM Integration**: Anthropic Claude API (via `anthropic` SDK)
- **Git Operations**: GitPython
- **Environment Config**: python-dotenv
- **Async Support**: asyncio + aiohttp (for concurrent LLM calls)

### Development Tools
- **Testing**: pytest with pytest-asyncio
- **Type Checking**: mypy (strict mode)
- **Linting**: ruff
- **Formatting**: black
- **Import Sorting**: isort
- **Package Management**: pip + requirements.txt (or uv)

## Build and Test Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e ".[dev]"
```

### Development Commands
```bash
# Run type checking
mypy py_cli --strict

# Run linting
ruff check py_cli
ruff check --select I py_cli  # Import checking

# Format code
black py_cli tests
isort py_cli tests

# Run tests
pytest -s tests/

# Run tests with coverage
pytest --cov=py_cli --cov-report=term-missing tests/
```

### Usage Examples
```bash
# Basic analysis of current git repo (default output: report.md)
py-cli analyze

# Specify custom repo path
py-cli analyze --repo /path/to/repo

# Specify output path
py-cli analyze --output ./analysis-report.md

# Analyze specific time range
py-cli analyze --since "2024-01-01" --until "2024-01-31"

# Use different analysis prompt
py-cli analyze --prompt clickhouse  # Use ClickHouse-specific prompt

# List available prompts
py-cli prompts list
```

## Code Style Guidelines

### Python Style
- Follow PEP 8 with black formatting (88 char line length)
- Use type hints for all function signatures (Python 3.13+ features)
- Use `from __future__ import annotations` for forward references
- Prefer dataclasses or Pydantic models for structured data
- Use pathlib.Path instead of os.path
- Use f-strings for string formatting

### Error Handling
- Use custom exception hierarchy in `py_cli.exceptions`
- Wrap external API calls with proper error handling
- Use context managers for resource management
- Log errors with appropriate severity levels

### Async Patterns
- Use `async def` for I/O bound operations (LLM API calls)
- Use `asyncio.gather()` for concurrent operations
- Provide sync wrappers where necessary for CLI compatibility

## Project Structure

```
python/projects/py-cli/
├── py_cli/                    # Main package
│   ├── __init__.py           # Package version
│   ├── __main__.py           # Entry point: python -m py_cli
│   ├── cli.py                # Main Click group and commands
│   ├── commands/             # CLI subcommands
│   │   ├── __init__.py
│   │   ├── analyze.py        # Git analysis command
│   │   └── prompts.py        # Prompt management commands
│   ├── core/                 # Core business logic
│   │   ├── __init__.py
│   │   ├── analyzer.py       # Git change analysis orchestrator
│   │   ├── git_client.py     # Git operations wrapper
│   │   └── reporter.py       # Report generation
│   ├── llm/                  # LLM module (reusable)
│   │   ├── __init__.py
│   │   ├── client.py         # Anthropic client wrapper
│   │   ├── models.py         # Pydantic models for LLM
│   │   ├── prompts/          # Prompt templates
│   │   │   ├── __init__.py
│   │   │   ├── default.py    # Default analysis prompt
│   │   │   └── clickhouse.py # ClickHouse-specific prompt
│   │   └── utils.py          # LLM utilities (token counting, etc.)
│   ├── config.py             # Configuration management
│   ├── exceptions.py         # Custom exceptions
│   └── utils.py              # General utilities
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures
│   ├── test_cli.py          # CLI tests
│   ├── test_analyzer.py     # Analyzer unit tests
│   ├── test_git_client.py   # Git client tests
│   └── test_llm_client.py   # LLM client tests
├── docs/                    # Documentation
│   ├── architecture/        # Architecture docs
│   └── guides/             # User guides
├── pyproject.toml          # Project configuration
├── requirements.txt        # Dependencies
├── requirements-dev.txt    # Dev dependencies
├── README.md              # User documentation
├── CHANGELOG.md           # Version history
├── RULES.md               # Project rules
└── AGENTS.md              # This file
```

## Key Design Patterns

### Extensible CLI Architecture
- Use Click's group mechanism for subcommands
- Each command lives in `commands/` module
- Common options via Click decorators
- Plugin-like structure for adding new commands

### LLM Module Reusability
- Abstract LLM client interface
- Prompt templates as Python modules
- Support for multiple prompt types (default, clickhouse, custom)
- Caching layer for LLM responses (optional)

### Configuration Management
- Environment variables from `~/.env` file
- Hierarchical config: CLI args > env vars > defaults
- Support for config file (`~/.py-cli/config.toml`)

## Important Notes

### LLM API Configuration
- API key read from `~/.env` file (`ANTHROPIC_API_KEY`)
- Support for other LLM providers via config (extensible)
- Rate limiting and retry logic built into LLM client

### Git Operations
- Operates on git repositories (local or clone)
- Uses GitPython for programmatic git access
- Handles large repos with commit filtering

### Report Generation
- Default output: Markdown format
- Extensible formatter system (future: HTML, JSON)
- Customizable templates via Jinja2

### Testing Strategy
- Unit tests with mocked LLM responses
- Git operations tested with temporary repos
- Integration tests for end-to-end workflows

## Dependencies

### Required
```
anthropic>=0.20.0
click>=8.0.0
gitpython>=3.1.0
python-dotenv>=1.0.0
pydantic>=2.0.0
aiohttp>=3.9.0
```

### Development
```
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
mypy>=1.7.0
black>=23.0.0
ruff>=0.1.0
isort>=5.12.0
```

## Related Documentation

- [RULES.md](./RULES.md) - Coding standards and project rules
- [CHANGELOG.md](./CHANGELOG.md) - Version history
- [README.md](./README.md) - User-facing documentation
- [docs/architecture/](./docs/architecture/) - Architecture documentation
