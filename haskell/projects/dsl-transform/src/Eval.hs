{-|
Module      : Eval
Description : Monad Transformer-based Evaluator for the DSL

This module implements the semantics (evaluation logic) for our DSL using
a stack of Monad Transformers from the `mtl` library. This demonstrates how
Haskell elegantly handles computation contexts without explicit context passing
or global variables.

== The Monad Transformer Stack

The evaluation context is constructed as a stack of transformers:

@
EvalMonad a = ReaderT Env (ExceptT EvalError (StateT EvalState Identity)) a
@

Reading from inside-out (Identity -> StateT -> ExceptT -> ReaderT):

1. 'Identity': The base monad (pure computation, no actual side effects)
2. 'StateT EvalState': Threading mutable state through the computation
3. 'ExceptT EvalError': Short-circuiting error handling
4. 'ReaderT Env': Read-only access to the environment/variable bindings

== Why Monad Transformers?

In imperative languages, we'd pass context pointers explicitly:

> Value eval(AST* ast, Env* env, State* state, Error** error) {
>     // manually check and propagate errors
>     // manually thread state through
> }

In Haskell with Monad Transformers, the compiler handles all the plumbing:

> eval :: AST -> EvalMonad Value
> eval ast = do
>     env <- ask        -- get environment (Reader)
>     modify (...)      -- update state (State)
>     throwError (...)  -- abort with error (Except)

This eliminates boilerplate and lets us focus on the evaluation logic.
-}
module Eval (
    -- * Evaluation Monad
    EvalMonad,
    runEval,
    
    -- * Environment and State
    Env,
    emptyEnv,
    EvalState(..),
    initialState,
    EvalError(..),
    
    -- * Values
    Value(..),
    showValue,
    
    -- * Evaluation Function
    eval,
    
    -- * Utility
    evalProgram
) where

import Control.Monad.Identity
import Control.Monad.Reader
import Control.Monad.Except
import Control.Monad.State
import qualified Data.Map as Map
import Data.Map (Map)

import Syntax

-- ---------------------------------------------------------------------------
-- Values
-- ---------------------------------------------------------------------------

{-| The result of evaluating an expression.

Our DSL is dynamically typed, so 'Value' is a sum type that can represent:
- Integers
- Booleans
- Lists (linked list of Values)
- Closures (functions with captured environment)
- Unit (for expressions that don't return meaningful values)
-}
data Value
    = VInt Integer                    -- ^ Integer value
    | VBool Bool                      -- ^ Boolean value
    | VNil                            -- ^ Empty list
    | VCons Value Value               -- ^ Non-empty list (head, tail)
    | VClosure Name AST Env           -- ^ Closure: parameter, body, captured env
    | VUnit                           -- ^ Unit value (for side effects)
    deriving (Eq, Show)

-- ---------------------------------------------------------------------------
-- Evaluation Context: The Monad Transformer Stack
-- ---------------------------------------------------------------------------

{-| The Environment maps variable names to their bound values.

We use Map for O(log n) lookup. The environment is immutable (functional),
meaning each variable binding creates a new Map rather than modifying in place.
This is handled efficiently by Map's persistent data structure.
-}
type Env = Map Name Value

-- | An empty environment with no bindings
emptyEnv :: Env
emptyEnv = Map.empty

{-| The evaluation state tracks mutable information during execution.

Unlike the Environment (which is read-only and lexically scoped), State
can be modified during evaluation. We use it for:
- Execution metrics (instruction count)
- Execution log (print statements)
-}
data EvalState = EvalState
    { evalSteps    :: Int      -- ^ Number of evaluation steps performed
    , evalLog      :: [String] -- ^ Accumulated output from Print statements
    } deriving (Eq, Show)

-- | Initial evaluation state
initialState :: EvalState
initialState = EvalState { evalSteps = 0, evalLog = [] }

{-| Evaluation errors that can occur during execution.

Using a custom error type (rather than String) makes error handling
type-safe and allows programmatic inspection of error conditions.
-}
data EvalError
    = UndefinedVariable Name         -- ^ Reference to undefined variable
    | TypeMismatch String Value      -- ^ Expected type X, got value Y
    | DivisionByZero                 -- ^ Division by zero
    | ArityMismatch                  -- ^ Wrong number of arguments
    | NotAFunction Value             -- ^ Attempt to call non-function
    deriving (Eq, Show)

{-| The Monad Transformer Stack.

This is the heart of our evaluator. By composing transformers, we get
all the capabilities we need without any boilerplate:

* 'ReaderT Env': Gives us 'ask' and 'local' for accessing and extending
  the variable environment. The environment is read-only - we can only
  extend it locally, not modify it globally.

* 'ExceptT EvalError': Gives us 'throwError' and 'catchError' for error
  handling. Errors short-circuit the computation immediately.

* 'StateT EvalState': Gives us 'get', 'put', 'modify' for mutable state.
  Unlike Reader, State IS mutable and persists across the computation.

* 'Identity': The base monad. Using Identity makes our evaluation pure,
  meaning we can run it without any IO. We could replace this with 'IO'
  if we wanted actual side effects.

type EvalMonad a = ReaderT Env (ExceptT EvalError (StateT EvalState Identity)) a
-}
type EvalMonad = ReaderT Env (ExceptT EvalError (StateT EvalState Identity))

{-| Run the evaluation monad with given initial environment and state.

This function peels off the transformer layers one by one:

1. 'runReaderT': Provides the environment
2. 'runExceptT': Handles potential errors
3. 'runStateT': Threads the state through
4. 'runIdentity': Executes the pure computation

The result is @Either EvalError (a, EvalState)@:
- 'Left error': Evaluation failed with an error
- 'Right (value, finalState)': Success, with final value and state
-}
{-| Run the evaluation monad with given initial environment and state.

This function peels off the transformer layers one by one:

1. 'runReaderT': Provides the environment, gives: ExceptT EvalError (StateT EvalState Identity) a
2. 'runExceptT': Handles potential errors, gives: StateT EvalState Identity (Either EvalError a)
3. 'runStateT': Threads the state through, gives: Identity (Either EvalError a, EvalState)
4. 'runIdentity': Executes the pure computation

The result is @(Either EvalError a, EvalState)@:
- The first component is Left error or Right value
- The second component is the final state (always available, even on error)

This ordering means we can inspect the state (e.g., step count, log) even
if evaluation failed - useful for debugging!
-}
runEval :: EvalMonad a -> Env -> EvalState -> (Either EvalError a, EvalState)
runEval m env initState = runIdentity (runStateT (runExceptT (runReaderT m env)) initState)

-- ---------------------------------------------------------------------------
-- Evaluation Function
-- ---------------------------------------------------------------------------

{-| Evaluate an AST to produce a Value.

This is the core of our interpreter. Notice how the type signature
@AST -> EvalMonad Value@ says exactly what we need: given an AST,
produce a Value in the evaluation context. The monad stack handles
all the context threading automatically.

The implementation uses deep pattern matching and do-notation, with
monadic operations that demonstrate each transformer:
- 'ask': Read the environment (ReaderT)
- 'local': Temporarily extend the environment (ReaderT)
- 'throwError': Abort with an error (ExceptT)
- 'modify': Update the state (StateT)
- 'gets': Read from state (StateT)
-}
eval :: AST -> EvalMonad Value
eval ast = do
    -- Increment step counter to demonstrate StateT
    modify $ \s -> s { evalSteps = evalSteps s + 1 }
    
    case ast of
        -- Integer literals evaluate to themselves
        IntLit n -> return $ VInt n
        
        -- Boolean literals evaluate to themselves
        BoolLit b -> return $ VBool b
        
        -- Variable lookup: ask for the environment, then look up the name
        Var name -> do
            env <- ask  -- ask :: ReaderT Env m Env
            case Map.lookup name env of
                Just val -> return val
                Nothing  -> throwError $ UndefinedVariable name
                            -- throwError :: EvalError -> ExceptT EvalError m a
        
        -- Let binding: evaluate the expression, then bind in extended environment
        Let name expr body -> do
            val <- eval expr
            -- local :: (Env -> Env) -> EvalMonad a -> EvalMonad a
            -- local temporarily extends the environment for the computation
            local (Map.insert name val) (eval body)
        
        -- Binary operations: evaluate both operands, then apply
        BinOp op left right -> do
            lval <- eval left
            rval <- eval right
            evalBinOp op lval rval
        
        -- Conditional: evaluate condition, then choose branch
        If cond trueBranch falseBranch -> do
            cval <- eval cond
            case cval of
                VBool True  -> eval trueBranch
                VBool False -> eval falseBranch
                other       -> throwError $ TypeMismatch "Bool" other
        
        -- Print statement: evaluate expression, add to log
        Print expr -> do
            val <- eval expr
            -- modify :: (EvalState -> EvalState) -> EvalMonad ()
            -- Here we append the string representation to the log
            modify $ \s -> s { evalLog = evalLog s ++ [showValue val] }
            return VUnit
        
        -- Sequence: evaluate first for side effects, return second
        Seq expr1 expr2 -> do
            _ <- eval expr1  -- Ignore result, keep side effects
            eval expr2
        
        -- Empty list
        Nil -> return VNil
        
        -- Cons: evaluate head and tail, construct list value
        Cons headExpr tailExpr -> do
            hval <- eval headExpr
            tval <- eval tailExpr
            return $ VCons hval tval
        
        -- Lambda: capture current environment in a closure
        Lambda param body -> do
            env <- ask
            -- The closure captures the current environment
            return $ VClosure param body env
        
        -- Function application: evaluate function and argument, then apply
        App funcExpr argExpr -> do
            funcVal <- eval funcExpr
            argVal <- eval argExpr
            case funcVal of
                VClosure param body closureEnv ->
                    -- Apply: extend closure's captured environment with the argument
                    -- and evaluate the body
                    local (const $ Map.insert param argVal closureEnv) (eval body)
                other -> throwError $ NotAFunction other

-- | Evaluate a binary operation on two values
evalBinOp :: BinOp -> Value -> Value -> EvalMonad Value
evalBinOp Add (VInt l) (VInt r) = return $ VInt (l + r)
evalBinOp Sub (VInt l) (VInt r) = return $ VInt (l - r)
evalBinOp Mul (VInt l) (VInt r) = return $ VInt (l * r)
evalBinOp Div (VInt l) (VInt r)
    | r == 0    = throwError DivisionByZero
    | otherwise = return $ VInt (l `div` r)
evalBinOp Eq  l        r        = return $ VBool (l == r)
evalBinOp Lt  (VInt l) (VInt r) = return $ VBool (l < r)
evalBinOp Gt  (VInt l) (VInt r) = return $ VBool (l > r)
evalBinOp And (VBool l) (VBool r) = return $ VBool (l && r)
evalBinOp Or  (VBool l) (VBool r) = return $ VBool (l || r)
-- Type mismatch cases
evalBinOp op l _ = throwError $ TypeMismatch (showOpExpected op) l
  where
    showOpExpected Add = "Int -> Int -> Int"
    showOpExpected Sub = "Int -> Int -> Int"
    showOpExpected Mul = "Int -> Int -> Int"
    showOpExpected Div = "Int -> Int -> Int"
    showOpExpected Eq  = "a -> a -> Bool"
    showOpExpected Lt  = "Int -> Int -> Bool"
    showOpExpected Gt  = "Int -> Int -> Bool"
    showOpExpected And = "Bool -> Bool -> Bool"
    showOpExpected Or  = "Bool -> Bool -> Bool"

-- | Convert a Value to a string (for printing)
showValue :: Value -> String
showValue (VInt n)     = show n
showValue (VBool b)    = show b
showValue VNil         = "[]"
showValue (VCons h t)  = showCons h t
showValue (VClosure{}) = "<function>"
showValue VUnit        = "()"

-- Helper to show lists nicely
showCons :: Value -> Value -> String
showCons h t = "[" ++ showValue h ++ showTail t ++ "]"
  where
    showTail VNil = ""
    showTail (VCons h' t') = ", " ++ showValue h' ++ showTail t'
    showTail other = " | " ++ showValue other

-- ---------------------------------------------------------------------------
-- Convenience Functions
-- ---------------------------------------------------------------------------

{-| Evaluate a program (AST) with empty environment and initial state.

Returns either an error message, or a tuple of (result, log, steps).
This is the high-level entry point for running programs.

Note: Even when an error occurs, we still get the final state, which
includes the step count and any log output generated before the error.
This demonstrates the power of the StateT-over-ExceptT ordering.
-}
evalProgram :: AST -> Either String (Value, [String], Int)
evalProgram ast = 
    let (result, finalState) = runEval (eval ast) emptyEnv initialState
    in case result of
        Left err -> Left $ showError err
        Right val -> Right (val, evalLog finalState, evalSteps finalState)
  where
    showError (UndefinedVariable name) = "Undefined variable: " ++ name
    showError (TypeMismatch expected got) = 
        "Type mismatch: expected " ++ expected ++ ", got " ++ showValue got
    showError DivisionByZero = "Division by zero"
    showError ArityMismatch = "Arity mismatch in function application"
    showError (NotAFunction val) = "Not a function: " ++ showValue val
