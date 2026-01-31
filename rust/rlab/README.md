# rlab - Rust Learning and Algorithms Library

[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange.svg)](https://www.rust-lang.org/)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue.svg)](LICENSE)

A Rust workspace containing a library of algorithms, data structures, and CLI tools for learning and benchmarking.

## Features

### Sorting Algorithms (16 implementations)

| Category | Algorithms | Time Complexity | Space |
|----------|-----------|-----------------|-------|
| **Simple** | Bubble, Selection, Insertion, Shell, Gnome, Comb | O(n²) | O(1) |
| **Efficient** | Quick, Merge, Heap, Tim, Intro | O(n log n) | O(1)-O(n) |
| **Integer** | Counting, Radix (LSD/MSD), Bucket, Flash | O(n)-O(n+k) | O(n+k) |

### Tools

- **Sorting Benchmark** - Compare algorithm performance on various data distributions
- **Addr2line** - Resolve addresses to source locations in binaries

### LeetCode Solutions

- 30+ classic LeetCode problems solved in Rust
- Organized by category: Array, Linked List, Tree, DP, Sorting, Misc
- All solutions include tests

## Quick Start

### Build

```bash
# Build entire workspace
cargo build --release

# Build specific crate
cargo build -p rlab        # Library only
cargo build -p rlab-tools  # Tools binary only
```

### Run Tests

```bash
# Run all tests
cargo test --workspace

# Run with output visible
cargo test -- --nocapture

# Run benchmarks
cargo bench -p rlab
```

### Using the Library

```rust
use rlab::sort::{quick_sort, merge_sort, is_sorted};

fn main() {
    let mut numbers = [3, 1, 4, 1, 5, 9, 2, 6];
    quick_sort(&mut numbers);
    assert!(is_sorted(&numbers));
}
```

### Using the CLI

```bash
# Sorting benchmark
cargo run --release -- --sort-bench
cargo run --release -- --sort-bench --sizes 1000,10000 --algorithms quick,merge,heap

# Addr2line (resolve address to source)
cargo run --release -- /usr/bin/ls 0x401000
```

## Project Structure

```
rlab/
├── lib/rlab/           # Core library crate
│   ├── src/common/sort/   # Sorting algorithms
│   ├── tests/             # Integration tests
│   └── benches/           # Criterion benchmarks
├── tools/rlab-tools/   # CLI tools binary
├── leetcode/           # LeetCode solutions
│   ├── src/
│   │   ├── array/         # Array problems
│   │   ├── linked_list/   # Linked list problems
│   │   ├── tree/          # Tree problems
│   │   ├── dp/            # Dynamic programming
│   │   ├── sorting/       # Sorting problems
│   │   └── misc/          # Miscellaneous
│   └── tests/
└── Cargo.toml          # Workspace root
```

## Algorithm Examples

### Quick Sort
```rust
use rlab::sort::quick_sort;

let mut arr = [3, 1, 4, 1, 5, 9, 2, 6];
quick_sort(&mut arr);
assert_eq!(arr, [1, 1, 2, 3, 4, 5, 6, 9]);
```

### Merge Sort (Stable)
```rust
use rlab::sort::merge_sort;

let mut arr = vec![(1, "a"), (2, "b"), (1, "c")];
merge_sort(&mut arr);
// Order of equal elements is preserved
```

### Radix Sort (Integers)
```rust
use rlab::sort::radix_sort_lsd;

let mut arr = [170, 45, 75, 90, 2, 802, 24, 66];
radix_sort_lsd(&mut arr);  // O(n) for fixed-size integers
```

## Benchmark Results

Example comparison on random data (10,000 elements):

```
| Algorithm       |       Size |         Mean |
|-----------------|------------|--------------|
| radix-lsd       |      10000 |         90µs |
| merge           |      10000 |        205µs |
| quick           |      10000 |        361µs |
| heap            |      10000 |        721µs |
```

Run your own:
```bash
cargo run --release -- --sort-bench --sizes 10000
```

## Workspace Layout

### `lib/rlab` - Library Crate
Core algorithms and data structures.

**Key modules:**
- `rlab::sort` - Sorting algorithms collection
- `rlab` - Math utilities (add, factorial, gcd)

### `tools/rlab-tools` - CLI Binary
Command-line utilities using the library.

**Commands:**
- `--sort-bench` - Run sorting benchmarks
- `--help` - Show usage information
- `<binary> <address>` - Addr2line functionality

### `leetcode` - LeetCode Solutions
Practice problems from LeetCode organized by category.

**Categories:**
- `array` - Two Sum, Max Subarray, Stock problems, etc.
- `linked_list` - Reverse, Merge, Cycle detection
- `tree` - Traversals, BST validation, Depth
- `dp` - Climbing Stairs, House Robber, LCS, LIS
- `sorting` - Binary search, Merge sorted arrays
- `misc` - Islands, Trapping Rain Water, Valid Parentheses

## Adding New Algorithms

1. **Sorting**: Add to appropriate file in `lib/rlab/src/common/sort/`
   - `simple.rs` - O(n²) algorithms
   - `efficient.rs` - O(n log n) algorithms
   - `integer.rs` - O(n) integer sorts

2. **Export**: Add to `lib/rlab/src/common/sort/mod.rs`

3. **Test**: Add unit tests in source file and integration tests in `lib/rlab/tests/`

## Dependencies

### Library
- `fastrand` - Fast random number generation

### Tools
- `gimli` - DWARF debug info parsing
- `object` - Object file parsing
- `memmap2` - Memory-mapped files
- `anyhow` - Error handling

### Dev
- `tokio` - Async runtime for tests
- `criterion` - Benchmarking framework

## License

Licensed under either of:

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT license ([LICENSE-MIT](LICENSE-MIT))

at your option.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Rust Community for excellent documentation and crates
- Algorithms inspiration from CLRS and various computer science resources
