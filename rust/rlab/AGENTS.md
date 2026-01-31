# rlab - Rust Learning and Algorithms Benchmark

This is a Rust project for learning and experimenting with algorithms, data structures, and systems programming concepts.

## Project Structure

```
rlab/
├── Cargo.toml          # Project configuration
├── Cargo.lock          # Dependency lock file
├── src/
│   ├── lib.rs          # Library root with basic math functions
│   ├── main.rs         # Binary entry point with CLI
│   ├── addr2line.rs    # DWARF debug info parsing (address to line resolution)
│   ├── examples.rs     # Basic Rust learning examples
│   └── common/
│       ├── mod.rs      # Common utilities module
│       └── sort/
│           ├── mod.rs  # Sorting algorithms module
│           └── quick_sort.rs  # Quick sort implementation
├── tests/
│   ├── test_basic.rs       # Basic Rust concepts (ownership, borrowing)
│   ├── test_traits.rs      # Trait system demonstrations
│   ├── test_concurrency.rs # Thread and channel tests
│   ├── test_async.rs       # Async/await with Tokio
│   ├── test_sort.rs        # Sorting algorithm integration tests
│   └── test_examples.rs    # Examples module integration tests
```

## Building

```bash
# Build the library and binary
cargo build

# Build in release mode
cargo build --release
```

## Running Tests

```bash
# Run all tests
cargo test

# Run tests with output visible
cargo test -- --nocapture

# Run specific test file
cargo test --test test_sort

# Run doc tests
cargo test --doc
```

## Running the Binary

```bash
# Run learning examples
cargo run -- --examples

# Resolve address in binary (addr2line functionality)
cargo run -- ./path/to/binary 0x401234
```

## Key Modules

### `addr2line`
DWARF-based address-to-line resolution. Uses `gimli`, `object`, and `memmap2` crates.

**Note**: The full DWARF line number parsing is complex. Currently uses symbol table as fallback.

### `examples`
Basic Rust learning demonstrations:
- Constants and functions
- Closures and higher-order functions
- `Cow` (Clone on Write) for efficient conditional mutation

### `common::sort`
Sorting algorithms:
- `quick_sort` - Standard quicksort with last-element pivot
- `quick_sort_random` - Randomized pivot variant (better for sorted input)
- `is_sorted` - Verify if a slice is sorted

## Code Style

- Use `///` for public API documentation (doc comments)
- Use `//!` for module-level documentation
- Include doc tests in examples when possible
- Follow Rust naming conventions (`snake_case` for functions/variables, `CamelCase` for types)
- Use `#[allow(dead_code)]` for intentionally unused but exported items

## Dependencies

- `tokio` - Async runtime
- `gimli` - DWARF parsing
- `object` - Object file parsing
- `memmap2` - Memory-mapped files
- `anyhow` - Error handling
- `fastrand` - Fast random number generation (for randomized quicksort)

## Common Tasks

### Adding a new algorithm
1. Create a new file in `src/common/` or appropriate subdirectory
2. Add module declaration in parent `mod.rs`
3. Write comprehensive doc comments with examples
4. Add unit tests in the same file
5. Add integration tests in `tests/` if needed

### Adding a new example
1. Add to `src/examples.rs` or create new module
2. Export function in module
3. Add to `run_examples()` if it should be shown in `--examples`
4. Write integration tests in `tests/test_examples.rs`

### Fixing build warnings
```bash
# Check for issues
cargo clippy

# Fix automatically where possible
cargo fix
```

## Known Issues

1. **addr2line DWARF parsing**: Full line number resolution is incomplete due to complex gimli API. Symbol table fallback works.

2. **quick_sort bug fixed**: The original implementation had a bug where `_quick_sort` recursively called `partition` instead of itself. This has been fixed.

## Architecture Decisions

- **No unsafe code**: Removed `unsafe` transmute for lifetime extension; use proper lifetime management instead
- **Modular design**: Split main.rs into `addr2line.rs` and `examples.rs` modules
- **Trait-based APIs**: Use generics with trait bounds for flexibility
- **Error types**: Custom error types for each module rather than generic `anyhow` in library code
