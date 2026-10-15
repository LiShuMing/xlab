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

```text
python/
├── pylab/           # Main Python lab
│   ├── src/         # Source modules
│   ├── test/        # Pytest tests
│   └── requirements.txt
├── projects/        # Personal Python projects
├── ivm/             # Incremental view maintenance experiments
├── tools/           # Utility scripts
├── thirdparty/      # External packages
└── llm_benchmark/   # LLM evaluation framework
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

## Migrated Python projects

| Former xlab path | Current home |
| --- | --- |
| `python/projects/py-cli/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-tools/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-optimizer1/` | [vela/research/optimizer-evidence](https://github.com/LiShuMing/vela/tree/main/research/optimizer-evidence) |
| `python/projects/py-optimizer2/` | [vela/research/optimizer-scanner](https://github.com/LiShuMing/vela/tree/main/research/optimizer-scanner) |
| `python/projects/py-pia/` | [carina/modules/product-intelligence](https://github.com/LiShuMing/carina/tree/main/modules/product-intelligence) |
| `python/projects/py-report/` | [carina/modules/research-report](https://github.com/LiShuMing/carina/tree/main/modules/research-report) |
| `python/projects/py-email/` | [lyra/modules/email-digest](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest) |
| `python/projects/py-learn/` | [lyra/modules/daily-learning](https://github.com/LiShuMing/lyra/tree/main/modules/daily-learning) |

Do not recreate these retired roots. Read the destination module guide before running commands.
The obsolete `projects/cron.sh` is removed without a stub. No installed scheduler has been inspected or changed; an old cron entry pointing to it will fail with a missing-file error until its owner removes or replaces that entry. Review destination setup and live-state handling separately; see [cleanup boundaries](../docs/meta/repository-cleanup.md).
