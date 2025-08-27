# RDB - A Rust Database Implementation

This is a minimal database implementation in Rust, demonstrating the core components of a relational database management system.

## Components

1. **Parser** - Parses SQL queries into an Abstract Syntax Tree (AST)
2. **Analyzer** - Performs semantic analysis on the AST
3. **Planner** - Creates a logical query plan
4. **Executor** - Executes the query plan and returns results
5. **Storage** - Handles data storage (placeholder implementation)

## Current Features

- Simple SELECT query parsing (`SELECT * FROM table WHERE condition`)
- Basic query execution with mock data

## Example

The project currently demonstrates a simple query execution flow:

```sql
SELECT * FROM users WHERE id = 1
```

## Project Structure

```
src/
├── main.rs          # Entry point
├── parser/          # SQL parser
│   ├── mod.rs       # Parser implementation
│   └── ast.rs       # Abstract Syntax Tree definitions
├── analyzer/        # Semantic analyzer
├── planner/         # Query planner
├── executor/        # Query executor
└── storage/         # Storage engine (placeholder)
```

## Building and Running

```bash
cargo build
cargo run
```

## Future Improvements

1. Implement a proper SQL parser using a parsing library like `nom` or `lalrpop`
2. Add support for more SQL statements (INSERT, UPDATE, DELETE, CREATE TABLE, etc.)
3. Implement a proper storage engine with file-based persistence
4. Add indexing support
5. Implement transactions and concurrency control
6. Add support for more data types
7. Implement proper error handling and reporting

## License

This project is open-source and available under the MIT License.