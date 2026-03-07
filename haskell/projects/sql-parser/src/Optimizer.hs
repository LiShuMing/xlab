{-# LANGUAGE LambdaCase #-}
{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : Optimizer
Description : Rule-Based SQL Optimizer

This module implements a pure, rule-based optimizer for SQL ASTs.

Design Philosophy:
- **Pure Transformation**: The optimizer is a pure function `AST -> AST`.
  This guarantees referential transparency: the same input always produces
  the same output, enabling equational reasoning about optimizations.
- **Composability**: Each optimization rule is an independent function.
  Rules are composed to form the full optimization pipeline.
- **Deep Pattern Matching**: We recursively traverse the entire AST,
  applying rules at every level. This ensures optimizations are applied
  to nested expressions as well.
-}
module Optimizer
    ( optimize
    , optimizeExpr
    ) where

import AST

-- | Top-level optimization function.
--
-- This is a pure function that applies all optimization rules to a Statement.
-- The purity guarantee means:
-- 1. No side effects (no IO, no state mutation)
-- 2. Idempotent application: optimize (optimize ast) == optimize ast
-- 3. Thread-safe: can be called from multiple threads without synchronization
optimize :: Statement -> Statement
optimize = \case
    StmtSelect select -> StmtSelect (optimizeSelect select)

-- | Optimize a SELECT statement by transforming all components.
optimizeSelect :: SelectStmt -> SelectStmt
optimizeSelect ss = ss
    { ssSelect = fmap optimizeSelectItem (ssSelect ss)
    , ssFrom   = ssFrom ss  -- FROM clause has no expressions to optimize
    , ssWhere  = optimizeWhere <$> ssWhere ss
    }

-- | Optimize a SELECT item's expression.
optimizeSelectItem :: SelectItem -> SelectItem
optimizeSelectItem = \case
    SelectAll -> SelectAll
    SelectExpr expr alias -> SelectExpr (optimizeExpr expr) alias

-- | Optimize a WHERE clause by transforming its expression.
optimizeWhere :: WhereClause -> WhereClause
optimizeWhere (WhereClause expr) = WhereClause (optimizeExpr expr)

-- | Optimize an expression by applying all rules recursively.
--
-- The strategy is:
-- 1. First, recursively optimize all sub-expressions (bottom-up traversal)
-- 2. Then, apply optimization rules to the current node
--
-- This order ensures that rules see optimized children, enabling
-- multi-level optimizations (e.g., constant folding through multiple levels).
optimizeExpr :: Expr -> Expr
optimizeExpr = \case
    ELit lit -> ELit lit  -- Literals are already optimized
    ECol col -> ECol col  -- Column refs are already optimized
    EFunc name args -> EFunc name (map optimizeExpr args)
    EBin op left right ->
        let left'  = optimizeExpr left
            right' = optimizeExpr right
            -- Apply rules to the binary expression
        in applyRules op left' right'

-- | Apply optimization rules to a binary expression.
-- Rules are applied in sequence; each rule can transform the expression.
applyRules :: BinaryOp -> Expr -> Expr -> Expr
applyRules op left right =
    -- Rule 1: Constant Folding for arithmetic operations
    case (op, left, right) of
        (OpAdd, ELit (LitInt l), ELit (LitInt r)) -> ELit (LitInt (l + r))
        (OpSub, ELit (LitInt l), ELit (LitInt r)) -> ELit (LitInt (l - r))
        (OpMul, ELit (LitInt l), ELit (LitInt r)) -> ELit (LitInt (l * r))
        (OpDiv, ELit (LitInt l), ELit (LitInt r)) 
            | r /= 0 -> ELit (LitInt (l `div` r))
        -- Rule 2: Boolean simplification (AND with TRUE/FALSE)
        (OpAnd, ELit (LitBool True), expr) -> expr
        (OpAnd, expr, ELit (LitBool True)) -> expr
        (OpAnd, ELit (LitBool False), _) -> ELit (LitBool False)
        (OpAnd, _, ELit (LitBool False)) -> ELit (LitBool False)
        -- Rule 3: Boolean simplification (OR with TRUE/FALSE)
        (OpOr, ELit (LitBool True), _) -> ELit (LitBool True)
        (OpOr, _, ELit (LitBool True)) -> ELit (LitBool True)
        (OpOr, ELit (LitBool False), expr) -> expr
        (OpOr, expr, ELit (LitBool False)) -> expr
        -- Rule 4: Comparison of identical constants
        (OpEq, ELit l, ELit r) | l == r -> ELit (LitBool True)
        (OpEq, ELit l, ELit r) | l /= r -> ELit (LitBool False)
        (OpNe, ELit l, ELit r) | l == r -> ELit (LitBool False)
        (OpNe, ELit l, ELit r) | l /= r -> ELit (LitBool True)
        -- No rule applies; reconstruct the expression
        _ -> EBin op left right

-- | Additional optimization rules could be added here:
-- 
-- * Predicate Pushdown: Move predicates closer to data sources
-- * Expression Simplification: x = x -> TRUE, x + 0 -> x
-- * Dead Code Elimination: Remove unused projections
--
-- The modular design makes adding new rules straightforward.
