# JIT Compilation Pipeline - PoC Specification

## Role & Context

You are a senior database kernel architect and a top-tier Rust compiler expert. We are building a modern, Intermediate Representation (IR) based Just-In-Time (JIT) compilation pipeline for an OLAP database query engine, heavily inspired by the data-centric code generation of systems like Umbra and DuckDB.

## Task

Write a complete, self-contained Rust Proof of Concept (PoC) that compiles a mathematical SQL expression into optimized native machine code at runtime using the `cranelift` and `cranelift-jit` crates.

## Technical Requirements

### Columnar Data

Represent column data as standard Rust `Vec<i64>` arrays.

### AST Definition

Define an idiomatic Rust enum `Expr` to represent an Abstract Syntax Tree. Include operations like `ColumnA`, `ColumnB`, `Add`, and `Mul` so we can test a slightly more complex expression (e.g., `A * B + A`).

### Cranelift JIT Compiler (The Core)

- Create a `JIT` struct managing the `JITBuilder`, `JITModule`, and `Context`.
- Define a function signature that takes two input pointers (`*const i64`), an output pointer (`*mut i64`), and a row count (`usize`). Ensure the ABI matches the target system (System V).
- Implement an AST traversal method that uses `cranelift_frontend::FunctionBuilder` to translate the `Expr` enum into Cranelift IR instructions (e.g., `builder.ins().iadd()`, `imul()`).
- Implement the loop logic within the Cranelift IR to iterate over the row count, load values from memory, compute the result, store it, and advance the pointers.

### Execution

In `main()`, initialize the dummy data, instantiate the JIT compiler, compile the AST into a raw function pointer using Cranelift, transmute it to an `extern "C"` (or `sysv64`) Rust function, execute the batch, and assert the correctness of the results.

## Output Constraints

- Output strictly idiomatic Rust code.
- Provide the exact `Cargo.toml` dependencies block required (e.g., `cranelift`, `cranelift-jit`, `cranelift-module`, `cranelift-frontend`).
- Include highly professional English comments explaining the Cranelift specific mechanics: IR generation, memory flags (`MemFlags`), variable declarations, and block construction (Basic Blocks).
- Ensure the `unsafe` block for executing the JIT code is tightly scoped and explained.
- Keep it to a single `main.rs` file structure for ease of copy-pasting and testing.
