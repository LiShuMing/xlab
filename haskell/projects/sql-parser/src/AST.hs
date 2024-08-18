{-# LANGUAGE LambdaCase #-}
{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : AST
Description : Algebraic Data Types for SQL Abstract Syntax Tree

This module defines the core AST types for our SQL parser.

Design Philosophy:
- **Immutability by Default**: All data types are immutable algebraic data types.
  This eliminates entire classes of bugs related to shared mutable state.
- **Make Impossible States Unrepresentable**: The type system encodes SQL semantics
  directly. For example, a `Select` statement must have projections (even if `*`),
  preventing malformed ASTs at compile time.
- **No Partial Functions**: Types are designed to avoid the need for partial functions
  like `head` or `fromJust`. We use `NonEmpty` lists where at least one element is
  required.
-}
module AST
    ( -- * Core Expression Types
      Expr(..)
    , BinaryOp(..)
    , Literal(..)
    
      -- * Column and Table References
    , ColumnRef(..)
    , TableRef(..)
    
      -- * SELECT Statement Components
    , SelectItem(..)
    , FromClause(..)
    , WhereClause(..)
    
      -- * The AST Root
    , Statement(..)
    , SelectStmt(..)
    ) where

import Data.Text (Text)
import Data.List.NonEmpty (NonEmpty)

-- | A reference to a column, optionally qualified with a table name.
-- Using 'Maybe TableRef' allows both 'column' and 'table.column' syntax.
data ColumnRef = ColumnRef
    { crTable  :: Maybe Text  -- ^ Optional table qualifier
    , crColumn :: Text        -- ^ Column name
    } deriving (Show, Eq)

-- | A table reference in the FROM clause.
-- Currently supports simple table names; extensible for joins later.
data TableRef = TableRef
    { trName :: Text  -- ^ Table name
    } deriving (Show, Eq)

-- | A literal value in SQL (integer, string, boolean, NULL).
-- Representing literals explicitly enables constant folding optimizations.
data Literal
    = LitInt     Int    -- ^ Integer literal
    | LitString  Text   -- ^ String literal (single-quoted)
    | LitBool    Bool   -- ^ Boolean literal (TRUE/FALSE)
    | LitNull           -- ^ NULL value
    deriving (Show, Eq)

-- | Binary operators supported in expressions.
-- Each constructor represents a distinct operation for pattern matching.
data BinaryOp
    = OpEq          -- ^ Equality (=)
    | OpNe          -- ^ Inequality (<>)
    | OpLt          -- ^ Less than (<)
    | OpLe          -- ^ Less than or equal (<=)
    | OpGt          -- ^ Greater than (>)
    | OpGe          -- ^ Greater than or equal (>=)
    | OpAdd         -- ^ Addition (+)
    | OpSub         -- ^ Subtraction (-)
    | OpMul         -- ^ Multiplication (*)
    | OpDiv         -- ^ Division (/)
    | OpAnd         -- ^ Logical AND
    | OpOr          -- ^ Logical OR
    deriving (Show, Eq)

-- | SQL expressions. This is the core recursive type for representing
-- computations, comparisons, and logical operations.
--
-- The design uses a flat sum type rather than a typed expression tree.
-- This trades some compile-time safety for parser simplicity. A more advanced
-- design could use GADTs to enforce type correctness of expressions.
data Expr
    = ELit Literal              -- ^ Literal value
    | ECol ColumnRef            -- ^ Column reference
    | EBin BinaryOp Expr Expr   -- ^ Binary operation
    | EFunc Text [Expr]         -- ^ Function call (name, arguments)
    deriving (Show, Eq)

-- | An item in the SELECT projection list.
-- Supports both 'SELECT *' and 'SELECT expr [AS alias]'.
data SelectItem
    = SelectAll                 -- ^ SELECT *
    | SelectExpr
        { siExpr :: Expr        -- ^ Expression to project
        , siAlias :: Maybe Text -- ^ Optional alias (AS name)
        } deriving (Show, Eq)

-- | The FROM clause of a SELECT statement.
-- Uses NonEmpty to enforce at least one table, matching SQL semantics.
newtype FromClause = FromClause
    { fcTables :: NonEmpty TableRef  -- ^ List of tables (for joins)
    } deriving (Show, Eq)

-- | The WHERE clause, wrapping a boolean expression.
-- Wrapped in a newtype for potential future extensions (e.g., HAVING).
newtype WhereClause = WhereClause
    { wcExpr :: Expr  -- ^ Filter predicate
    } deriving (Show, Eq)

-- | A SELECT statement AST.
-- Record syntax provides clear field names for pattern matching.
data SelectStmt = SelectStmt
    { ssSelect  :: NonEmpty SelectItem  -- ^ Projection list (at least one item)
    , ssFrom    :: Maybe FromClause     -- ^ Optional FROM clause
    , ssWhere   :: Maybe WhereClause    -- ^ Optional WHERE clause
    } deriving (Show, Eq)

-- | The root AST node. Currently only SELECT is supported, but this enables
-- future extension to INSERT, UPDATE, DELETE, etc.
data Statement
    = StmtSelect SelectStmt  -- ^ SELECT statement
    deriving (Show, Eq)
