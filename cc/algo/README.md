# Algorithm Implementations

This directory contains algorithm implementations, including LeetCode solutions, LCR (LintCode/LeetCode) problems, and common algorithm patterns.

## Coding Resources

- [GeeksforGeeks](https://www.geeksforgeeks.org/)
- [HackerRank](https://www.hackerrank.com/)

## Structure

- `src/leetcode/` - LeetCode problem solutions
- `src/lcr/` - LCR problem solutions
- `src/algo/` - Common algorithm implementations
  - `algo_sort.cc` - Sorting algorithms
  - `algo_binary_tree.cc` - Binary tree operations
  - `algo_graph.cc` - Graph algorithms
  - `algo_hash_table.cc` - Hash table implementations
  - `algo_cache.cc` - Cache algorithms (LRU, LFU, etc.)
  - `algo_lock_free_queue.cc` - Lock-free queue implementations
  - `algo_join_hash_map.cc` - Hash join implementations
  - `algo_aggregate.cc` - Aggregation algorithms
- `python/` - Python test files
- `src/oi/` - OI Wiki 学习笔记与配套例程（前缀和/差分、三分、树上差分、时间线段树 + 回滚并查集
  等），目录内 `.cc` 一律用 `oi_` 前缀命名（`oi_data.cc` / `oi_prefix_sum.cc` /
  `oi_total_binary_search.cc` / `oi_ternary_search.cc` / `oi_tree_difference.cc` /
  `oi_segment_tree_rollback_dsu.cc` 及 `_test`）；带 `main()` 的单文件都自带自测，
  `make run_oi_prefix_sum`、`make run_oi_ternary_search`、`make run_oi_tree_difference`
  可直接跑；代码遵循根目录 `AGENTS.md` 的 Google C++ Style 约定
- `oi/` - [Traced offline dynamic connectivity: time segment tree + rollback DSU](oi/README.md)
- `bin/` - Compiled binaries

## Building

The project uses a Makefile for building. You can build individual problems or all algorithms:

```bash
# Build a specific LeetCode problem
make leetcode_140

# Build a specific LCR problem
make lcr_159

# Build a specific algorithm
make algo_sort

# Build a specific OI note/program
make oi_prefix_sum

# Build all algorithms
make algo_all

# Clean all binaries
make clean

# Show help
make help
```

## Running

After building, executables are placed in the `bin/` directory:

```bash
./bin/leetcode_140
./bin/algo_sort
```

## Examples

Some of the implemented problems include:
- Dynamic Programming: leetcode_140, leetcode_322, leetcode_300
- Graph Algorithms: leetcode_1631, leetcode_863
- Tree Problems: leetcode_297, leetcode_235, leetcode_98
- String Problems: leetcode_5, leetcode_76, leetcode_424
- And many more...

## Testing

Python tests are available in `python/test/`:

```bash
cd python
pytest
```

