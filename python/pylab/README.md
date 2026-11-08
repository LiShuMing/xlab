# pylab - Python Laboratory

A collection of Python experiments, algorithms, and tools for learning and research.

## Overview

pylab is a personal laboratory for exploring Python concepts, algorithms, data structures, and tools. It includes LeetCode solutions, database experiments, data processing utilities, and benchmarking tools.

## Features

### Algorithm Practice
- **LeetCode Solutions**: 50+ problems solved
  - Array and string manipulation
  - Dynamic programming
  - Tree and graph algorithms
  - Sorting and searching
  - 剑指Offer (Chinese interview problems)

### Database Experiments
- **DBSP**: prototype moved to [`labs/ivm/dbsp/`](../../labs/ivm/dbsp/)
- **DuckDB**: In-process OLAP queries
- **Benchmarking**: MySQL and StarRocks performance testing

### Data Processing
- **PySpark**: Apache Spark with Iceberg integration
- **Pandas/Numpy**: Data manipulation and numerical computing
- **FAISS**: Vector similarity search experiments

### Testing & Utilities
- Comprehensive pytest suite
- Sorting algorithm benchmarks
- Cryptography experiments
- Visualization tools (matplotlib)

## Quick Start

### Installation

```bash
# Navigate to project
cd python/pylab

# Install dependencies
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
cd test && make test

# Run specific test file
pytest -s test_sort.py

# Run with coverage
pytest --cov=..
```

### Running LeetCode Solutions

```bash
# Run specific solution
python leetcode/300.py

# Run with test input
python -c "from leetcode.offer.47 import solve; print(solve([1,2,3]))"
```

### Distributed K-means learning experiment

Read [the overall design and experiment contract](DISTRIBUTED_KMEANS.md) first.
[distributed_kmeans.py](distributed_kmeans.py) compares a serial reference with
persistent spawn workers, unequal shards, a straggler and explicit failures.
It simulates synchronous distributed computation on one host, not network or
cluster performance. No Ray, Spark, service or account is required.

From the repository root, use a project-local environment:

```sh
python3 -m venv python/pylab/.venv
uv pip install --python python/pylab/.venv/bin/python numpy==2.1.0 pytest==8.3.5
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python/pylab/.venv/bin/python -m pytest python/pylab/test/test_distributed_kmeans.py -q
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python/pylab/.venv/bin/python python/pylab/distributed_kmeans.py
```

The CLI executes the complete matrix on 10,000 synthetic points. Use `--rows 1000`
for a smaller run. JSON and Markdown evidence go to a new, ignored
`.local/kmeans/<run-id>/` directory; `--output` must name a new directory.
Every comparison uses the same input and initial centers. Timing includes startup
and cleanup; a small parallel run may be slower than serial.

## Project Structure

```
python/pylab/
├── leetcode/               # LeetCode solutions
│   ├── offer/              # 剑指Offer problems
│   │   ├── 47.py           # Permutations II
│   │   └── 51.py           # Reverse Pairs
│   ├── 300.py              # Longest Increasing Subsequence
│   ├── 632.py              # Smallest Range Covering Elements
│   └── ...
├── test/                   # Test suite
│   ├── Makefile            # Test configuration
│   ├── test_basic.py       # Basic Python patterns
│   ├── test_sort.py        # Sorting algorithms
│   ├── test_numpy.py       # NumPy experiments
│   ├── test_pandas.py      # Pandas experiments
│   ├── test_duckdb.py      # DuckDB queries
│   ├── test_faiss.py       # Vector search
│   └── test_cryptography.py # Cryptography
├── uttest/                 # Unit tests
│   ├── test_skiplist.py    # Skip list implementation
│   └── test_string.py      # String algorithms
├── tools/                  # Utilities
│   ├── pyspark/            # Spark experiments
│   │   ├── test_spark.py
│   │   ├── pyspark_iceberg_tpch.py
│   │   └── pyspark_iceberg_tpcds.py
│   ├── benchmark/          # Database benchmarking
│   │   ├── run.py
│   │   ├── sysbench.sh
│   │   └── mysqlslap.sh
│   ├── sr/                 # StarRocks utilities
│   └── pyplot.py           # Plotting utilities
├── notebooks/              # Jupyter notebooks
│   └── test_pyspark.ipynb
└── requirements.txt        # Dependencies
```

## Dependencies

### Core
- pytest / pytest-cov - Testing
- numpy - Numerical computing
- scipy - Scientific computing
- pandas - Data manipulation

### Database
- duckdb - In-process OLAP
- (optional) pyspark - Apache Spark

### Specialized
- faiss-cpu - Vector similarity search
- cryptography - Cryptographic operations
- matplotlib - Plotting
- beautifulsoup4 - Web scraping
- requests - HTTP client
- locust - Load testing
- pyzmq - ZeroMQ messaging
- gevent - Async networking

## Algorithm Examples

### Dynamic Programming

```python
# leetcode/300.py - LIS
from typing import List
import bisect

def length_of_lis(nums: List[int]) -> int:
    """
    Longest Increasing Subsequence - O(n log n)
    Uses patience sorting with binary search.
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

### Sorting Test

```python
# test/test_sort.py
import pytest
from algorithms import quick_sort, merge_sort

class TestSorting:
    @pytest.mark.parametrize("sort_func", [quick_sort, merge_sort])
    def test_sort_basic(self, sort_func):
        arr = [3, 1, 4, 1, 5, 9, 2, 6]
        assert sort_func(arr) == [1, 1, 2, 3, 4, 5, 6, 9]

    def test_sort_empty(self):
        assert quick_sort([]) == []
```

## Database Experiments

### DuckDB

```python
import duckdb

conn = duckdb.connect()

# Query parquet
df = conn.execute("""
    SELECT * FROM 'data.parquet'
    WHERE date > '2024-01-01'
""").fetchdf()
```

## Benchmarking

### MySQL Benchmark

```bash
cd tools/benchmark
./sysbench.sh
```

### Custom Benchmark

```python
from benchmark import Benchmark

bench = Benchmark()
result = bench.run_query("SELECT COUNT(*) FROM large_table")
print(f"Query time: {result.duration_ms}ms")
```

## Development

### Adding a LeetCode Solution

1. Create file: `leetcode/XXX.py`
2. Include problem description
3. Add complexity analysis
4. Optional: Add test

```python
"""
Problem XXX: Problem Name
Link: https://leetcode.com/problems/XXX/

Description here...

Time: O(...)
Space: O(...)
"""

def solution(args):
    pass
```

### Running PySpark

```bash
# TPC-H queries on Iceberg
python tools/pyspark/pyspark_iceberg_tpch.py

# TPC-DS queries
python tools/pyspark/pyspark_iceberg_tpcds.py
```

## Testing Philosophy

- **Unit tests**: For algorithms and data structures
- **Integration tests**: For database operations
- **Exploratory tests**: For learning new libraries
- **Benchmarks**: For performance-critical code

## Future Plans

- [ ] Add more LeetCode solutions
- [ ] Implement more data structures
- [ ] Add ML experiments
- [ ] More visualization tools

## License

MIT License
