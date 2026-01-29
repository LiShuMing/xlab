# Haskell Lab (haskell/hslab)

## Overview
Haskell laboratory for functional programming exploration, category theory concepts, and lazy evaluation patterns.

## Build System
- **Build Tool**: `cabal` or `stack`
- ** GHC**: Glasgow Haskell Compiler
- **Test Tool**: `cabal test` or `stack test`
- **REPL**: `ghci` for interactive development

## Project Structure
```
haskell/
└── hslab/           # Main Haskell lab
```

## Key Concepts
- **Lazy Evaluation**: Expressions evaluated on demand
- **Pure Functions**: No side effects, referential transparency
- **Type Inference**: Compiler deduces types automatically
- **Pattern Matching**: Exhaustiveness checking
- **Higher-Order Functions**: `map`, `filter`, `fold`
- **Monads**: `Maybe`, `Either`, `IO`, `State`

## Coding Conventions
- Use `haskell-language-server` for IDE support
- Explicit type signatures for top-level functions
- Point-free style when it improves readability
- List comprehensions for simple transformations
- `<$>` and `<*>` for functor/applicative operations
- `do` notation for monadic chains

## AI Vibe Coding Tips
- Start with type signatures, then implement
- Use `foldr`/`foldl` for list reductions
- Pattern match on constructors exhaustively
- Use `where` clauses for local definitions
- Beware of space leaks with lazy evaluation
- Use `seq` or `!` strictness annotations when needed
- Consider `Data.Sequence` for efficient concatenation
- Partial functions (`head`, `!!`): handle edge cases
- Learn common typeclasses: `Functor`, `Applicative`, `Monad`, `Monoid`
