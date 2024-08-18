# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the ToyDB project.

## Project Architecture

ToyDB is a tiny, document-oriented database inspired by TinyDB. It provides a simple, Pythonic API for storing and querying JSON-like documents.

```
python/projects/py-toydb/
├── toydb/                  # Main package
│   ├── __init__.py         # Package exports
│   ├── db.py              # ToyDB class (main database)
│   ├── table.py           # Table class for document collections
│   ├── queries.py         # Query API (where, Query)
│   ├── storages.py        # Storage backends (JSON, Memory)
│   ├── middlewares.py     # Storage middleware (caching, compression)
│   ├── utils.py           # Utility functions
│   └── version.py         # Version info
├── tests/                  # Test suite
│   ├── conftest.py        # pytest fixtures
│   └── test_tables.py     # Table tests
├── pyproject.toml         # Poetry configuration
└── pytest.ini            # pytest configuration
```

## Key Components

### ToyDB Class (`toydb/db.py`)
Main database class that:
- Manages storage backend
- Creates and caches Table instances
- Provides access to default table
- Acts as context manager for proper cleanup

### Table Class (`toydb/table.py`)
Document collection that supports:
- Insert, update, remove operations
- Search with Query API
- Multiple document operations
- ID generation

### Query API (`toydb/queries.py`)
Document querying with:
- `where('field')` - Start a query
- Comparison operators: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical operators: `&` (and), `|` (or), `~` (not)
- Field existence checks
- Regex matching

### Storage Backends (`toydb/storages.py`)
- **JSONStorage**: Persist to JSON file
- **MemoryStorage**: In-memory storage (non-persistent)

### Middlewares (`toydb/middlewares.py`)
Storage wrappers for:
- Caching
- Compression
- Encryption (extensible)

## Dependencies

| Package | Purpose |
|---------|---------|
| pytest | Testing framework |
| pytest-cov | Coverage reporting |
| pytest-pycodestyle | Style checking |
| pytest-mypy | Type checking |
| pyyaml | YAML support |
| sphinx | Documentation |

## Building and Testing

```bash
# Install with Poetry
poetry install

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=toydb

# Type checking
poetry run pytest --mypy

# Code style
poetry run pytest --pycodestyle
```

## Coding Standards

1. **Python Version**: 3.8+ (with typing support)
2. **Type Hints**: Use for all public APIs
3. **Docstrings**: Google-style or Sphinx-style
4. **Testing**: pytest with fixtures
5. **Code Style**: pycodestyle compliant

## Common Tasks

### Adding a Storage Backend

1. Create class inheriting from `Storage` in `storages.py`
2. Implement `read()`, `write()`, `close()` methods
3. Add tests in `tests/`
4. Update documentation

```python
from toydb.storages import Storage

class MyStorage(Storage):
    def __init__(self, path: str):
        self.path = path

    def read(self) -> dict | None:
        # Read and return data dict
        pass

    def write(self, data: dict) -> None:
        # Write data dict
        pass

    def close(self) -> None:
        # Cleanup
        pass
```

### Adding a Query Operation

1. Add method to `Query` class in `queries.py`
2. Ensure it returns a callable for document matching
3. Add tests for the operation
4. Document usage

```python
# In queries.py
def matches(self, pattern: str) -> 'QueryInstance':
    """Match field against regex pattern."""
    def test(value):
        return re.match(pattern, str(value)) is not None
    return self._generate_test(test, ('matches', self._path, pattern))
```

### Using the Database

```python
from toydb import ToyDB, where
from toydb.storages import JSONStorage, MemoryStorage

# With file storage
db = ToyDB('data.json', storage=JSONStorage)

# With in-memory storage
db = ToyDB(storage=MemoryStorage)

# Insert documents
db.insert({'name': 'Alice', 'age': 30})
db.insert({'name': 'Bob', 'age': 25})

# Search
results = db.search(where('age') > 25)

# Update
db.update({'age': 31}, where('name') == 'Alice')

# Remove
db.remove(where('name') == 'Bob')

# Using tables
table = db.table('users')
table.insert({'name': 'Charlie'})

# Context manager (ensures proper cleanup)
with ToyDB('data.json') as db:
    db.insert({'data': 'value'})
```

## Prohibited Actions

1. **DO NOT** break backward compatibility without major version bump
2. **DO NOT** modify storage format without migration path
3. **DO NOT** skip tests for new features
4. **DO NOT** use `print()` for debugging - use logging
5. **DO NOT** modify `__init__.py` exports without consideration

## Performance Considerations

- ToyDB is optimized for simplicity, not high performance
- All data is loaded into memory
- Use appropriate storage for your use case
- Consider middleware for caching frequently accessed data

## Testing Strategy

- Unit tests for all public APIs
- Test both in-memory and file-based storage
- Test query operations comprehensively
- Test edge cases (empty DB, missing fields, etc.)

## Reading Order for New Contributors

1. `toydb/__init__.py` - Package overview and exports
2. `toydb/db.py` - Main ToyDB class
3. `toydb/table.py` - Table operations
4. `toydb/queries.py` - Query API
5. `toydb/storages.py` - Storage backends
6. `tests/test_tables.py` - Usage examples

## Communication Style

- Be concise and practical
- Include code examples
- Reference TinyDB documentation for context
- Explain design decisions clearly
