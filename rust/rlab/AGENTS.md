# rlab - Rust Learning and Algorithms Library

This is a Rust workspace containing a library of algorithms/data structures and CLI tools.

## Workspace Structure

```
rlab/
├── Cargo.toml              # Workspace root
├── Cargo.lock              # Workspace lock file
├── lib/
│   └── rlab/               # Core library crate
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs      # Library root
│           └── common/
│               ├── mod.rs
│               └── sort/   # Sorting algorithms
│                   ├── mod.rs
│                   ├── benchmark.rs
│                   ├── simple.rs       # O(n²) sorts
│                   ├── efficient.rs    # O(n log n) sorts
│                   ├── integer.rs      # O(n) sorts
│                   └── quick_sort.rs
│               └── (more modules...)
│       └── tests/          # Integration tests
├── tools/
│   └── rlab-tools/         # CLI tools binary
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs     # CLI entry point
│           └── addr2line.rs # DWARF address resolution
└── benches/                # Criterion benchmarks (placeholder)
```

## Crates

### `lib/rlab` - Core Library

The library crate provides:

- **Sorting Algorithms** (`rlab::sort`):
  - Simple: Bubble, Selection, Insertion, Shell, Gnome, Comb
  - Efficient: Quick, Merge, Heap, Tim, Intro
  - Integer: Counting, Radix (LSD/MSD), Bucket, Flash
  - Benchmarking utilities

- **Math Utilities** (`rlab`):
  - `add()` - Simple addition
  - `factorial()` - Factorial calculation
  - `gcd()` - Greatest common divisor

### `tools/rlab-tools` - CLI Tools

Command-line utilities:

1. **Sorting Benchmarks** (`--sort-bench`):
   ```bash
   rlab --sort-bench
   rlab --sort-bench --sizes 1000,10000 --algorithms quick,merge,heap
   ```

2. **Addr2line** - Address to source location:
   ```bash
   rlab /path/to/binary 0x401234
   ```

## Building

```bash
# Build entire workspace
cargo build

# Build in release mode
cargo build --release

# Build specific crate
cargo build -p rlab
cargo build -p rlab-tools
```

## Testing

```bash
# Run all tests
cargo test

# Run tests for specific crate
cargo test -p rlab
cargo test -p rlab-tools

# Run with output visible
cargo test -- --nocapture
```

## Running Tools

```bash
# Run sorting benchmarks
cargo run --release -- --sort-bench

# Run with custom options
cargo run --release -- --sort-bench \
  --sizes 1000,10000,100000 \
  --algorithms quick,merge,heap,radix-lsd \
  --distributions random,sorted,reverse

# Run addr2line
cargo run --release -- /usr/bin/ls 0x401000
```

## Adding New Code

### Adding a sorting algorithm

1. Add implementation to appropriate file:
   - `lib/rlab/src/common/sort/simple.rs` - O(n²) algorithms
   - `lib/rlab/src/common/sort/efficient.rs` - O(n log n) algorithms  
   - `lib/rlab/src/common/sort/integer.rs` - O(n) integer algorithms

2. Export in `lib/rlab/src/common/sort/mod.rs`:
   ```rust
   pub use your_file::your_sort;
   ```

3. Add to `SortAlgorithm` enum for benchmark support

4. Add unit tests in the same file

5. Add integration tests in `lib/rlab/tests/test_sort.rs`

### Adding a new tool

1. Add module to `tools/rlab-tools/src/`
2. Import and use in `tools/rlab-tools/src/main.rs`
3. Add CLI argument parsing

### Adding a new data structure

1. Create module in `lib/rlab/src/`
2. Export in `lib/rlab/src/lib.rs`
3. Add unit tests
4. Add integration tests in `lib/rlab/tests/`

## Dependencies

### Library (`lib/rlab`)
- `fastrand` - Fast random number generation

### Tools (`tools/rlab-tools`)
- `rlab` - The library crate
- `gimli` - DWARF parsing
- `object` - Object file parsing
- `memmap2` - Memory-mapped files
- `anyhow` - Error handling

## Algorithm Complexity Summary

| Algorithm | Time (avg) | Space | Stable | Category |
|-----------|------------|-------|--------|----------|
| Bubble | O(n²) | O(1) | Yes | Simple |
| Selection | O(n²) | O(1) | No | Simple |
| Insertion | O(n²) | O(1) | Yes | Simple |
| Shell | O(n^1.3) | O(1) | No | Simple |
| Quick | O(n log n) | O(log n) | No | Efficient |
| Merge | O(n log n) | O(n) | Yes | Efficient |
| Heap | O(n log n) | O(1) | No | Efficient |
| Tim | O(n log n) | O(n) | Yes | Hybrid |
| Intro | O(n log n) | O(log n) | No | Hybrid |
| Counting | O(n+k) | O(n+k) | Yes | Integer |
| Radix | O(d(n+b)) | O(n+b) | Yes | Integer |
| Bucket | O(n+k) | O(n+k) | Yes | Integer |
