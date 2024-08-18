# Project Rules

This document defines the coding standards and project rules for py-cli.

## Code Style

### Python Style Guide

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use [Black](https://black.readthedocs.io/) for code formatting (88 character line length)
- Use [isort](https://pycqa.github.io/isort/) for import sorting
- Use [ruff](https://docs.astral.sh/ruff/) for linting

### Type Hints

- **All functions must have type hints** (mandatory)
- Use `from __future__ import annotations` for forward references
- Use strict mypy mode: `mypy --strict`
- Prefer `pathlib.Path` over `os.path`
- Use `datetime` with timezone awareness

Example:

```python
from __future__ import annotations

from pathlib import Path
from datetime import datetime

def process_file(
    input_path: Path,
    output_path: Path | None = None,
) -> dict[str, int]:
    """Process a file and return statistics.

    Args:
        input_path: Path to input file
        output_path: Optional output path

    Returns:
        Dictionary of statistics
    """
    ...
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `git_client.py` |
| Classes | PascalCase | `GitClient` |
| Functions | snake_case | `get_commits()` |
| Variables | snake_case | `repo_path` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Private | _leading_underscore | `_internal_func()` |

### Docstrings

- Use Google-style docstrings
- All public functions must have docstrings
- Include Args, Returns, and Raises sections where applicable

Example:

```python
def analyze(
    self,
    repo_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Run analysis on a git repository.

    Args:
        repo_path: Path to git repository (default: current directory)
        output_path: Output file path (default: auto-generated)

    Returns:
        Path to generated report

    Raises:
        AnalysisError: If analysis fails
    """
```

## Testing

### Test Requirements

- All new code must include tests
- Target 80%+ code coverage for core modules
- Use pytest fixtures for common setup
- Mock external API calls (LLM, git when appropriate)

### Test Organization

```
tests/
├── conftest.py          # Shared fixtures
├── test_git_client.py   # Git client tests
├── test_llm_client.py   # LLM client tests
├── test_analyzer.py     # Analyzer tests
├── test_utils.py        # Utility function tests
└── test_prompts.py      # Prompt template tests
```

### Test Naming

- Test files: `test_<module>.py`
- Test classes: `Test<ClassName>`
- Test functions: `test_<description>`

Example:

```python
class TestGitClient:
    """Tests for GitClient class."""

    def test_init_valid_repo(self, git_repo: Path) -> None:
        """Test initializing with a valid git repo."""
        ...
```

## Error Handling

### Exception Hierarchy

```
PyCliError (base)
├── ConfigError
├── GitError
├── LLMError
├── AnalysisError
└── PromptNotFoundError
```

### Rules

1. **Never catch bare `Exception`** - be specific
2. **Wrap external API errors** in domain-specific exceptions
3. **Preserve original exception** using `from e`
4. **Provide helpful error messages** for CLI users

Example:

```python
try:
    result = self._run_git(args)
except subprocess.CalledProcessError as e:
    msg = f"Git command failed: {' '.join(cmd)}\nError: {e.stderr}"
    raise GitError(msg) from e
```

## Git Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Build, tooling changes

### Examples

```
feat(analyzer): add support for custom date ranges

fix(git-client): handle empty repositories gracefully

docs(readme): add installation instructions

test(llm): add tests for retry logic
```

## Project Structure

### Directory Organization

```
py_cli/
├── __init__.py          # Package version
├── __main__.py          # Entry point
├── cli.py               # Main CLI group
├── config.py            # Configuration
├── exceptions.py        # Custom exceptions
├── utils.py             # Utilities
├── commands/            # CLI subcommands
│   ├── __init__.py
│   ├── analyze.py
│   └── prompts.py
├── core/                # Business logic
│   ├── __init__.py
│   ├── git_client.py
│   └── analyzer.py
└── llm/                 # LLM module
    ├── __init__.py
    ├── client.py
    ├── models.py
    └── prompts/
        ├── __init__.py
        ├── default.py
        └── clickhouse.py
```

### Module Responsibilities

- **`cli.py`**: CLI entry point, command registration
- **`commands/`**: Individual CLI commands
- **`core/`**: Business logic (git operations, analysis)
- **`llm/`**: LLM API integration
- **`config.py`**: Configuration management
- **`exceptions.py`**: Custom exception classes
- **`utils.py`**: General utility functions

## Dependencies

### Adding Dependencies

1. Add to `pyproject.toml` `[project.dependencies]`
2. Add to `requirements.txt` for production
3. Add to `requirements-dev.txt` for development
4. Run `pip install -e ".[dev]"` to update

### Version Constraints

- Use `>=` for minimum versions
- Pin major versions for stability: `package>=1.0.0,<2.0.0`
- Document why specific versions are required

## Documentation

### Required Documentation

- `README.md`: User-facing documentation
- `AGENTS.md`: AI assistant guidelines
- `CHANGELOG.md`: Version history
- `RULES.md`: This file

### Code Documentation

- All public APIs must have docstrings
- Complex logic needs inline comments
- Type hints are mandatory (self-documenting)

## CI/CD

### Pre-commit Checks

Before committing, run:

```bash
# Format code
black py_cli tests
isort py_cli tests

# Lint
ruff check py_cli

# Type check
mypy py_cli --strict

# Run tests
pytest -s tests/
```

### Pull Request Requirements

1. All tests pass
2. Type checking passes (`mypy --strict`)
3. Linting passes (`ruff check`)
4. Code formatted with Black
5. Documentation updated (if needed)
6. CHANGELOG.md updated (if user-facing changes)

## Security

### API Keys

- Never commit API keys
- Use `~/.env` file for local development
- Use environment variables in production
- Rotate keys regularly

### Sensitive Data

- Never log API keys or tokens
- Sanitize error messages that might contain sensitive data
- Use secure defaults

## Performance

### Guidelines

- Use async I/O for concurrent LLM calls
- Limit commit analysis to prevent token overflow
- Cache results where appropriate
- Profile hot paths before optimizing

### Resource Limits

- Default max commits: 100
- Default max diff size: 100KB per commit
- LLM max tokens: 4096 (configurable)
