You are a database internal engineer and a strict Haskell expert. 
Your task is to build the core foundation of a SQL Parser and a Rule-Based Optimizer for an OLAP engine using Haskell. 

The user has a deep background in C++ and database kernel development (like StarRocks/ClickHouse) but is transitioning to strictly functional programming. The architectural design must emphasize pure functions, immutability, and Type-Driven Design.

Please execute the following steps incrementally. STOP and ask for my review after completing each step before proceeding.

**Step 1: Project Scaffolding & Core ADTs Definition**
* Initialize a standard Haskell project (using Cabal).
* Define the Algebraic Data Types (ADTs) for the SQL Abstract Syntax Tree (AST) in `AST.hs`. 
* Support basic `SELECT`, `FROM`, `WHERE` clauses, binary expressions (`=`, `>`, `AND`), and column references. Make impossible states unrepresentable.

**Step 2: Megaparsec SQL Parser**
* Create `Parser.hs` using the `megaparsec` library.
* Implement parser combinators to parse a raw SQL string into the AST. Focus on pure composability and clear error messages.

**Step 3: Rule-Based Optimizer**
* Create `Optimizer.hs`.
* Implement a pure function: `optimize :: AST -> AST`.
* Use deep pattern matching to implement two logical optimization rules: 
  1. Constant Folding (e.g., `1 + 2` -> `3`).
  2. Predicate Pushdown or simplification (e.g., `AND` with `TRUE`).

**Engineering Constraints:**
1. NO partial functions (e.g., do not use standard `head`).
2. Isolate all side effects. The parser and optimizer MUST be mathematically pure.
3. Write clean, professional English comments explaining the *why* behind functional design choices.
4. Adhere to idiomatic Haskell styling.
