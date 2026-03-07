{-|
Module      : Spec
Description : Test Suite for the DSL Interpreter

This module contains a comprehensive test suite demonstrating:
1. Unit tests with HUnit for specific evaluation cases
2. Property-based tests with QuickCheck for algebraic laws
3. Error handling verification
4. Monad transformer stack verification

The tests verify both the correctness of the evaluator and the
properties guaranteed by the monadic structure.
-}
module Main where

import Test.HUnit
import Test.QuickCheck
import Control.Monad.Identity

import Syntax
import Eval

-- ---------------------------------------------------------------------------
-- Unit Tests: Basic Literals
-- ---------------------------------------------------------------------------

testIntLiteral :: Test
testIntLiteral = TestCase $ do
    let ast = IntLit 42
    case evalProgram ast of
        Right (VInt 42, [], 1) -> return ()
        other -> assertFailure $ "Expected VInt 42, got: " ++ show other

testBoolLiteralTrue :: Test
testBoolLiteralTrue = TestCase $ do
    let ast = BoolLit True
    case evalProgram ast of
        Right (VBool True, [], 1) -> return ()
        other -> assertFailure $ "Expected VBool True, got: " ++ show other

testBoolLiteralFalse :: Test
testBoolLiteralFalse = TestCase $ do
    let ast = BoolLit False
    case evalProgram ast of
        Right (VBool False, [], 1) -> return ()
        other -> assertFailure $ "Expected VBool False, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Arithmetic Operations
-- ---------------------------------------------------------------------------

testAddition :: Test
testAddition = TestCase $ do
    let ast = BinOp Add (IntLit 10) (IntLit 5)
    case evalProgram ast of
        Right (VInt 15, [], 3) -> return ()
        other -> assertFailure $ "Expected VInt 15, got: " ++ show other

testSubtraction :: Test
testSubtraction = TestCase $ do
    let ast = BinOp Sub (IntLit 10) (IntLit 3)
    case evalProgram ast of
        Right (VInt 7, [], 3) -> return ()
        other -> assertFailure $ "Expected VInt 7, got: " ++ show other

testMultiplication :: Test
testMultiplication = TestCase $ do
    let ast = BinOp Mul (IntLit 6) (IntLit 7)
    case evalProgram ast of
        Right (VInt 42, [], 3) -> return ()
        other -> assertFailure $ "Expected VInt 42, got: " ++ show other

testDivision :: Test
testDivision = TestCase $ do
    let ast = BinOp Div (IntLit 20) (IntLit 4)
    case evalProgram ast of
        Right (VInt 5, [], 3) -> return ()
        other -> assertFailure $ "Expected VInt 5, got: " ++ show other

testDivisionByZero :: Test
testDivisionByZero = TestCase $ do
    let ast = BinOp Div (IntLit 10) (IntLit 0)
    case evalProgram ast of
        Left "Division by zero" -> return ()
        other -> assertFailure $ "Expected division by zero error, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Comparison Operations
-- ---------------------------------------------------------------------------

testLessThanTrue :: Test
testLessThanTrue = TestCase $ do
    let ast = BinOp Lt (IntLit 3) (IntLit 5)
    case evalProgram ast of
        Right (VBool True, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool True, got: " ++ show other

testLessThanFalse :: Test
testLessThanFalse = TestCase $ do
    let ast = BinOp Lt (IntLit 5) (IntLit 3)
    case evalProgram ast of
        Right (VBool False, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool False, got: " ++ show other

testEqualityInt :: Test
testEqualityInt = TestCase $ do
    let ast = BinOp Eq (IntLit 42) (IntLit 42)
    case evalProgram ast of
        Right (VBool True, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool True, got: " ++ show other

testEqualityBool :: Test
testEqualityBool = TestCase $ do
    let ast = BinOp Eq (BoolLit True) (BoolLit True)
    case evalProgram ast of
        Right (VBool True, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool True, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Boolean Operations
-- ---------------------------------------------------------------------------

testAndTrue :: Test
testAndTrue = TestCase $ do
    let ast = BinOp And (BoolLit True) (BoolLit True)
    case evalProgram ast of
        Right (VBool True, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool True, got: " ++ show other

testAndFalse :: Test
testAndFalse = TestCase $ do
    let ast = BinOp And (BoolLit True) (BoolLit False)
    case evalProgram ast of
        Right (VBool False, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool False, got: " ++ show other

testOrTrue :: Test
testOrTrue = TestCase $ do
    let ast = BinOp Or (BoolLit False) (BoolLit True)
    case evalProgram ast of
        Right (VBool True, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool True, got: " ++ show other

testOrFalse :: Test
testOrFalse = TestCase $ do
    let ast = BinOp Or (BoolLit False) (BoolLit False)
    case evalProgram ast of
        Right (VBool False, [], 3) -> return ()
        other -> assertFailure $ "Expected VBool False, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Let Bindings
-- ---------------------------------------------------------------------------

testSimpleLet :: Test
testSimpleLet = TestCase $ do
    let ast = Let "x" (IntLit 10) (Var "x")
    case evalProgram ast of
        Right (VInt 10, [], 3) -> return ()
        other -> assertFailure $ "Expected VInt 10, got: " ++ show other

testLetWithExpression :: Test
testLetWithExpression = TestCase $ do
    let ast = Let "x" (BinOp Add (IntLit 5) (IntLit 5)) (BinOp Mul (Var "x") (IntLit 2))
    case evalProgram ast of
        Right (VInt 20, [], 7) -> return ()
        other -> assertFailure $ "Expected VInt 20, got: " ++ show other

testNestedLet :: Test
testNestedLet = TestCase $ do
    let ast = Let "x" (IntLit 5)
            (Let "y" (IntLit 10)
              (BinOp Add (Var "x") (Var "y")))
    case evalProgram ast of
        Right (VInt 15, [], 7) -> return ()
        other -> assertFailure $ "Expected VInt 15, got: " ++ show other

testVariableShadowing :: Test
testVariableShadowing = TestCase $ do
    -- let x = 10 in let x = 20 in x + 5 = 25 (not 15)
    let ast = Let "x" (IntLit 10)
            (Let "x" (IntLit 20)
              (BinOp Add (Var "x") (IntLit 5)))
    case evalProgram ast of
        Right (VInt 25, [], 7) -> return ()
        other -> assertFailure $ "Expected VInt 25 (shadowing), got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Conditionals
-- ---------------------------------------------------------------------------

testIfTrueBranch :: Test
testIfTrueBranch = TestCase $ do
    let ast = If (BoolLit True) (IntLit 100) (IntLit 200)
    case evalProgram ast of
        Right (VInt 100, [], 3) -> return ()
        other -> assertFailure $ "Expected VInt 100, got: " ++ show other

testIfFalseBranch :: Test
testIfFalseBranch = TestCase $ do
    let ast = If (BoolLit False) (IntLit 100) (IntLit 200)
    case evalProgram ast of
        Right (VInt 200, [], 3) -> return ()
        other -> assertFailure $ "Expected VInt 200, got: " ++ show other

testIfWithCondition :: Test
testIfWithCondition = TestCase $ do
    let ast = If (BinOp Lt (IntLit 3) (IntLit 5)) (IntLit 1) (IntLit 0)
    case evalProgram ast of
        Right (VInt 1, [], 5) -> return ()
        other -> assertFailure $ "Expected VInt 1, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Lists
-- ---------------------------------------------------------------------------

testEmptyList :: Test
testEmptyList = TestCase $ do
    let ast = Nil
    case evalProgram ast of
        Right (VNil, [], 1) -> return ()
        other -> assertFailure $ "Expected VNil, got: " ++ show other

testSingleElementList :: Test
testSingleElementList = TestCase $ do
    let ast = Cons (IntLit 42) Nil
    case evalProgram ast of
        Right (VCons (VInt 42) VNil, [], 3) -> return ()
        other -> assertFailure $ "Expected [42], got: " ++ show other

testMultiElementList :: Test
testMultiElementList = TestCase $ do
    let ast = Cons (IntLit 1) (Cons (IntLit 2) (Cons (IntLit 3) Nil))
    case evalProgram ast of
        Right (VCons (VInt 1) (VCons (VInt 2) (VCons (VInt 3) VNil)), [], 7) -> return ()
        other -> assertFailure $ "Expected [1,2,3], got: " ++ show other

testListEquality :: Test
testListEquality = TestCase $ do
    let list1 = Cons (IntLit 1) (Cons (IntLit 2) Nil)
        list2 = Cons (IntLit 1) (Cons (IntLit 2) Nil)
        ast = BinOp Eq list1 list2
    case evalProgram ast of
        Right (VBool True, [], 11) -> return ()
        other -> assertFailure $ "Expected equal lists (VBool True), got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Lambda and Closures
-- ---------------------------------------------------------------------------

testIdentityFunction :: Test
testIdentityFunction = TestCase $ do
    -- (\x -> x) 42 = 42
    let ast = App (Lambda "x" (Var "x")) (IntLit 42)
    case evalProgram ast of
        Right (VInt 42, [], 4) -> return ()
        other -> assertFailure $ "Expected VInt 42, got: " ++ show other

testConstantFunction :: Test
testConstantFunction = TestCase $ do
    -- (\x -> 100) 42 = 100
    let ast = App (Lambda "x" (IntLit 100)) (IntLit 42)
    case evalProgram ast of
        Right (VInt 100, [], 4) -> return ()
        other -> assertFailure $ "Expected VInt 100, got: " ++ show other

testClosureCapture :: Test
testClosureCapture = TestCase $ do
    -- let x = 10 in let f = \y -> x + y in let x = 20 in f 5 = 15
    let ast = Let "x" (IntLit 10)
            (Let "f" (Lambda "y" (BinOp Add (Var "x") (Var "y")))
              (Let "x" (IntLit 20)
                (App (Var "f") (IntLit 5))))
    case evalProgram ast of
        Right (VInt 15, [], 12) -> return ()
        other -> assertFailure $ "Expected VInt 15 (closure), got: " ++ show other

testCurriedFunction :: Test
testCurriedFunction = TestCase $ do
    -- let add = \x -> \y -> x + y in add 3 4 = 7
    let ast = Let "add" (Lambda "x" (Lambda "y" (BinOp Add (Var "x") (Var "y"))))
            (App (App (Var "add") (IntLit 3)) (IntLit 4))
    case evalProgram ast of
        Right (VInt 7, [], 11) -> return ()
        other -> assertFailure $ "Expected VInt 7, got: " ++ show other

testHigherOrderFunction :: Test
testHigherOrderFunction = TestCase $ do
    -- let twice = \f -> \x -> f (f x) in
    -- let inc = \x -> x + 1 in twice inc 5 = 7
    let ast = Let "twice" (Lambda "f" (Lambda "x" 
                  (App (Var "f") (App (Var "f") (Var "x")))))
            (Let "inc" (Lambda "x" (BinOp Add (Var "x") (IntLit 1)))
              (App (App (Var "twice") (Var "inc")) (IntLit 5)))
    case evalProgram ast of
        Right (VInt 7, [], 21) -> return ()
        other -> assertFailure $ "Expected VInt 7, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Print and Sequencing
-- ---------------------------------------------------------------------------

testPrintStatement :: Test
testPrintStatement = TestCase $ do
    let ast = Print (IntLit 42)
    case evalProgram ast of
        Right (VUnit, ["42"], 2) -> return ()
        other -> assertFailure $ "Expected VUnit with log, got: " ++ show other

testSequence :: Test
testSequence = TestCase $ do
    -- (print 1; 42) = 42 with log ["1"]
    let ast = Seq (Print (IntLit 1)) (IntLit 42)
    case evalProgram ast of
        Right (VInt 42, ["1"], 4) -> return ()
        other -> assertFailure $ "Expected VInt 42 with log, got: " ++ show other

testMultiplePrints :: Test
testMultiplePrints = TestCase $ do
    -- print 1; print 2; print 3; 42
    let ast = Seq (Print (IntLit 1))
              (Seq (Print (IntLit 2))
                (Seq (Print (IntLit 3)) (IntLit 42)))
    case evalProgram ast of
        Right (VInt 42, ["1", "2", "3"], 10) -> return ()
        other -> assertFailure $ "Expected VInt 42 with log [1,2,3], got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Error Handling
-- ---------------------------------------------------------------------------

testUndefinedVariable :: Test
testUndefinedVariable = TestCase $ do
    let ast = Var "undefined"
    case evalProgram ast of
        Left "Undefined variable: undefined" -> return ()
        other -> assertFailure $ "Expected undefined variable error, got: " ++ show other

testTypeMismatchInIf :: Test
testTypeMismatchInIf = TestCase $ do
    let ast = If (IntLit 1) (IntLit 0) (IntLit 1)
    case evalProgram ast of
        Left "Type mismatch" -> return ()
        Left _ -> return ()  -- Any type mismatch error is acceptable
        other -> assertFailure $ "Expected type mismatch error, got: " ++ show other

testNotAFunction :: Test
testNotAFunction = TestCase $ do
    let ast = App (IntLit 42) (IntLit 1)
    case evalProgram ast of
        Left "Not a function" -> return ()
        Left _ -> return ()  -- Any appropriate error
        other -> assertFailure $ "Expected 'not a function' error, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Unit Tests: Monad Transformer Stack Verification
-- ---------------------------------------------------------------------------

testStateCounting :: Test
testStateCounting = TestCase $ do
    -- Every eval call increments step counter
    let ast = BinOp Add (IntLit 1) (IntLit 2)  -- 1 + 2
    case evalProgram ast of
        Right (VInt 3, [], 3) -> return ()  -- IntLit(1) + IntLit(2) + Add = 3 steps
        other -> assertFailure $ "Expected 3 steps, got: " ++ show other

testStatePreservedAcrossLet :: Test
testStatePreservedAcrossLet = TestCase $ do
    -- let x = 1 in x + 2
    let ast = Let "x" (IntLit 1) (BinOp Add (Var "x") (IntLit 2))
    case evalProgram ast of
        Right (VInt 3, [], 5) -> return ()  -- let evals expr(1) + body(3) + 1 let = 5
        other -> assertFailure $ "Expected 5 steps, got: " ++ show other

-- ---------------------------------------------------------------------------
-- Property-Based Tests: QuickCheck
-- ---------------------------------------------------------------------------

-- | Generator for integer literals
intLitGen :: Gen AST
intLitGen = IntLit <$> arbitrary

-- | Generator for boolean literals
boolLitGen :: Gen AST
boolLitGen = BoolLit <$> arbitrary

-- | Generator for simple arithmetic expressions
arithExprGen :: Gen AST
arithExprGen = do
    op <- elements [Add, Sub, Mul]
    n1 <- arbitrary :: Gen Integer
    n2 <- arbitrary :: Gen Integer
    -- Avoid division by zero issues in property tests
    return $ BinOp op (IntLit n1) (IntLit n2)

-- Property: Addition is commutative in our DSL
prop_addCommutative :: Integer -> Integer -> Bool
prop_addCommutative x y =
    let expr1 = BinOp Add (IntLit x) (IntLit y)
        expr2 = BinOp Add (IntLit y) (IntLit x)
        result1 = case evalProgram expr1 of Right (VInt n, _, _) -> n; _ -> 0
        result2 = case evalProgram expr2 of Right (VInt n, _, _) -> n; _ -> 0
    in result1 == result2

-- Property: Multiplication is commutative
prop_mulCommutative :: Integer -> Integer -> Bool
prop_mulCommutative x y =
    let expr1 = BinOp Mul (IntLit x) (IntLit y)
        expr2 = BinOp Mul (IntLit y) (IntLit x)
        result1 = case evalProgram expr1 of Right (VInt n, _, _) -> n; _ -> 0
        result2 = case evalProgram expr2 of Right (VInt n, _, _) -> n; _ -> 0
    in result1 == result2

-- Property: x - x = 0
prop_subtractSelf :: Integer -> Bool
prop_subtractSelf x =
    let expr = BinOp Sub (IntLit x) (IntLit x)
    in case evalProgram expr of
        Right (VInt 0, _, _) -> True
        _ -> False

-- Property: x * 0 = 0
prop_multiplyZero :: Integer -> Bool
prop_multiplyZero x =
    let expr = BinOp Mul (IntLit x) (IntLit 0)
    in case evalProgram expr of
        Right (VInt 0, _, _) -> True
        _ -> False

-- Property: x + 0 = x
prop_addIdentity :: Integer -> Bool
prop_addIdentity x =
    let expr = BinOp Add (IntLit x) (IntLit 0)
    in case evalProgram expr of
        Right (VInt n, _, _) -> n == x
        _ -> False

-- Property: Equality is reflexive
prop_eqReflexive :: Integer -> Bool
prop_eqReflexive x =
    let expr = BinOp Eq (IntLit x) (IntLit x)
    in case evalProgram expr of
        Right (VBool True, _, _) -> True
        _ -> False

-- Property: Let-binding simple substitution
prop_letSubstitution :: Integer -> Bool
prop_letSubstitution x =
    let expr = Let "v" (IntLit x) (Var "v")
    in case evalProgram expr of
        Right (VInt n, _, _) -> n == x
        _ -> False

-- Property: Identity function returns argument
prop_identityFunction :: Integer -> Bool
prop_identityFunction x =
    let expr = App (Lambda "x" (Var "x")) (IntLit x)
    in case evalProgram expr of
        Right (VInt n, _, _) -> n == x
        _ -> False

-- ---------------------------------------------------------------------------
-- Test Suites
-- ---------------------------------------------------------------------------

basicTests :: Test
basicTests = TestLabel "Basic Literals" $ TestList
    [ testIntLiteral
    , testBoolLiteralTrue
    , testBoolLiteralFalse
    ]

arithmeticTests :: Test
arithmeticTests = TestLabel "Arithmetic Operations" $ TestList
    [ testAddition
    , testSubtraction
    , testMultiplication
    , testDivision
    , testDivisionByZero
    ]

comparisonTests :: Test
comparisonTests = TestLabel "Comparison Operations" $ TestList
    [ testLessThanTrue
    , testLessThanFalse
    , testEqualityInt
    , testEqualityBool
    ]

booleanTests :: Test
booleanTests = TestLabel "Boolean Operations" $ TestList
    [ testAndTrue
    , testAndFalse
    , testOrTrue
    , testOrFalse
    ]

letBindingTests :: Test
letBindingTests = TestLabel "Let Bindings" $ TestList
    [ testSimpleLet
    , testLetWithExpression
    , testNestedLet
    , testVariableShadowing
    ]

conditionalTests :: Test
conditionalTests = TestLabel "Conditionals" $ TestList
    [ testIfTrueBranch
    , testIfFalseBranch
    , testIfWithCondition
    ]

listTests :: Test
listTests = TestLabel "Lists" $ TestList
    [ testEmptyList
    , testSingleElementList
    , testMultiElementList
    , testListEquality
    ]

lambdaTests :: Test
lambdaTests = TestLabel "Lambda and Closures" $ TestList
    [ testIdentityFunction
    , testConstantFunction
    , testClosureCapture
    , testCurriedFunction
    , testHigherOrderFunction
    ]

sideEffectTests :: Test
sideEffectTests = TestLabel "Print and Sequencing" $ TestList
    [ testPrintStatement
    , testSequence
    , testMultiplePrints
    ]

errorHandlingTests :: Test
errorHandlingTests = TestLabel "Error Handling" $ TestList
    [ testUndefinedVariable
    , testTypeMismatchInIf
    , testNotAFunction
    ]

monadTransformerTests :: Test
monadTransformerTests = TestLabel "Monad Transformer Stack" $ TestList
    [ testStateCounting
    , testStatePreservedAcrossLet
    ]

allTests :: Test
allTests = TestList
    [ basicTests
    , arithmeticTests
    , comparisonTests
    , booleanTests
    , letBindingTests
    , conditionalTests
    , listTests
    , lambdaTests
    , sideEffectTests
    , errorHandlingTests
    , monadTransformerTests
    ]

-- ---------------------------------------------------------------------------
-- Main
-- ---------------------------------------------------------------------------

main :: IO ()
main = do
    putStrLn "==============================================="
    putStrLn "  DSL Interpreter Test Suite"
    putStrLn "==============================================="
    putStrLn ""
    
    -- Run HUnit tests
    putStrLn "Running Unit Tests..."
    putStrLn "---------------------"
    counts <- runTestTT allTests
    putStrLn ""
    
    -- Run QuickCheck property tests
    putStrLn "Running Property Tests..."
    putStrLn "-------------------------"
    
    putStrLn "\nProperty: Addition is commutative"
    quickCheck prop_addCommutative
    
    putStrLn "\nProperty: Multiplication is commutative"
    quickCheck prop_mulCommutative
    
    putStrLn "\nProperty: x - x = 0"
    quickCheck prop_subtractSelf
    
    putStrLn "\nProperty: x * 0 = 0"
    quickCheck prop_multiplyZero
    
    putStrLn "\nProperty: x + 0 = x"
    quickCheck prop_addIdentity
    
    putStrLn "\nProperty: Equality is reflexive"
    quickCheck prop_eqReflexive
    
    putStrLn "\nProperty: Let-binding substitution"
    quickCheck prop_letSubstitution
    
    putStrLn "\nProperty: Identity function returns argument"
    quickCheck prop_identityFunction
    
    putStrLn ""
    putStrLn "==============================================="
    putStrLn $ "Unit Test Summary: " ++ show counts
    putStrLn "==============================================="
    
    -- Exit with error code if any tests failed
    if errors counts > 0 || failures counts > 0
        then error "Tests failed!"
        else putStrLn "All tests passed!"
