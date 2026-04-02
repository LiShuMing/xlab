# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the pylab Python laboratory project.

## Project Architecture

pylab is a collection of Python experiments, algorithms, and tools for learning and research.

```
python/pylab/
├── leetcode/               # LeetCode solutions
│   ├── offer/              # 剑指Offer solutions
│   └── *.py                # Various LeetCode problems
├── test/                   # Unit tests
│   ├── test_basic.py
│   ├── test_sort.py
│   ├── test_clang.py
│   ├── test_numpy.py
│   ├── test_pandas.py
│   ├── test_duckdb.py
│   └── ...
├── uttest/                 # Additional tests
│   ├── test_skiplist.py
│   └── test_string.py
├── dbsp/                   # DBSP (Database Stream Processing)
│   ├── dbsp.py
│   └── test_dbsp.py
├── tools/                  # Utility tools
│   ├── pyspark/            # PySpark experiments
│   ├── benchmark/          # Benchmarking tools
│   ├── sr/                 # StarRocks utilities
│   └── pyplot.py
├── notebooks/              # Jupyter notebooks
├── requirements.txt        # Dependencies
└── test/Makefile           # Test runner
```

## Key Components

### LeetCode Solutions (`leetcode/`)
- Algorithm implementations for practice
- Organized by problem number
- Some organized by category (offer/ for 剑指Offer)

### Tests (`test/`)
- pytest-based test suite
- Sorting algorithm tests
- Database tests (DuckDB)
- ML/Vector tests (FAISS)
- Cryptography tests

### DBSP (`dbsp/`)
- Database Stream Processing experiments
- Incremental view maintenance concepts

### Tools (`tools/`)
- **pyspark/**: Apache Spark experiments with Iceberg
- **benchmark/**: Database benchmarking (MySQL, StarRocks)
- **sr/**: StarRocks utilities

## Dependencies

| Package | Purpose |
|---------|---------|
| pytest | Testing framework |
| numpy | Numerical computing |
| scipy | Scientific computing |
| pandas | Data manipulation |
| duckdb | In-process OLAP database |
| matplotlib | Plotting |
| faiss-cpu | Vector similarity search |
| cryptography | Cryptographic operations |
| beautifulsoup4 | Web scraping |
| requests | HTTP client |
| pyzmq | ZeroMQ bindings |
| gevent | Async networking |
| locust | Load testing |

## Building and Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
cd test && make test

# Run specific test
pytest -s test/test_sort.py

# Run with coverage
pytest --cov=.
```

## Coding Standards

1. **Python Version**: 3.10+
2. **Type Hints**: Use where appropriate
3. **Docstrings**: Document functions and modules
4. **PEP 8**: Follow style guidelines
5. **Testing**: Write tests for new algorithms

## Common Tasks

### Adding a LeetCode Solution

1. Create file in `leetcode/` or appropriate subdirectory
2. Include problem description in docstring
3. Add time/space complexity analysis
4. Optional: Add test in `test/`

```python
# leetcode/XXX.py
"""
Problem: Two Sum
Link: https://leetcode.com/problems/two-sum/

Time: O(n)
Space: O(n)
"""

def two_sum(nums: list[int], target: int) -> list[int]:
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []
```

### Adding a Test

```python
# test/test_example.py
import pytest

def test_example():
    assert True
```

### Adding a Tool

1. Create in `tools/` subdirectory
2. Add documentation
3. Add dependencies to requirements.txt if needed

## Prohibited Actions

1. **DO NOT** commit large data files
2. **DO NOT** hardcode credentials
3. **DO NOT** skip tests for algorithm code
4. **DO NOT** break existing test suite
5. **DO NOT** add dependencies without justification

## Performance Considerations

- Use numpy/pandas for numerical operations
- Use appropriate data structures
- Profile before optimizing
- Document complexity for algorithms

## Testing Strategy

- Unit tests for algorithms
- Integration tests for database code
- Benchmarks for performance-critical code
- Example notebooks for demonstrations

## Reading Order for New Contributors

1. `test/test_basic.py` - Basic Python patterns
2. `leetcode/` - Algorithm examples
3. `dbsp/` - Database concepts
4. `tools/` - Utility examples

## Communication Style

- Be practical and concise
- Include complexity analysis for algorithms
- Reference problem statements for LeetCode
- Show example usage in docstrings
