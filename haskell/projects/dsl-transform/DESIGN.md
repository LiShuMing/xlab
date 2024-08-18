You are a programming language theorist and a strict Haskell expert. 
Your task is to build a lightweight Data Processing DSL Interpreter using Haskell.

The user wants to master Monad Transformers (`mtl` library) to understand how Haskell handles computation contexts (State, Environment, Errors) without using C++ style context pointers or global variables.

Please execute the following steps incrementally. STOP and ask for my review after completing each step.

**Step 1: AST and Core Types**

- Initialize a Haskell project.
- Define the AST for a simple Lisp-like or data-centric DSL in `Syntax.hs` (e.g., Let bindings, Variables, Math operations, and a simple Print/Log statement).

**Step 2: The Evaluation Context (Monad Transformer Stack)**

- Create `Eval.hs`.
- Define a custom Monad stack using the `mtl` library. It should combine:
  - `ReaderT` (for read-only environment/variable scopes).
  - `ExceptT` (for runtime error handling like undefined variables).
  - `StateT` (optional, for tracking execution metrics or logs).
- Define the base monad as `Identity` (for pure execution) or `IO` (if side effects are strictly needed for the Print statement).

**Step 3: The Evaluator**

- Implement the `eval :: AST -> EvalMonad Value` function.
- Use deep pattern matching. Demonstrate how `ask`, `local`, `throwError`, and `modify` are used elegantly within `do` notation.

**Engineering Constraints:**

1. Strict separation of syntax (AST) and semantics (Evaluator).
2. The code must clearly showcase how Monad Transformers eliminate boilerplate context-passing.
3. Provide rich English comments explaining the type signatures of the Monad stack.

