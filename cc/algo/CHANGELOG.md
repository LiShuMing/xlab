# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Planned
- More LeetCode hard problems
- Advanced graph algorithms (Tarjan, network flow)
- Segment tree and Fenwick tree implementations
- Trie data structure
- Union-Find (Disjoint Set Union)

## [1.0.0] - 2024-XX-XX

### Added
- Initial comprehensive algorithm collection
- **LeetCode Solutions** (150+ problems)
  - Array problems: Two Sum, 3Sum, Container With Most Water
  - String problems: Longest Palindrome, Minimum Window Substring
  - Tree problems: Binary Tree Traversals, LCA, Serialize/Deserialize
  - Graph problems: Course Schedule, Word Ladder, Clone Graph
  - DP problems: Longest Increasing Subsequence, Edit Distance, Knapsack variants
  - Greedy: Jump Game, Merge Intervals
  - Backtracking: N-Queens, Permutations, Combinations
  - Intervals: Meeting Rooms, Non-overlapping Intervals
  - Math: Integer to Roman, Pow(x, n)
  - Bit manipulation: Single Number, Counting Bits

- **LCR Problems** (100+ 剑指Offer solutions)
  - LCR 000-199: Comprehensive coverage of classic interview problems
  - Topics: Arrays, Strings, Linked Lists, Trees, Dynamic Programming
  - Chinese problem statements with solutions

- **Core Algorithm Implementations** (`src/algo/`)
  - `algo_sort.cc` - Sorting algorithms
    - Quicksort, Mergesort, Heapsort
    - Counting sort, Radix sort, Bucket sort
  - `algo_binary_tree.cc` - Binary tree operations
    - All traversals (inorder, preorder, postorder, level order)
    - BST operations (insert, delete, validate)
    - Advanced: serialization, LCA
  - `algo_graph.cc` - Graph algorithms
    - BFS, DFS implementations
    - Shortest path: Dijkstra, Bellman-Ford
    - Minimum spanning tree: Prim, Kruskal
    - Topological sorting
  - `algo_hash_table.cc` - Hash table implementations
    - Separate chaining
    - Open addressing (linear/quadratic probing)
  - `algo_cache.cc` - Cache algorithms
    - LRU Cache (Least Recently Used)
    - LFU Cache (Least Frequently Used)
  - `algo_lock_free_queue.cc` - Lock-free data structures
    - Michael-Scott queue
    - Memory ordering examples
  - `algo_join_hash_map.cc` - Hash join for databases
  - `algo_aggregate.cc` - Streaming aggregation
  - `algo_segment_tree.cc` - Range query data structure
  - `algo_thread_pool.cc` - Thread pool implementation
  - `algo_scheduler.cc` - Task scheduling algorithms
  - `algo_string.cc` - String algorithms (KMP, Rabin-Karp)
  - `algo_mem.cc` - Memory management patterns
  - `algo_crontab_with_queue.cc` - Cron-like scheduler
  - `algo_work_pool.cc` - Work stealing patterns
  - `algo_hilbert.cc` - Hilbert curve (spatial indexing)
  - `algo_zorder.cc` - Z-order curve (Morton codes)
  - `algo_bt_distance.cc` - Tree distance algorithms
  - `algo_basic.cc` - Fundamental algorithms
  - `algo_queue_with_stack.cc` - Queue using stacks

- **HackerRank Solutions** (`src/hackerrank/`)
  - String manipulation problems
  - Algorithm challenges

- **Daily Programmer Challenges** (`src/dailyprogrammer/`)
  - Reddit r/dailyprogrammer solutions
  - Various difficulty levels

- **Build System**
  - Makefile with pattern rules
  - Support for: leetcode, lcr, algo, hackerrank, dailyprogrammer
  - Run targets for build-and-execute
  - Test target for verification

- **Python Testing Utilities** (`python/`)
  - pytest configuration
  - Test generation scripts
  - Solution validators

### Project Structure
```
cc/algo/
├── src/
│   ├── leetcode/       (150+ files)
│   ├── lcr/            (100+ files)
│   ├── algo/           (20+ algorithm files)
│   ├── hackerrank/
│   ├── dailyprogrammer/
│   ├── msjd/
│   ├── linux/
│   └── include/fwd.h
├── python/
│   ├── test/
│   └── script/
├── bin/                (compiled binaries)
└── Makefile
```

## [0.9.0] - 2023-XX-XX

### Added
- Core algorithm collection
- Basic LeetCode solutions
- Initial Makefile

## [0.5.0] - 2022-XX-XX

### Added
- First algorithm implementations
- Sorting and basic data structures

## [0.1.0] - 2022-XX-XX

### Added
- Project initialization
- First LeetCode solutions

## Categories by Difficulty

### Easy (50+ problems)
- Array manipulations
- Basic string operations
- Simple tree traversals
- Hash table applications

### Medium (80+ problems)
- Two pointers
- Sliding window
- Binary search variants
- BFS/DFS
- Dynamic programming
- Backtracking
- Greedy algorithms

### Hard (20+ problems)
- Advanced DP
- Complex graph algorithms
- Hard string problems
- Optimization problems

## Algorithm Topics Covered

| Category | Algorithms | Problems |
|----------|-----------|----------|
| Arrays | Two pointers, sliding window, prefix sum | 30+ |
| Strings | KMP, regex, parsing | 15+ |
| Linked Lists | Fast/slow pointers, reversal | 10+ |
| Trees | DFS, BFS, BST operations | 25+ |
| Graphs | DFS, BFS, shortest path | 20+ |
| DP | 1D, 2D, interval, bitmask | 35+ |
| Greedy | Interval scheduling, Huffman | 10+ |
| Backtracking | Permutations, subsets, N-queens | 15+ |
| Sorting | Various algorithms | 10+ |
| Binary Search | Standard and variants | 15+ |
| Heap/Priority Queue | Top K, merge K sorted | 10+ |
| Union Find | Connected components | 5+ |
| Trie | Prefix matching | 5+ |
| Segment Tree | Range queries | 3+ |
| Bit Manipulation | XOR, bit masks | 10+ |
