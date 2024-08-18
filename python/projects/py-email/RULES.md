# RULES.md

Project rules and coding standards for py-email.

## Code Naming Conventions

### Files and Modules

- **Source files**: `snake_case.py`
- **Test files**: `test_<module>.py`
- **Module directories**: Short, descriptive, lowercase (e.g., `gmail/`, `llm/`, `db/`)

### Classes

- **Pydantic models**: PascalCase, descriptive (e.g., `EmailSummary`, `DailyDigest`)
- **Exceptions**: PascalCase with `Error` suffix (e.g., `LLMSummarizationError`)
- **Repository classes**: PascalCase with repository purpose (e.g., `MessageRepository`)

### Functions and Methods

- **Public functions**: `snake_case`, verb-first (e.g., `sync_messages()`, `build_digest()`)
- **Private functions**: `_snake_case` with leading underscore
- **Test functions**: `test_<functionality>_<condition>` (e.g., `test_cleaner_handles_empty_html`)

### Variables

- **Constants**: `SCREAMING_SNAKE_CASE` at module level
- **Variables**: `snake_case`
- **Private variables**: `_snake_case` with leading underscore
- **Type variables**: PascalCase (e.g., `T`, `ModelType`)

## Commit Message Convention

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Build/config changes

Scopes:
- `gmail`: Gmail API module
- `parser`: HTML parsing module
- `db`: Database layer
- `llm`: LLM summarization
- `digest`: Digest generation
- `cli`: Command-line interface
- `server`: Web server
- `config`: Configuration

Examples:
```
feat(digest): add HTML rendering with Jinja2
fix(llm): handle JSON parsing errors gracefully
test(db): add repository tests for edge cases
docs: update README with setup instructions
```

## Testing Requirements

### Coverage Targets

- **Core modules**: 80%+ coverage
- **Utility functions**: 90%+ coverage
- **Error handling**: All exception paths tested

### Test Structure

```python
def test_<function>_<condition>():
    """Test that <function> handles <condition> correctly."""
    # Arrange
    input_data = ...
    expected = ...

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected
```

### Required Test Cases

For each public function/method, include tests for:
1. **Happy path**: Normal input produces expected output
2. **Edge cases**: Empty input, boundary values
3. **Error handling**: Invalid input raises appropriate exceptions
4. **Integration**: Works correctly with dependent components (use mocks)

### Mocking Guidelines

- Mock external API calls (Gmail, LLM)
- Mock database for unit tests (use real SQLite for integration tests)
- Use `pytest-mock` fixture (`mocker`)

## Documentation Requirements

### Docstrings

All public functions, classes, and methods must have docstrings following Google style:

```python
def function(param1: str, param2: int | None = None) -> bool:
    """Short description of function.

    Longer description if needed, explaining the purpose
    and any important implementation details.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to None.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.
        CustomError: When something else goes wrong.

    Example:
        >>> result = function("test", 42)
        >>> print(result)
        True
    """
```

### Module Docstrings

Each module should have a docstring explaining its purpose:

```python
"""Email synchronization module.

Handles Gmail API authentication and incremental sync using historyId.
Provides functions for fetching new messages and maintaining sync state.
"""
```

### Type Hints

- All function parameters must have type hints
- All function return values must have type hints
- Use modern Python 3.11+ syntax:
  - `str | None` instead of `Optional[str]`
  - `list[str]` instead of `List[str]`
  - `dict[str, int]` instead of `Dict[str, int]`

## Code Quality Standards

### Ruff Configuration

Configured in `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

### Pre-commit Checklist

Before committing:
1. Run `ruff check src/ tests/` - must pass with no errors
2. Run `ruff format src/ tests/` - must not produce changes
3. Run `pytest tests/ -v` - all tests must pass
4. Run `mypy --strict src/` - no type errors

### Import Ordering

```python
# 1. Standard library imports
import sqlite3
from datetime import datetime
from pathlib import Path

# 2. Third-party imports
import structlog
from pydantic import BaseModel

# 3. Local imports
from my_email.config import Settings
from my_email.db.models import EmailSummary
```

## Error Handling Standards

### Exception Hierarchy

Define custom exceptions for domain-specific errors:

```python
class MyEmailError(Exception):
    """Base exception for my-email."""
    pass

class GmailError(MyEmailError):
    """Gmail API related errors."""
    pass

class LLMError(MyEmailError):
    """LLM API related errors."""
    pass
```

### Retry Logic

Use `tenacity` for external API calls:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=10),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError))
)
def call_external_api():
    ...
```

### Error Messages

- Be specific about what went wrong
- Include relevant context (without exposing secrets)
- Suggest possible solutions if applicable

## Database Standards

### Schema Changes

1. Update schema in `repository.py`
2. Add migration logic if needed
3. Update all affected queries
4. Add tests for new schema

### Query Style

- Use parameterized queries (never string interpolation)
- Prefer explicit column lists over `SELECT *`
- Use type annotations for query results

## Configuration Standards

### Environment Variables

- Use UPPER_CASE for env var names
- Group related vars with prefix (e.g., `GMAIL_`, `LLM_`)
- Provide defaults only for non-sensitive values
- Document all env vars in `.env.example`

### Pydantic Settings

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        frozen=True,
    )

    # Required fields (no default)
    gmail_credentials_file: Path

    # Optional fields with defaults
    db_path: Path = Path('data/my_email.db')
    log_level: str = 'INFO'
```

## Change Tracking

All changes must be documented in `CHANGE_LOGS.md` with:
- Date of change
- Affected modules/files
- Description of changes
- Breaking changes (if any)
