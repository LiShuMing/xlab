# Interpreter

A custom interpreter implementation with lexer, parser, and AST generation.

## Overview

This project implements an interpreter with:
- Lexical analysis (lexer) using Flex
- Syntax analysis (parser) using Yacc/Bison
- Abstract Syntax Tree (AST) generation
- Expression evaluation

## Structure

- `gen/` - Generated lexer and parser code
  - `ms_lex.l` - Lexer specification (Flex)
  - `ms_yacc.y` - Parser specification (Yacc/Bison)
- `ast/` - AST implementation
  - `parser.h/cpp` - Parser interface
  - `creator.h/cpp` - AST node creation
  - `exprs.h` - Expression definitions
- `common/` - Common utilities
  - `dummy_lock.hpp` - Lock utilities
  - `free_list.hpp` - Memory management
- `logging/` - Logging utilities
  - `interpreter_logger.hpp`
- `main.cpp` - Main entry point
- `interpreter.h` - Interpreter interface

## Building

The project uses CMake and requires Flex and Bison:

```bash
./build.sh
```

Or manually:

```bash
mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
```

### Prerequisites

- Flex (lexer generator)
- Bison or Yacc (parser generator)
- CMake 3.12+
- C++17 compiler

### Installing Prerequisites

On Ubuntu/Debian:
```bash
sudo apt-get install flex bison
```

On macOS:
```bash
brew install flex bison
```

## Build Types

- `DEBUG`: Debug build with symbols
- `RELEASE`: Optimized release build
- `ASAN`: Address sanitizer build
- `LSAN`: Leak sanitizer build

## Running

After building:

```bash
./build/interpreter
```

## How It Works

1. **Lexical Analysis**: The lexer (`ms_lex.l`) tokenizes input source code
2. **Syntax Analysis**: The parser (`ms_yacc.y`) parses tokens according to grammar rules
3. **AST Generation**: The parser creates an Abstract Syntax Tree using AST creators
4. **Evaluation**: The interpreter evaluates the AST to execute the program

## Project Components

### Lexer (`gen/ms_lex.l`)
- Defines token patterns
- Handles whitespace and comments
- Generates token stream for parser

### Parser (`gen/ms_yacc.y`)
- Defines grammar rules
- Builds AST during parsing
- Handles syntax errors

### AST (`ast/`)
- Expression nodes for different types
- Tree structure for program representation
- Node creation and manipulation

## Development

To modify the language:
1. Update `gen/ms_lex.l` for new tokens
2. Update `gen/ms_yacc.y` for new grammar rules
3. Update `ast/exprs.h` for new AST node types
4. Rebuild the project

## Notes

- The generated lexer and parser files are created in the build directory
- The project uses C++17 features
- Memory management uses custom free lists for efficiency

