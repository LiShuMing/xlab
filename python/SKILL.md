# Python Lab (python/pylab)

## Overview
Python laboratory for scripting, data processing, algorithms, and rapid prototyping. Uses pytest for testing with virtual environment isolation.

## Build System
- **Environment**: Virtual environments (`pyenv`, `venv`)
- **Dependencies**: `pip install -r requirements.txt`
- **Test Tool**: pytest
- **Test Command**: `cd python/pylab/test && make test`
- **Individual Tests**: `pytest -s test_file.py`

## Project Structure
```
python/
├── pylab/           # Main Python lab
│   ├── src/         # Source modules
│   ├── test/        # Pytest tests
│   └── requirements.txt
├── projects/        # Personal Python projects
├── ivm/             # Interactive VM / experiments
├── tools/           # Utility scripts
├── thirdparty/      # External packages
└── pyenv-3.13.5/    # Python version manager
```

## Key Concepts
- **Duck Typing**: Object behavior over type checking
- **Dynamic Typing**: Types checked at runtime
- **Interpreted**: No compilation step
- **Indentation**: Whitespace matters for blocks
- **Type Hints**: Optional static typing (Python 3.5+)

## Coding Conventions
- PEP 8 style guide (use `black`, `isort`)
- Type hints for function signatures
- Use `__main__` guard for CLI scripts
- Context managers (`with`) for resource management
- List/dict comprehensions for concise transformations
- Virtual environments for dependency isolation

## AI Vibe Coding Tips
- Use `typing` module for complex type hints
- Prefer `pathlib.Path` over `os.path`
- Use `dataclasses` for structured data (Python 3.7+)
- `enumerate()` instead of manual index tracking
- Generator expressions for memory efficiency
- `functools` for caching (`@lru_cache`)
- Underscore conventions: `_private`, `__dunder`, `_single_leading`
- Exception handling: specific over generic
- Consider `pydantic` for data validation
