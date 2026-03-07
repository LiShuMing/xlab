# DSL Interpreter: Design, Build, Test & Documentation

A comprehensive guide to the Data Processing DSL Interpreter built with Haskell Monad Transformers.

---

## 1. DESIGN

### 1.1 Overview

This project implements a **Data Processing DSL Interpreter** using Haskell's `mtl` (Monad Transformer Library). The goal is to demonstrate how Monad Transformers elegantly handle computation contexts (State, Environment, Errors) without the boilerplate of explicit context passing found in imperative languages.

### 1.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DSL Interpreter                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │   Syntax.hs  │   │    Eval.hs   │   │   Main.hs    │    │
│  │              │   │              │   │              │    │
│  │  • AST       │──▶│  • Monad     │──▶│  • Examples  │    │
│  │  • BinOp     │   │    Stack     │   │  • Demo      │    │
│  │  • showAST   │   │  • eval      │   │  • I/O       │    │
│  └──────────────┘   └──────────────┘   └──────────────┘    │
│                            │                                │
│                            ▼                                │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Monad Transformer Stack                   │ │
│  │  ReaderT Env (ExceptT EvalError (StateT EvalState Identity)) │ │
│  │                                                       │ │
│  │  • ReaderT: Variable environment (ask, local)         │ │
│  │  • ExceptT: Error handling (throwError)               │ │
│  │  • StateT:  Execution metrics (modify, gets)          │ │
│  │  • Identity: Pure computation base                    │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Key Design Decisions

#### 1.3.1 Strict Separation of Concerns
- **Syntax.hs**: Defines the Abstract Syntax Tree (AST) with no evaluation logic
- **Eval.hs**: Implements semantics using pure functions in a monadic context
- **Main.hs**: Provides examples and I/O interface

#### 1.3.2 The Monad Transformer Stack

```haskell
type EvalMonad = ReaderT Env (ExceptT EvalError (StateT EvalState Identity))
```

| Transformer | Purpose | Key Operations |
|-------------|---------|----------------|
| `ReaderT Env` | Immutable variable bindings | `ask`, `local` |
| `ExceptT EvalError` | Error propagation | `throwError`, `catchError` |
| `StateT EvalState` | Mutable execution state | `modify`, `get`, `put` |
| `Identity` | Pure computation base | N/A |

**Why this order?** StateT is outermost over ExceptT, meaning we can inspect state (logs, step count) even when evaluation fails—useful for debugging.

#### 1.3.3 Value Representation

```haskell
data Value
    = VInt Integer
    | VBool Bool
    | VNil
    | VCons Value Value
    | VClosure Name AST Env  -- Captures environment!
    | VUnit
```

Closures capture their defining environment, enabling lexical scoping.

### 1.4 Language Features

| Feature | Syntax | Example |
|---------|--------|---------|
| Literals | `42`, `True` | `IntLit 42` |
| Variables | `x` | `Var "x"` |
| Let Binding | `let x = e1 in e2` | `Let "x" e1 e2` |
| Arithmetic | `+`, `-`, `*`, `/` | `BinOp Add e1 e2` |
| Comparison | `<`, `>`, `==` | `BinOp Lt e1 e2` |
| Boolean | `&&`, `\|\|` | `BinOp And e1 e2` |
| Conditional | `if c then t else f` | `If c t f` |
| Lambda | `\x -> e` | `Lambda "x" e` |
| Application | `f arg` | `App f arg` |
| Lists | `[]`, `:` | `Nil`, `Cons h t` |
| Print | `print e` | `Print e` |
| Sequence | `e1; e2` | `Seq e1 e2` |

### 1.5 Comparison: Haskell vs C++ Style Context Passing

**C++ Style (Explicit Context):**
```cpp
Value eval(AST* ast, Env* env, State* state, Error** error) {
    if (*error) return nullptr;  // Check and propagate
    
    Env* newEnv = extendEnv(env, name, value);
    Value result = eval(body, newEnv, state, error);
    freeEnv(newEnv);  // Manual cleanup
    
    if (*error) return nullptr;
    return result;
}
```

**Haskell Style (Monadic):**
```haskell
eval :: AST -> EvalMonad Value
eval (Let name expr body) = do
    val <- eval expr
    local (Map.insert name val) (eval body)  -- Automatic cleanup!
```

**Benefits:**
- No manual error checking at every step
- No explicit environment threading
- Automatic resource management (GC)
- Composable and testable

---

## 2. BUILD

### 2.1 Prerequisites

- **GHC**: 9.6.7 or later
- **Cabal**: 3.0 or later
- **Dependencies**:
  - `base >= 4.14`
  - `mtl >= 2.2` (Monad Transformer Library)
  - `containers >= 0.6` (for Data.Map)
  - `HUnit >= 1.6` (for testing)
  - `QuickCheck >= 2.14` (for property testing)

### 2.2 Project Structure

```
dsl-transform/
├── dsl-transform.cabal      # Package configuration
├── DESIGN.md                # Original design requirements
├── DESIGN_BUILD_TEST_DOC.md # This document
├── src/
│   ├── Syntax.hs            # AST definitions
│   ├── Eval.hs              # Monad stack & evaluator
│   └── Main.hs              # Example programs
└── test/
    └── Spec.hs              # Unit & property tests
```

### 2.3 Build Commands

```bash
# Clone/navigate to project
cd dsl-transform

# Build the project
cabal build

# Build and run the executable
cabal run

# Run tests
cabal test

# Run tests with detailed output
cabal test --test-show-details=direct

# Build in release mode
cabal build -O2

# Clean build artifacts
cabal clean
```

### 2.4 Cabal Configuration

```cabal
executable dsl-transform
  main-is:             Main.hs
  other-modules:       Syntax, Eval
  build-depends:       base >= 4.14 && < 5.0,
                       mtl >= 2.2,
                       containers >= 0.6
  hs-source-dirs:      src
  ghc-options:         -Wall -Wextra

test-suite dsl-transform-test
  type:                exitcode-stdio-1.0
  main-is:             Spec.hs
  other-modules:       Syntax, Eval
  build-depends:       base >= 4.14 && < 5.0,
                       mtl >= 2.2,
                       containers >= 0.6,
                       HUnit >= 1.6,
                       QuickCheck >= 2.14
  hs-source-dirs:      src, test
  ghc-options:         -Wall -Wextra -threaded -rtsopts
```

### 2.5 Expected Output (Executable)

```
============================================
DSL Interpreter using Monad Transformers
============================================

This interpreter demonstrates the use of mtl
(Monad Transformer Library) to compose:
  - ReaderT: Environment (variable bindings)
  - ExceptT: Error handling
  - StateT:  Execution state (steps, logs)

============================================================
Example: Simple Arithmetic
------------------------------------------------------------
AST:
let x = (10 + 5) in
(x * 2)
----------------------------------------
Result:
Value:   30
Steps:   7
...
```

---

## 3. TEST

### 3.1 Test Suite Overview

The test suite includes:
- **40 Unit Tests** (HUnit): Specific evaluation cases
- **8 Property Tests** (QuickCheck): Algebraic laws

### 3.2 Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| Basic Literals | 3 | Int, Bool, Nil |
| Arithmetic | 5 | +, -, *, /, div-by-zero |
| Comparison | 4 | <, >, == |
| Boolean | 4 | &&, \\\| |
| Let Bindings | 4 | Simple, nested, shadowing |
| Conditionals | 3 | If-then-else |
| Lists | 4 | Nil, Cons, equality |
| Lambda/Closures | 5 | Functions, HOF, capture |
| Side Effects | 3 | Print, Seq |
| Error Handling | 3 | Undefined, type mismatch |
| Monad Stack | 2 | State counting |

### 3.3 Running Tests

```bash
# Run all tests
cabal test

# Sample output:
# Cases: 40  Tried: 40  Errors: 0  Failures: 0
# 
# Property: Addition is commutative
# +++ OK, passed 100 tests.
# 
# Property: Multiplication is commutative
# +++ OK, passed 100 tests.
# ...
# All tests passed!
```

### 3.4 Property Tests (QuickCheck)

```haskell
-- Addition is commutative
x + y = y + x

-- Multiplication is commutative
x * y = y * x

-- Subtraction of self
x - x = 0

-- Multiplication by zero
x * 0 = 0

-- Addition identity
x + 0 = x

-- Equality reflexive
x == x = True

-- Let substitution
let x = v in x = v

-- Identity function
(λx. x) v = v
```

Each property is tested with 100 random inputs.

### 3.5 Example Unit Test

```haskell
testClosureCapture :: Test
testClosureCapture = TestCase $ do
    -- let x = 10 in 
    -- let f = \y -> x + y in 
    -- let x = 20 in f 5 
    -- Result: 15 (not 25!)
    let ast = Let "x" (IntLit 10)
            (Let "f" (Lambda "y" (BinOp Add (Var "x") (Var "y")))
              (Let "x" (IntLit 20)
                (App (Var "f") (IntLit 5))))
    case evalProgram ast of
        Right (VInt 15, [], 12) -> return ()
        other -> assertFailure $ "Expected 15, got: " ++ show other
```

### 3.6 Test Results Summary

```
===============================================
  DSL Interpreter Test Suite
===============================================

Unit Tests:     40 passed, 0 failed
Property Tests: 8 passed (800 total assertions)
Coverage:       All language features tested
```

---

## 4. DOCUMENTATION

### 4.1 API Documentation

#### Syntax.hs

| Export | Type | Description |
|--------|------|-------------|
| `Name` | `type Name = String` | Variable identifiers |
| `BinOp` | `data BinOp` | Binary operators |
| `AST` | `data AST` | Abstract syntax tree |
| `showAST` | `AST -> String` | Pretty-print AST |

#### Eval.hs

| Export | Type | Description |
|--------|------|-------------|
| `EvalMonad` | `* -> *` | Evaluation monad transformer stack |
| `runEval` | `EvalMonad a -> Env -> EvalState -> (Either EvalError a, EvalState)` | Execute computation |
| `Env` | `Map Name Value` | Variable environment |
| `emptyEnv` | `Env` | Empty environment |
| `EvalState` | `data` | Execution state (steps, log) |
| `initialState` | `EvalState` | Initial state |
| `EvalError` | `data` | Error types |
| `Value` | `data` | Runtime values |
| `eval` | `AST -> EvalMonad Value` | Core evaluation function |
| `evalProgram` | `AST -> Either String (Value, [String], Int)` | High-level evaluator |
| `showValue` | `Value -> String` | Pretty-print value |

### 4.2 Monad Operations Reference

```haskell
-- ReaderT operations
ask      :: EvalMonad Env              -- Get environment
local    :: (Env -> Env) -> EvalMonad a -> EvalMonad a  -- Extend scope

-- ExceptT operations
throwError :: EvalError -> EvalMonad a  -- Abort with error

-- StateT operations
modify   :: (EvalState -> EvalState) -> EvalMonad ()  -- Update state
gets     :: (EvalState -> a) -> EvalMonad a           -- Query state
```

### 4.3 Error Types

```haskell
data EvalError
    = UndefinedVariable Name
    | TypeMismatch String Value
    | DivisionByZero
    | ArityMismatch
    | NotAFunction Value
```

### 4.4 Usage Examples

#### Example 1: Simple Expression
```haskell
import Syntax
import Eval

-- Evaluate: 1 + 2 * 3
program :: AST
program = BinOp Add (IntLit 1) (BinOp Mul (IntLit 2) (IntLit 3))

main :: IO ()
main = do
    case evalProgram program of
        Left err -> putStrLn $ "Error: " ++ err
        Right (val, log, steps) -> do
            putStrLn $ "Result: " ++ showValue val
            putStrLn $ "Steps:  " ++ show steps
```

#### Example 2: With Variables
```haskell
-- let x = 10 in x + 5
program :: AST
program = Let "x" (IntLit 10) (BinOp Add (Var "x") (IntLit 5))
-- Result: 15
```

#### Example 3: Lambda Function
```haskell
-- (\x -> x + 1) 41
program :: AST
program = App (Lambda "x" (BinOp Add (Var "x") (IntLit 1))) (IntLit 41)
-- Result: 42
```

#### Example 4: Error Handling
```haskell
-- undefined + 1
program :: AST
program = BinOp Add (Var "undefined") (IntLit 1)
-- Result: Left "Undefined variable: undefined"
```

### 4.5 Learning Path

1. **Understand the Problem**: Read `DESIGN.md`
2. **Study the AST**: Review `src/Syntax.hs`
3. **Learn the Monad Stack**: Study `src/Eval.hs` comments
4. **Run Examples**: Execute `cabal run`
5. **Explore Tests**: Read `test/Spec.hs`
6. **Modify & Experiment**: Change examples, add features

### 4.6 Further Reading

- [MTL Documentation](https://hackage.haskell.org/package/mtl)
- [Monad Transformers Step by Step](http://page.mi.fu-berlin.de/scravy/realworldhaskell/materialien/monad-transformers-step-by-step.pdf)
- [ReaderT Design Pattern](https://www.fpcomplete.com/blog/2017/06/readert-design-pattern/)
- [Haskell in Depth - Chapter on Monad Transformers](https://www.manning.com/books/haskell-in-depth)

---

## 5. QUICK REFERENCE

### Build & Run
```bash
cabal build          # Build
cabal run            # Run examples
cabal test           # Run tests
cabal repl           # Interactive REPL
```

### AST Construction
```haskell
IntLit 42                    -- 42
BoolLit True                 -- True
Var "x"                      -- x
Let "x" e1 e2                -- let x = e1 in e2
BinOp Add e1 e2              -- e1 + e2
If c t f                     -- if c then t else f
Lambda "x" e                 -- \x -> e
App f arg                    -- f arg
Nil                          -- []
Cons h t                     -- h : t
Print e                      -- print(e)
Seq e1 e2                    -- e1; e2
```

### Key Insights

1. **Monad transformers compose contexts** without boilerplate
2. **ReaderT provides lexical scoping** through environment extension
3. **ExceptT enables error handling** without explicit checks
4. **StateT tracks mutable state** while remaining pure
5. **Closures capture environment** enabling first-class functions

---

## Appendix: Complete Feature Matrix

| Feature | Status | Test Coverage |
|---------|--------|---------------|
| Integer literals | ✅ | ✅ |
| Boolean literals | ✅ | ✅ |
| Variables | ✅ | ✅ |
| Let bindings | ✅ | ✅ |
| Shadowing | ✅ | ✅ |
| Arithmetic (+,-,*,/) | ✅ | ✅ |
| Division by zero | ✅ | ✅ |
| Comparison (<,>,==) | ✅ | ✅ |
| Boolean (&&,\\|) | ✅ | ✅ |
| Conditionals | ✅ | ✅ |
| Lambda | ✅ | ✅ |
| Application | ✅ | ✅ |
| Currying | ✅ | ✅ |
| Closures | ✅ | ✅ |
| Higher-order functions | ✅ | ✅ |
| Lists | ✅ | ✅ |
| Print | ✅ | ✅ |
| Sequencing | ✅ | ✅ |
| Error handling | ✅ | ✅ |
| Step counting | ✅ | ✅ |

**Total**: 20/20 features implemented and tested.
