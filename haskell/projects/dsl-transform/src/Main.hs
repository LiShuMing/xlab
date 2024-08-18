{-|
Module      : Main
Description : Entry point and examples for the DSL Interpreter

This module demonstrates the DSL interpreter with several example programs
that showcase different features:

1. Simple arithmetic and let bindings
2. Conditionals and comparison
3. Lists and recursion (via Church encoding or explicit recursion)
4. Lambda functions and closures
5. Error handling
6. Print statements and logging
7. Complex nested expressions

Each example prints both the source AST and the evaluation result.
-}
module Main where

import Syntax (AST(..), BinOp(..), showAST)
import Eval (Value(..), evalProgram, showValue)

-- ---------------------------------------------------------------------------
-- Example Programs
-- ---------------------------------------------------------------------------

-- | Example 1: Simple arithmetic
-- let x = 10 + 5 in x * 2
example1 :: AST
example1 = Let "x" (BinOp Add (IntLit 10) (IntLit 5))
           (BinOp Mul (Var "x") (IntLit 2))

-- | Example 2: Conditional expression
-- if 5 > 3 then 100 else 200
example2 :: AST
example2 = If (BinOp Gt (IntLit 5) (IntLit 3))
              (IntLit 100)
              (IntLit 200)

-- | Example 3: Let with shadowing
-- let x = 10 in let x = 20 in x + 5
-- Result should be 25 (inner x shadows outer x)
example3 :: AST
example3 = Let "x" (IntLit 10)
           (Let "x" (IntLit 20)
             (BinOp Add (Var "x") (IntLit 5)))

-- | Example 4: Lambda and application
-- let add = \x -> \y -> x + y in (add 10) 20
example4 :: AST
example4 = Let "add" (Lambda "x" (Lambda "y" (BinOp Add (Var "x") (Var "y"))))
           (App (App (Var "add") (IntLit 10)) (IntLit 20))

-- | Example 5: Factorial using recursion (Y-combinator style would be complex,
-- so we use a simplified nested let for demonstration)
-- let fact = \n -> if n == 0 then 1 else n * fact (n - 1) in fact 5
-- Note: This won't actually work without fixpoint, so we do manual unrolling
example5 :: AST
example5 = Let "fact" (Lambda "n" 
             (If (BinOp Eq (Var "n") (IntLit 0))
                 (IntLit 1)
                 (BinOp Mul (Var "n") 
                   (App (Var "fact") (BinOp Sub (Var "n") (IntLit 1))))))
           (App (Var "fact") (IntLit 5))

-- | Example 6: Print statements and sequencing
-- let x = 10 in (print x; x + 5)
example6 :: AST
example6 = Let "x" (IntLit 10)
           (Seq (Print (Var "x"))
                (BinOp Add (Var "x") (IntLit 5)))

-- | Example 7: List construction
-- 1 : 2 : 3 : []
example7 :: AST
example7 = Cons (IntLit 1) 
           (Cons (IntLit 2) 
             (Cons (IntLit 3) Nil))

-- | Example 8: Boolean operations
-- (5 < 10) && (20 > 15)
example8 :: AST
example8 = BinOp And 
             (BinOp Lt (IntLit 5) (IntLit 10))
             (BinOp Gt (IntLit 20) (IntLit 15))

-- | Example 9: Undefined variable (error handling demo)
example9 :: AST
example9 = Var "undefinedVariable"

-- | Example 10: Division by zero (error handling demo)
example10 :: AST
example10 = BinOp Div (IntLit 10) (IntLit 0)

-- | Example 11: Complex nested expression
-- let x = 5 in let y = x * 2 in if y > 5 then y + x else y - x
example11 :: AST
example11 = Let "x" (IntLit 5)
            (Let "y" (BinOp Mul (Var "x") (IntLit 2))
              (If (BinOp Gt (Var "y") (IntLit 5))
                  (BinOp Add (Var "y") (Var "x"))
                  (BinOp Sub (Var "y") (Var "x"))))

-- | Example 12: Higher-order function (map simulation)
-- let twice = \f -> \x -> f (f x) in
-- let addOne = \x -> x + 1 in
-- twice addOne 5  => 7
example12 :: AST
example12 = Let "twice" (Lambda "f" (Lambda "x" 
              (App (Var "f") (App (Var "f") (Var "x")))))
            (Let "addOne" (Lambda "x" (BinOp Add (Var "x") (IntLit 1)))
              (App (App (Var "twice") (Var "addOne")) (IntLit 5)))

-- | Example 13: Closure capturing
-- let x = 10 in let f = \y -> x + y in let x = 20 in f 5
-- Result should be 15 (f captured x=10, not the new x=20)
example13 :: AST
example13 = Let "x" (IntLit 10)
            (Let "f" (Lambda "y" (BinOp Add (Var "x") (Var "y")))
              (Let "x" (IntLit 20)
                (App (Var "f") (IntLit 5))))

-- | Example 14: Multiple print statements
-- (print 1; print 2; print 3; 42)
example14 :: AST
example14 = Seq (Print (IntLit 1))
            (Seq (Print (IntLit 2))
              (Seq (Print (IntLit 3))
                (IntLit 42)))

-- | Example 15: List equality
-- [1, 2] == [1, 2]
example15 :: AST
example15 = BinOp Eq 
              (Cons (IntLit 1) (Cons (IntLit 2) Nil))
              (Cons (IntLit 1) (Cons (IntLit 2) Nil))

-- ---------------------------------------------------------------------------
-- Running Examples
-- ---------------------------------------------------------------------------

-- | Run a single example and print formatted output
runExample :: String -> AST -> IO ()
runExample name ast = do
    putStrLn $ replicate 60 '='
    putStrLn $ "Example: " ++ name
    putStrLn $ replicate 60 '-'
    putStrLn "AST:"
    putStrLn $ showAST ast
    putStrLn $ replicate 40 '-'
    putStrLn "Result:"
    case evalProgram ast of
        Left err -> putStrLn $ "ERROR: " ++ err
        Right (val, logs, steps) -> do
            putStrLn $ "Value:   " ++ showValue val
            putStrLn $ "Steps:   " ++ show steps
            if null logs 
                then return ()
                else putStrLn $ "Log:     " ++ show logs
    putStrLn ""

-- | Main entry point
main :: IO ()
main = do
    putStrLn ""
    putStrLn "  ============================================"
    putStrLn "  DSL Interpreter using Monad Transformers"
    putStrLn "  ============================================"
    putStrLn ""
    putStrLn "  This interpreter demonstrates the use of mtl"
    putStrLn "  (Monad Transformer Library) to compose:"
    putStrLn "    - ReaderT: Environment (variable bindings)"
    putStrLn "    - ExceptT: Error handling"
    putStrLn "    - StateT:  Execution state (steps, logs)"
    putStrLn ""
    
    runExample "Simple Arithmetic" example1
    runExample "Conditional" example2
    runExample "Variable Shadowing" example3
    runExample "Lambda and Application" example4
    runExample "Factorial (recursive)" example5
    runExample "Print Statements" example6
    runExample "List Construction" example7
    runExample "Boolean Operations" example8
    runExample "Undefined Variable (Error)" example9
    runExample "Division by Zero (Error)" example10
    runExample "Complex Nested Expression" example11
    runExample "Higher-Order Function" example12
    runExample "Closure Capturing" example13
    runExample "Multiple Prints" example14
    runExample "List Equality" example15
    
    putStrLn $ replicate 60 '='
    putStrLn "All examples completed!"
