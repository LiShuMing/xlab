# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-XX-XX

### Added
- Initial release of rlab workspace
- Core library (`lib/rlab`) with sorting algorithms
  - Simple sorts: Bubble, Selection, Insertion, Shell, Gnome, Comb
  - Efficient sorts: Quick, Merge, Heap, Tim, Intro
  - Integer sorts: Counting, Radix (LSD/MSD), Bucket, Flash
  - Generic implementations for `Ord` types
  - Comprehensive test suite
- CLI tools (`tools/rlab-tools`)
  - Sorting benchmark utility
  - Addr2line implementation for DWARF debug info
- Bloom Filter implementations (`tools/bloom_filter`)
  - Classic Bloom Filter
  - Split Block Bloom Filter (SBBF)
  - XOR Filter
  - Performance benchmarks
- Lock-free data structures (`tools/lockfree-queue`)
  - MPSC (Multi-Producer Single-Consumer) queue
  - MPMC (Multi-Producer Multi-Consumer) queue
  - Benchmarks and examples
- Thread pool implementation (`tools/thread-pool`)
  - Configurable worker threads
  - Work-stealing support
  - Builder pattern API
- LeetCode solutions (`tools/leetcode`)
  - 30+ classic problems solved
  - Organized by category: Array, Linked List, Tree, DP, Sorting, Misc
  - Utility modules for common data structures

### Workspace Structure
```
rlab/
├── Cargo.toml              # Workspace root
├── lib/
│   └── rlab/               # Core library crate
│       ├── src/
│       │   ├── lib.rs
│       │   └── common/
│       │       ├── mod.rs
│       │       └── sort/
│       ├── tests/
│       └── benches/
└── tools/
    ├── rlab-tools/         # CLI tools
    ├── bloom_filter/       # Bloom filter variants
    ├── lockfree-queue/     # Lock-free queues
    ├── thread-pool/        # Thread pool
    └── leetcode/           # LeetCode solutions
```

### Algorithms

| Algorithm | Category | Time (avg) | Space | Stable |
|-----------|----------|------------|-------|--------|
| Bubble | Simple | O(n²) | O(1) | Yes |
| Selection | Simple | O(n²) | O(1) | No |
| Insertion | Simple | O(n²) | O(1) | Yes |
| Shell | Simple | O(n^1.3) | O(1) | No |
| Gnome | Simple | O(n²) | O(1) | Yes |
| Comb | Simple | O(n²) | O(1) | No |
| Quick | Efficient | O(n log n) | O(log n) | No |
| Merge | Efficient | O(n log n) | O(n) | Yes |
| Heap | Efficient | O(n log n) | O(1) | No |
| Tim | Efficient | O(n log n) | O(n) | Yes |
| Intro | Hybrid | O(n log n) | O(log n) | No |
| Counting | Integer | O(n+k) | O(n+k) | Yes |
| Radix LSD | Integer | O(d(n+b)) | O(n+b) | Yes |
| Radix MSD | Integer | O(d(n+b)) | O(n+b) | Yes |
| Bucket | Integer | O(n+k) | O(n+k) | Yes |
| Flash | Integer | O(n) | O(n) | No |

### Dependencies

- **Library**: `fastrand` (random number generation)
- **Tools**: `gimli`, `object`, `memmap2` (DWARF parsing), `anyhow` (errors)
- **Dev**: `criterion` (benchmarks), `tokio` (async tests)

## [0.0.1] - 2024-XX-XX

### Added
- Project initialization
- Basic workspace structure
- Initial sorting algorithm implementations
- Project scaffolding
