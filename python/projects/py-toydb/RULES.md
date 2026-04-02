# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the ToyDB project.

## Code Style

### Python Standards

- **Python Version**: 3.8+ (type hints required)
- **Type Hints**: Use for all function signatures and public APIs
- **Docstrings**: Sphinx-style with reStructuredText
- **Code Style**: PEP 8 compliant (enforced via pycodestyle)

### Commands

```bash
# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=toydb

# Type checking
poetry run pytest --mypy

# Code style
poetry run pytest --pycodestyle

# All checks
poetry run pytest --cov=toydb --mypy --pycodestyle
```

## Project Structure

```
python/projects/py-toydb/
├── toydb/                  # Main package
│   ├── __init__.py         # Package exports and docs
│   ├── db.py              # ToyDB main class
│   ├── table.py           # Table (document collection)
│   ├── queries.py         # Query API
│   ├── storages.py        # Storage backends
│   ├── middlewares.py     # Storage middleware
│   ├── utils.py           # Utility functions
│   └── version.py         # Version string
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── conftest.py        # pytest fixtures
│   └── test_tables.py     # Table tests
├── pyproject.toml         # Poetry config
└── pytest.ini            # pytest config
```

## Naming Conventions

- **Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case()`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Private**: `_leading_underscore`
- **Type Variables**: `PascalCase` descriptive names

## API Design Principles

### Fluent Interface

Query API uses fluent method chaining:

```python
# Good - Fluent and readable
db.search(where('name').matches('^A') & (where('age') > 25))

# Good - Clear logical grouping
db.search(
    (where('type') == 'user') &
    (where('status').one_of(['active', 'pending']))
)
```

### Type Hints

All public APIs must have type hints:

```python
from typing import Dict, List, Iterator, Optional, Type, Any, Callable

def search(self, cond: Optional[Callable[[Dict], bool]]) -> List[Dict]:
    """
    Search for documents matching the condition.

    :param cond: Query condition callable
    :returns: List of matching documents
    """
    ...
```

### Documentation

Use Sphinx-style docstrings:

```python
def insert(self, document: Dict[str, Any]) -> int:
    """
    Insert a new document into the table.

    :param document: The document to insert
    :returns: The new document ID
    :raises ValueError: If document is not a dict

    Example::

        >>> db.insert({'name': 'Alice', 'age': 30})
        1
    """
```

## Testing Requirements

### Test Structure

```python
# tests/test_example.py
import pytest
from toydb import ToyDB, where
from toydb.storages import MemoryStorage

class TestExample:
    def setup_method(self):
        """Set up test fixtures."""
        self.db = ToyDB(storage=MemoryStorage)

    def teardown_method(self):
        """Clean up after tests."""
        self.db.close()

    def test_insert(self):
        """Test document insertion."""
        doc_id = self.db.insert({'name': 'test'})
        assert doc_id == 1

    def test_search(self):
        """Test document search."""
        self.db.insert({'name': 'Alice', 'age': 30})
        results = self.db.search(where('age') > 25)
        assert len(results) == 1
```

### Fixtures

Use pytest fixtures for common setup:

```python
# tests/conftest.py
import pytest
from toydb import ToyDB
from toydb.storages import MemoryStorage

@pytest.fixture
def db():
    """Create a fresh in-memory database."""
    db = ToyDB(storage=MemoryStorage)
    yield db
    db.close()

@pytest.fixture
def populated_db(db):
    """Create a database with sample data."""
    db.insert({'name': 'Alice', 'age': 30, 'city': 'NYC'})
    db.insert({'name': 'Bob', 'age': 25, 'city': 'LA'})
    db.insert({'name': 'Charlie', 'age': 35, 'city': 'NYC'})
    return db
```

## Storage Backend Guidelines

### Creating a Storage

All storages must inherit from `Storage` base class:

```python
from typing import Dict, Optional
from toydb.storages import Storage

class CustomStorage(Storage):
    """
    Custom storage implementation.

    :param path: Path to storage location
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._handle = None

    def read(self) -> Optional[Dict]:
        """
        Read data from storage.

        :returns: Data dict or None if empty
        """
        # Implementation
        pass

    def write(self, data: Dict) -> None:
        """
        Write data to storage.

        :param data: Data to persist
        """
        # Implementation
        pass

    def close(self) -> None:
        """Close storage and cleanup resources."""
        if self._handle:
            self._handle.close()
```

### Storage Considerations

1. **Thread Safety**: Storage should be thread-safe
2. **Atomic Writes**: Ensure data integrity
3. **Error Handling**: Raise appropriate exceptions
4. **Resource Cleanup**: Implement `close()` properly

## Query API Design

### Query Operations

```python
# Comparison
where('field') == value
where('field') != value
where('field') < value
where('field') > value
where('field') <= value
where('field') >= value

# String
where('field').matches(regex)
where('field').contains(substring)
where('field').search(regex)

# Collection
where('field').one_of([a, b, c])
where('field').has(subquery)
where('field').any(subquery)
where('field').all(subquery)

# Logical
where('a') == 1 & where('b') == 2  # AND
where('a') == 1 | where('b') == 2  # OR
~where('a') == 1                    # NOT
```

### Custom Query Test

```python
def custom_test(value):
    """Custom test function for queries."""
    return isinstance(value, str) and value.startswith('prefix')

# Use with where
db.search(where('field').test(custom_test))
```

## Error Handling

### Exceptions

Use built-in exceptions appropriately:

- `ValueError`: Invalid arguments
- `KeyError`: Missing required fields
- `IOError`/`OSError`: Storage errors
- `RuntimeError`: Unexpected state

```python
def insert(self, document: Dict) -> int:
    if not isinstance(document, dict):
        raise ValueError(f"Document must be dict, got {type(document)}")
    # ... implementation
```

## Version Management

### Semantic Versioning

Follow SemVer (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking API changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

Update `toydb/version.py`:

```python
__version__ = '4.8.2'
```

## Documentation

### README

Include:
- Project description
- Installation instructions
- Quick start guide
- API overview
- Examples

### Changelog

Document all changes in `CHANGELOG.md`:

```markdown
## [4.8.2] - 2024-XX-XX

### Added
- New feature X

### Fixed
- Bug fix Y

### Changed
- Behavior change Z
```

## Middleware Development

### Creating Middleware

```python
from toydb.middlewares import Middleware
from toydb.storages import Storage

class CacheMiddleware(Middleware):
    """
    Caching middleware for storage.

    :param storage: Storage to wrap
    :param cache_size: Maximum cache entries
    """

    def __init__(self, storage: Storage, cache_size: int = 100) -> None:
        super().__init__(storage)
        self._cache: Dict = {}
        self._cache_size = cache_size

    def read(self) -> Optional[Dict]:
        if not self._cache:
            self._cache = self.storage.read() or {}
        return self._cache

    def write(self, data: Dict) -> None:
        self._cache = data.copy()
        self.storage.write(data)

    def flush(self) -> None:
        """Clear the cache."""
        self._cache.clear()
```

## Performance Guidelines

### Memory Usage

- ToyDB loads all data into memory
- Don't use for datasets > available RAM
- Use streaming for large operations when possible

### Query Optimization

- Simple equality checks are fastest
- Combine conditions efficiently
- Cache repeated queries

```python
# Good - Single pass
db.search((where('a') == 1) & (where('b') == 2))

# Less efficient - Multiple passes
results = db.search(where('a') == 1)
results = [r for r in results if r['b'] == 2]
```

## Git Workflow

### Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `perf`: Performance
- `test`: Tests

Examples:
```
feat: add regex search operator
fix: handle None values in queries
docs: update API examples
```

## Release Process

1. Update version in `version.py`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Build package: `poetry build`
5. Publish: `poetry publish`
