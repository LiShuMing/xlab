# Rust Lab (rust)

## Overview
Rust laboratory focusing on systems programming with memory safety, zero-cost abstractions, and fearless concurrency.

## Build System
- **Build Tool**: Cargo
- **Test Tool**: `cargo test`
- **Benchmark Tool**: `cargo bench`
- **Linter**: `cargo clippy`
- **Formatter**: `cargo fmt`
- **Dependency**: `cargo add` or edit `Cargo.toml`

## Project Structure
```
rust/
├── rlab/            # Main Rust lab
├── rdb/             # Database implementation
├── thirdparty/      # External crates
└── Cargo.toml       # Workspace config
```

## Key Concepts
- **Ownership**: Memory safety without GC
- **Borrowing**: References with lifetime rules
- **Lifetime**: Compile-time memory management
- **Traits**: Interfaces and polymorphism
- **Error Handling**: `Result<T, E>` and `?` operator
- **Concurrency**: Fearless parallelism (Send, Sync)

## Coding Conventions
- `snake_case` for functions and variables
- `PascalCase` for types and traits
- `SCREAMING_SNAKE_CASE` for constants
- Return types: `Result` for fallible functions
- Use `?` for error propagation
- Derive traits: `Clone`, `Debug`, `PartialEq`
- Pattern matching with `match` and `let...else`
- Iterators over index-based loops

## AI Vibe Coding Tips
- Start with the type signature, implement outwards
- Use `cargo check` frequently for compile errors
- `clippy` provides linting and suggestions
- Borrow checker rules:
  - Multiple immutable refs OR one mutable ref
  - References cannot outlive their owner
- Use `Box<T>` for heap allocation
- Use `Arc<T>` for shared ownership
- `Rc<T>` for single-threaded reference counting
- Error handling: custom types via `thiserror`, messages via `anyhow`
- Learn common traits: `Clone`, `Copy`, `Default`, `Display`
