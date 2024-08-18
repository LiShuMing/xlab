# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the pylab Python laboratory project.

## Code Style

### Python Standards

- **Python Version**: 3.10+
- **Type Hints**: Encouraged for function signatures
- **Docstrings**: Google-style or PEP 257
- **Formatting**: PEP 8 compliant

### Commands

```bash
# Run tests
cd test && make test

# Run specific test
pytest -s test_sort.py

# Run with coverage
pytest --cov=..

# Type checking (optional)
mypy .
```

## Project Structure

```
python/pylab/
├── leetcode/               # Algorithm solutions
│   ├── offer/              # 剑指Offer (Chinese problems)
│   └── *.py                # Individual solutions
├── test/                   # Test suite
│   ├── Makefile            # Test runner config
│   ├── test_basic.py       # Basic Python tests
│   ├── test_sort.py        # Sorting algorithm tests
│   ├── test_clang.py       # libclang tests
│   ├── test_numpy.py       # NumPy tests
│   ├── test_pandas.py      # Pandas tests
│   ├── test_duckdb.py      # DuckDB tests
│   ├── test_faiss.py       # Vector index tests
│   └── test_cryptography.py # Crypto tests
├── uttest/                 # Additional unit tests
│   ├── test_skiplist.py
│   └── test_string.py
├── dbsp/                   # Database Stream Processing
│   ├── dbsp.py
│   └── test_dbsp.py
├── tools/                  # Utilities
│   ├── pyspark/            # Spark experiments
│   ├── benchmark/          # DB benchmarking
│   ├── sr/                 # StarRocks tools
│   └── pyplot.py
├── notebooks/              # Jupyter notebooks
├── requirements.txt        # Dependencies
└── .python-version         # pyenv version file
```

## Naming Conventions

- **Modules**: `snake_case.py`
- **Functions**: `snake_case()`
- **Classes**: `PascalCase`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Private**: `_leading_underscore`

## Algorithm Standards

### LeetCode Solutions

1. **File Header**: Include problem link and description
2. **Complexity Analysis**: Time and space complexity
3. **Solution Approach**: Brief explanation
4. **Type Hints**: For function signatures

```python
"""
Problem 300: Longest Increasing Subsequence
Link: https://leetcode.com/problems/longest-increasing-subsequence/

Given an integer array nums, return the length of the longest strictly increasing subsequence.

Example:
    Input: nums = [10,9,2,5,3,7,101,18]
    Output: 4

Time Complexity: O(n log n)
Space Complexity: O(n)
"""

from typing import List
import bisect

def length_of_lis(nums: List[int]) -> int:
    """
    Find length of longest increasing subsequence using patience sorting.

    Args:
        nums: List of integers

    Returns:
        Length of LIS
    """
    tails = []
    for num in nums:
        idx = bisect.bisect_left(tails, num)
        if idx == len(tails):
            tails.append(num)
        else:
            tails[idx] = num
    return len(tails)
```

### Testing Algorithms

```python
# test/test_example.py
import pytest
from leetcode.example import solution

class TestSolution:
    def test_example_1(self):
        assert solution([1, 2, 3]) == 6

    def test_example_2(self):
        assert solution([]) == 0

    def test_edge_case(self):
        assert solution([0]) == 0
```

## Testing Requirements

### Test Structure

- Use `pytest` framework
- Group related tests in classes
- Use descriptive test names
- Include edge cases

### Running Tests

```bash
# All tests
cd test && make test

# Specific test file
pytest -s test_sort.py

# With verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Test Coverage

Target coverage for:
- Algorithm implementations
- Database operations
- Tool utilities

Skip coverage for:
- One-off experiments
- Notebook code
- Benchmark scripts

## Documentation

### Code Documentation

- Module docstrings explain purpose
- Function docstrings include args/returns
- Complex algorithms include explanation
- Include example usage

```python
def quick_sort(arr: list[int]) -> list[int]:
    """
    Sort array using quicksort algorithm.

    Quicksort is a divide-and-conquer algorithm that picks a 'pivot'
    element and partitions the array around it.

    Args:
        arr: List of integers to sort

    Returns:
        New sorted list (does not modify input)

    Example:
        >>> quick_sort([3, 1, 4, 1, 5])
        [1, 1, 3, 4, 5]

    Time: O(n log n) average, O(n²) worst case
    Space: O(log n) for recursion
    """
    # implementation...
```

### README Files

Tool directories should include README explaining:
- Purpose
- Usage
- Dependencies
- Example

## Dependencies

### Core Dependencies

```
pytest          # Testing framework
pytest-cov      # Coverage
numpy           # Numerical computing
scipy           # Scientific computing
pandas          # Data analysis
duckdb          # OLAP database
matplotlib      # Plotting
requests        # HTTP client
```

### Specialized Dependencies

```
faiss-cpu       # Vector similarity
cryptography    # Cryptographic operations
beautifulsoup4  # HTML parsing
locust          # Load testing
pyzmq           # Messaging
gevent          # Async networking
```

### Adding Dependencies

1. Add to `requirements.txt`
2. Pin major versions: `package == X.Y.Z`
3. Add comment explaining purpose
4. Update this document

## Performance Guidelines

### For Algorithms

- Document Big-O complexity
- Use appropriate data structures
- Consider trade-offs clearly
- Benchmark when uncertain

### For Data Processing

- Use vectorized numpy/pandas operations
- Avoid Python loops for large data
- Use generators for streaming
- Profile before optimizing

### Example

```python
# Bad - Python loop
result = []
for x in data:
    result.append(x * 2)

# Good - Vectorized
import numpy as np
result = np.array(data) * 2

# Good - Generator
result = (x * 2 for x in data)
```

## Database Code

### DuckDB Usage

```python
import duckdb

# In-memory database
conn = duckdb.connect()

# Query
df = conn.execute("SELECT * FROM table").fetchdf()

# Register pandas DataFrame
conn.register('my_df', df)
```

### Best Practices

- Close connections properly
- Use context managers
- Parameterize queries
- Handle large results with chunking

## Git Workflow

### Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New algorithm or feature
- `fix`: Bug fix
- `test`: Test additions/changes
- `docs`: Documentation
- `refactor`: Code restructuring
- `perf`: Performance improvement

Examples:
```
feat: add solution for LeetCode 300 (LIS)
fix: correct quicksort partition logic
test: add edge cases for sort algorithms
docs: add complexity analysis to README
```

## Prohibited Patterns

1. **No bare excepts**: Use `except Exception:` minimum
2. **No mutable defaults**: Use `None` and check
3. **No global state**: Pass state explicitly
4. **No hardcoded paths**: Use path joining
5. **No print debugging**: Use logging or remove

```python
# Bad
def bad(items=[]):
    items.append(1)
    return items

# Good
def good(items=None):
    if items is None:
        items = []
    items.append(1)
    return items
```

## Security Considerations

1. Never commit credentials
2. Use environment variables for secrets
3. Validate inputs
4. Use parameterized queries
5. Don't eval() untrusted input

## Jupyter Notebooks

- Clear outputs before committing
- Include markdown explanations
- Keep cells runnable in order
- Document cell purpose

## Benchmarking

Use `tools/benchmark/` for performance testing:
- Document test setup
- Include reproducible steps
- Report environment details
- Compare against baselines
