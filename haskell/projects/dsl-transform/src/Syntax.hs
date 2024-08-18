{-|
Module      : Syntax
Description : Abstract Syntax Tree (AST) for a Data Processing DSL

This module defines the core data types for a Lisp-like, data-centric DSL.
It demonstrates strict separation of syntax from semantics - a hallmark of
functional language design.

The DSL supports:
- Let bindings for variable declarations
- Variable references
- Arithmetic operations
- Comparison operations
- Conditional expressions (if-then-else)
- Print/Log statements for side effects
- Lists for data processing
- Lambda expressions and function application
-}
module Syntax (
    -- * AST Types
    AST(..),
    BinOp(..),
    Name,
    
    -- * Utility Functions
    showAST
) where

-- | A Name is simply a String representing an identifier
-- We use a type alias to make type signatures more semantic and allow
-- easy refactoring in the future.
type Name = String

-- | Binary operations supported by our DSL
-- We separate these from the AST type to keep pattern matching clean
-- and to allow easy extension of operators without modifying the core AST.
data BinOp
    = Add       -- ^ Addition (+)
    | Sub       -- ^ Subtraction (-)
    | Mul       -- ^ Multiplication (*)
    | Div       -- ^ Division (/)
    | Eq        -- ^ Equality (==)
    | Lt        -- ^ Less than (<)
    | Gt        -- ^ Greater than (>)
    | And       -- ^ Logical AND
    | Or        -- ^ Logical OR
    deriving (Eq, Show)

-- | The Abstract Syntax Tree (AST) for our DSL
-- This is a recursive data structure that represents all possible
-- expressions in our language. Each constructor represents a different
-- syntactic construct.
data AST
    = -- | Integer literal
      -- Example: @42@
      IntLit Integer
      
    | -- | Boolean literal
      -- Example: @True@
      BoolLit Bool
      
    | -- | Variable reference by name
      -- The name is looked up in the current environment
      Var Name
      
    | -- | Let binding: @let x = expr1 in expr2@
      -- Introduces a new variable binding into scope for the body expression
      Let Name AST AST
      
    | -- | Binary operation: @left op right@
      -- Combines two expressions with a binary operator
      BinOp BinOp AST AST
      
    | -- | Conditional expression: @if cond then trueBranch else falseBranch@
      -- Evaluates to trueBranch if cond is true, falseBranch otherwise
      If AST AST AST
      
    | -- | Print statement: @print expr@
      -- Outputs the value of expr (side effect)
      Print AST
      
    | -- | Sequence of expressions: @expr1 ; expr2@
      -- Evaluates expr1 (for side effects), then returns expr2
      Seq AST AST
      
    | -- | Empty list literal: @[]@
      Nil
      
    | -- | Cons constructor: @head : tail@
      -- Creates a new list by prepending an element
      Cons AST AST
      
    | -- | Lambda abstraction: @\x -> body@
      -- Creates an anonymous function
      Lambda Name AST
      
    | -- | Function application: @func arg@
      -- Applies a function to an argument
      App AST AST
      
    deriving (Eq, Show)

-- | Pretty-print an AST with indentation
-- This is useful for debugging and visualization
showAST :: AST -> String
showAST = go 0
  where
    go _ (IntLit n)     = show n
    go _ (BoolLit b)    = show b
    go _ (Var name)     = name
    go _ Nil            = "[]"
    
    go indent (Let name expr body) =
        let indents = replicate indent ' '
        in concat [indents, "let ", name, " = ", go indent expr, " in\n",
                   indents, go indent body]
    
    go indent (BinOp op left right) =
        concat ["(", go indent left, " ", showOp op, " ", go indent right, ")"]
    
    go indent (If cond trueBranch falseBranch) =
        concat ["if ", go indent cond, " then ", go indent trueBranch,
                " else ", go indent falseBranch]
    
    go indent (Print expr) =
        concat ["print(", go indent expr, ")"]
    
    go indent (Seq expr1 expr2) =
        concat [go indent expr1, "; ", go indent expr2]
    
    go indent (Cons h t) =
        concat [go indent h, " : ", go indent t]
    
    go indent (Lambda param body) =
        concat ["\\", param, " -> ", go indent body]
    
    go indent (App func arg) =
        concat [go indent func, "(", go indent arg, ")"]
    
    showOp Add = "+"
    showOp Sub = "-"
    showOp Mul = "*"
    showOp Div = "/"
    showOp Eq  = "=="
    showOp Lt  = "<"
    showOp Gt  = ">"
    showOp And = "&&"
    showOp Or  = "||"
