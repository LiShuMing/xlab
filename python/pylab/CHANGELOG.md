# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Planned
- More LeetCode solutions (target: 100 problems)
- Additional data structure implementations
- ML experiments with PyTorch
- More DuckDB analytics examples

## [0.2.0] - 2024-XX-XX

### Added
- **FAISS integration** (`test/test_faiss.py`)
  - Vector similarity search experiments
  - Index types: Flat, IVF, HNSW
  - Benchmarks for different index configurations

- **Cryptography experiments** (`test/test_cryptography.py`)
  - Symmetric encryption (AES)
  - Hashing (SHA-256, BLAKE2)
  - Key derivation

- **DBSP module** (`dbsp/`)
  - Database Stream Processing concepts
  - Incremental view maintenance
  - Test suite for stream operations

- **StarRocks utilities** (`tools/sr/`)
  - Audit log parsing
  - Data generation scripts

### Updated
- Upgraded numpy to 2.1
- Upgraded pandas to 2.2.3
- Upgraded DuckDB to 1.1.3
- Upgraded matplotlib to 3.10.0

## [0.1.0] - 2024-XX-XX

### Added
- Initial project structure
- **LeetCode solutions** (50+ problems)
  - Array problems: Two Sum, 3Sum, Container With Most Water
  - Dynamic Programming: LIS (300), LCS, Knapsack variants
  - Tree problems: Traversals, BST validation
  - Graph problems: BFS, DFS, Dijkstra
  - Sorting: Custom sort implementations
  - 剑指Offer problems (offer/ directory)

- **Test suite** (`test/`)
  - `test_basic.py` - Python fundamentals
  - `test_sort.py` - Sorting algorithm tests
  - `test_clang.py` - libclang experiments
  - `test_numpy.py` - NumPy operations
  - `test_pandas.py` - Pandas data manipulation
  - `test_duckdb.py` - DuckDB SQL queries
  - `test_radix_sort.py` - Radix sort implementation
  - `test_radix_join.py` - Database join algorithms

- **Unit tests** (`uttest/`)
  - `test_skiplist.py` - Skip list data structure
  - `test_string.py` - String algorithms

- **PySpark tools** (`tools/pyspark/`)
  - Apache Spark integration tests
  - Apache Iceberg table format support
  - TPC-H query implementations
  - TPC-DS query implementations
  - Hive metastore integration

- **Benchmarking tools** (`tools/benchmark/`)
  - MySQL benchmarking (sysbench, mysqlslap)
  - StarRocks benchmarking
  - Configuration templates
  - Master/worker distributed testing

- **Visualization** (`tools/pyplot.py`)
  - Matplotlib helper functions
  - Plotting utilities

- **Jupyter notebooks** (`notebooks/`)
  - PySpark experiments
  - Interactive data analysis

### Dependencies
- pytest / pytest-cov - Testing framework
- numpy - Numerical computing
- scipy - Scientific computing
- pandas - Data manipulation
- duckdb - In-process OLAP database
- matplotlib - Plotting
- beautifulsoup4 - Web scraping
- requests - HTTP client
- locust - Load testing
- pyzmq - ZeroMQ messaging
- gevent - Async networking
- faiss-cpu - Vector similarity search
- cryptography - Cryptographic operations

## [0.0.1] - 2024-XX-XX

### Added
- Project initialization
- Basic directory structure
- Initial requirements.txt
- First LeetCode solutions
