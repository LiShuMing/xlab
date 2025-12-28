# Algorithm Implementations

This directory contains algorithm implementations, including LeetCode solutions, LCR (LintCode/LeetCode) problems, and common algorithm patterns.

## Coding
- 
- https://www.geeksforgeeks.org/
- https://www.hackerrank.com/

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

