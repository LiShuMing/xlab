# py-cli

LLM-powered Git repository code change analyzer.

Generate structured technical reports from git commit history using Large Language Models (Claude).

## Features

- **Automated Analysis**: Analyzes git commits and generates detailed technical reports
- **Multiple Prompt Templates**: Built-in prompts for general analysis and database/kernel projects (ClickHouse)
- **Flexible Date Ranges**: Analyze any time period in your repository history
- **Extensible Architecture**: Easy to add new CLI commands and prompt templates
- **Type-Safe**: Full Python type hints and strict mypy checking

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd python/projects/py-cli

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e ".[dev]"
```

### Configuration

Create a `~/.env` file with your Anthropic API key:

```bash
cp .env.example ~/.env
# Edit ~/.env and add your API key
ANTHROPIC_API_KEY=your_api_key_here
```

Get your API key from: https://console.anthropic.com/

### Usage

```bash
# Analyze current repository (last 30 days)
py-cli analyze

# Analyze a specific repository
py-cli analyze --repo /path/to/repo

# Specify custom date range
py-cli analyze --since 2024-01-01 --until 2024-01-31

# Custom output path
py-cli analyze --output my-report.md

# Use ClickHouse-specific analysis prompt
py-cli analyze --prompt clickhouse

# List available prompts
py-cli prompts list

# Show prompt details
py-cli prompts show default
```

## Project Structure

```
py-cli/
├── py_cli/                 # Main package
│   ├── cli.py             # CLI entry point
│   ├── commands/          # CLI subcommands
│   │   ├── analyze.py     # Analyze command
│   │   └── prompts.py     # Prompt management
│   ├── core/              # Core business logic
│   │   ├── git_client.py  # Git operations
│   │   └── analyzer.py    # Analysis orchestrator
│   ├── llm/               # LLM module
│   │   ├── client.py      # Anthropic API client
│   │   ├── models.py      # Data models
│   │   └── prompts/       # Prompt templates
│   ├── config.py          # Configuration
│   ├── exceptions.py      # Custom exceptions
│   └── utils.py           # Utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
├── pyproject.toml         # Project configuration
└── requirements.txt       # Dependencies
```

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Or install with dev extras
pip install -e ".[dev]"
```

### Code Quality

```bash
# Format code
black py_cli tests
isort py_cli tests

# Run linter
ruff check py_cli

# Type checking
mypy py_cli --strict

# Run tests
pytest -s tests/

# Run tests with coverage
pytest --cov=py_cli --cov-report=term-missing tests/
```

## Report Output

The generated report includes:

- **Executive Summary**: Key findings in bullet points
- **Changes by Category**: Grouped by feature, bugfix, refactor, etc.
- **Key Changes**: Most significant changes with impact analysis
- **Architecture Direction**: Insights into codebase evolution
- **Recommendations**: Actionable suggestions
- **Appendix**: Complete commit list

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required) | - |
| `ANTHROPIC_MODEL` | Claude model to use | `claude-3-5-sonnet-20241022` |
| `ANTHROPIC_MAX_TOKENS` | Maximum tokens per request | `4096` |
| `ANTHROPIC_TEMPERATURE` | Sampling temperature | `0.1` |

### Command-Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--repo` | `-r` | Path to git repository |
| `--output` | `-o` | Output file path |
| `--since` | `-s` | Start date (YYYY-MM-DD) |
| `--until` | `-u` | End date (YYYY-MM-DD) |
| `--prompt` | `-p` | Prompt template to use |
| `--max-commits` | `-m` | Maximum commits to analyze |

## Extending py-cli

### Adding a New Prompt Template

Create a new file in `py_cli/llm/prompts/`:

```python
# py_cli/llm/prompts/my_custom.py
SYSTEM_PROMPT = """Your system prompt here..."""

USER_PROMPT_TEMPLATE = """Your template with {placeholders}..."""

def format_commit_details(commits: list[dict]) -> str:
    """Format commits for the prompt."""
    return "..."
```

Register it in `py_cli/llm/prompts/__init__.py`:

```python
from py_cli.llm.prompts import my_custom

PROMPTS = {
    "default": default,
    "clickhouse": clickhouse,
    "my_custom": my_custom,
}
```

### Adding a New CLI Command

Create a new file in `py_cli/commands/`:

```python
# py_cli/commands/my_command.py
import click

@click.command(name="my-command")
def my_command() -> None:
    """My custom command."""
    click.echo("Hello!")
```

Register it in `py_cli/cli.py`:

```python
from py_cli.commands.my_command import my_command

cli.add_command(my_command)
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please ensure:

1. Code follows the style guidelines (black, ruff, mypy)
2. Tests pass (`pytest`)
3. New features include tests
4. Documentation is updated

See [AGENTS.md](./AGENTS.md) for detailed development guidelines.
