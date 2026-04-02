# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the rlab Rust workspace.

## Code Style

### Rust Standards

- **Rust Edition**: 2021
- **Minimum Version**: 1.70+
- **Formatting**: Use `cargo fmt` with default settings
- **Linting**: Use `cargo clippy` with strict settings

### Formatting Commands

```bash
# Format all code
cargo fmt --all

# Check formatting without modifying
cargo fmt --all -- --check

# Run clippy lints
cargo clippy --all-targets --all-features -- -D warnings

# Check all crates
cargo check --workspace
```

### Naming Conventions

- **Modules**: `snake_case` (e.g., `sort`, `bloom_filter`)
- **Types/Traits**: `PascalCase` (e.g., `BloomFilter`, `SortAlgorithm`)
- **Functions/Variables**: `snake_case` (e.g., `quick_sort`, `is_sorted`)
- **Constants**: `SCREAMING_SNAKE_CASE` (e.g., `MAX_SIZE`)
- **Macros**: `snake_case!` (e.g., `vec!`, `println!`)

## Architecture Principles

### Module Organization

```
lib/rlab/src/
├── lib.rs              # Crate root - re-exports public API
├── common/
│   ├── mod.rs          # Common module exports
│   └── sort/           # Sorting algorithms submodule
│       ├── mod.rs      # Sort module exports
│       ├── simple.rs   # O(n²) algorithms
│       ├── efficient.rs # O(n log n) algorithms
│       ├── integer.rs  # O(n) integer sorts
│       ├── quick_sort.rs # Quick sort variants
│       └── benchmark.rs # Benchmark utilities
```

### Public API Design

1. **Re-export at crate root**: Public items should be accessible from `rlab::`
2. **Module-level organization**: Group related functionality in modules
3. **Trait-based interfaces**: Use traits for shared behavior (e.g., `Sorter`)
4. **Generic where appropriate**: Support multiple types when possible

Example:
```rust
// In lib.rs
pub mod sort;
pub use sort::{quick_sort, merge_sort, is_sorted};

// In sort/mod.rs
pub use simple::{bubble_sort, insertion_sort};
pub use efficient::{quick_sort, merge_sort, heap_sort};
pub use integer::{counting_sort, radix_sort_lsd};
```

### Error Handling

- Use `Result<T, E>` for fallible operations
- Use `Option<T>` for nullable values
- Prefer `thiserror` for library error types
- Prefer `anyhow` for application error handling
- Avoid `unwrap()` and `expect()` in production code

```rust
// Good
fn divide(a: f64, b: f64) -> Option<f64> {
    if b == 0.0 { None } else { Some(a / b) }
}

// Good
fn parse_config(path: &Path) -> Result<Config, ConfigError> {
    let content = std::fs::read_to_string(path)?;
    toml::from_str(&content).map_err(ConfigError::from)
}
```

### Documentation

- **All public items must have doc comments** (`///`)
- Include examples in doc comments
- Document panics, errors, and safety requirements
- Use `//!` for module-level documentation

```rust
/// Sorts a slice using quicksort algorithm.
///
/// # Time Complexity
/// - Average: O(n log n)
/// - Worst: O(n²) - rare with randomized pivot
///
/// # Space Complexity
/// O(log n) for recursion stack
///
/// # Examples
/// ```
/// use rlab::sort::quick_sort;
///
/// let mut arr = [3, 1, 4, 1, 5];
/// quick_sort(&mut arr);
/// assert_eq!(arr, [1, 1, 3, 4, 5]);
/// ```
pub fn quick_sort<T: Ord>(arr: &mut [T]) {
    // ...
}
```

## Testing Requirements

### Test Structure

```
lib/rlab/
├── src/               # Source code
├── tests/             # Integration tests
│   ├── test_basic.rs
│   ├── test_sort.rs
│   └── ...
└── benches/           # Benchmarks
    └── sort_benchmark.rs
```

### Test Standards

- **Unit tests**: In the same file as the code (`#[cfg(test)]` module)
- **Integration tests**: In `tests/` directory
- **Documentation tests**: Examples in doc comments
- **Benchmarks**: Use Criterion in `benches/` directory

```rust
// Unit test in source file
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bubble_sort_basic() {
        let mut arr = [3, 1, 4, 1, 5];
        bubble_sort(&mut arr);
        assert_eq!(arr, [1, 1, 3, 4, 5]);
    }

    #[test]
    fn test_bubble_sort_empty() {
        let mut arr: [i32; 0] = [];
        bubble_sort(&mut arr);
        assert!(arr.is_empty());
    }
}
```

### Running Tests

```bash
# Run all tests
cargo test --workspace

# Run tests for specific crate
cargo test -p rlab
cargo test -p rlab-tools

# Run with output
cargo test -- --nocapture

# Run benchmarks
cargo bench -p rlab

# Run specific benchmark
cargo bench -p bloom_filter
```

## Performance Guidelines

### Benchmarking

- Use Criterion for statistical benchmarking
- Compare against baseline when optimizing
- Document benchmark results in PR descriptions

```bash
# Run benchmarks
cargo bench -p rlab

# Save baseline
cargo bench -p rlab -- --save-baseline before

# Compare after changes
cargo bench -p rlab -- --baseline before
```

### Optimization Hints

- Mark hot functions with `#[inline]` for small functions
- Use `const fn` for compile-time computation
- Prefer iterators over explicit loops when clearer
- Use `unsafe` only when necessary and document safety invariants

## Unsafe Code Guidelines

1. **Minimize usage**: Prefer safe Rust when possible
2. **Document invariants**: Every `unsafe` block must have safety comments
3. **Encapsulate**: Hide unsafe code behind safe abstractions
4. **Review required**: All unsafe code requires peer review

```rust
/// # Safety
/// Caller must ensure:
/// - ptr is non-null and properly aligned
/// - ptr points to valid memory of type T
pub unsafe fn read_unchecked<T>(ptr: *const T) -> T {
    // SAFETY: Caller guarantees ptr is valid per documented invariants
    unsafe { ptr.read() }
}
```

## Workspace Organization

### Crate Structure

```
rlab/
├── Cargo.toml          # Workspace root
├── lib/
│   └── rlab/           # Core library
├── tools/
│   ├── rlab-tools/     # CLI tools
│   ├── bloom_filter/   # Bloom filter implementations
│   ├── lockfree-queue/ # Lock-free data structures
│   ├── thread-pool/    # Thread pool implementation
│   └── leetcode/       # LeetCode solutions
```

### Crate Responsibilities

- **`lib/rlab`**: Core algorithms and data structures
- **`tools/rlab-tools`**: CLI binary using the library
- **`tools/bloom_filter`**: Standalone bloom filter crate with benchmarks
- **`tools/lockfree-queue`**: Lock-free queue implementations
- **`tools/thread-pool`**: Thread pool implementation
- **`tools/leetcode`**: LeetCode practice problems

### Dependencies

- **Library crates**: Minimize external dependencies
- **Tool crates**: Can use more dependencies (`anyhow`, `clap`, etc.)
- **Dev dependencies**: `criterion` for benchmarks, `tokio` for async tests

## Git Workflow

### Commit Messages

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat(sort): add tim sort implementation
fix(quick_sort): prevent stack overflow on sorted input
docs(bloom_filter): add complexity analysis
perf(radix): optimize counting phase
```

## CI/CD Requirements

### Required Checks

- `cargo fmt --all -- --check` - Formatting
- `cargo clippy --all-targets --all-features -- -D warnings` - Linting
- `cargo test --workspace` - Tests
- `cargo doc --no-deps` - Documentation builds

## Dependencies Policy

### Approved Dependencies

- **Random**: `fastrand` (fast, simple)
- **Error Handling**: `anyhow` (apps), `thiserror` (libraries)
- **Parsing**: `nom`, `regex`
- **Async**: `tokio`
- **CLI**: `clap`
- **Serialization**: `serde`
- **Benchmarking**: `criterion`

### Adding New Dependencies

1. Check if it's already in the workspace
2. Evaluate: maintenance, size, license compatibility
3. Add to workspace `Cargo.toml` if shared
4. Document why it's needed

## Code Review Checklist

- [ ] Code follows naming conventions
- [ ] All public items documented
- [ ] Tests added for new functionality
- [ ] `cargo clippy` passes without warnings
- [ ] `cargo fmt` formatting applied
- [ ] No `unwrap()` or `expect()` in library code
- [ ] Unsafe code has safety documentation
- [ ] Benchmarks added for performance-critical code
- [ ] CHANGELOG.md updated for user-facing changes
