{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : Spec
Description : Test Suite for SQL Parser and Optimizer
-}
module Main where

import Test.Hspec
import Data.Text (Text)
import qualified Data.Text as T
import qualified Data.List.NonEmpty as NE

import Parser (parseSQL)
import Optimizer (optimize, optimizeExpr)
import AST

main :: IO ()
main = hspec $ do
    describe "Parser" $ do
        it "parses simple SELECT *" $ do
            parseSQL "SELECT * FROM users" `shouldBe`
                Right (StmtSelect SelectStmt
                    { ssSelect = NE.fromList [SelectAll]
                    , ssFrom = Just $ FromClause (NE.fromList [TableRef "users"])
                    , ssWhere = Nothing
                    })

        it "parses SELECT with WHERE clause" $ do
            parseSQL "SELECT id, name FROM users WHERE id = 1" `shouldSatisfy`
                \case
                    Right (StmtSelect ss) ->
                        case ssWhere ss of
                            Just (WhereClause (EBin OpEq (ECol (ColumnRef Nothing "id")) (ELit (LitInt 1)))) -> True
                            _ -> False
                    _ -> False

        it "parses boolean expressions" $ do
            parseSQL "SELECT * FROM t WHERE a = 1 AND b = 2" `shouldSatisfy`
                \case
                    Right (StmtSelect ss) ->
                        case ssWhere ss of
                            Just (WhereClause (EBin OpAnd _ _)) -> True
                            _ -> False
                    _ -> False

        it "rejects invalid SQL" $ do
            parseSQL "SELEC * FROM t" `shouldSatisfy` \case
                Left _ -> True
                _ -> False

    describe "Optimizer" $ do
        it "performs constant folding (addition)" $ do
            let expr = EBin OpAdd (ELit (LitInt 1)) (ELit (LitInt 2))
            optimizeExpr expr `shouldBe` ELit (LitInt 3)

        it "performs constant folding (multiplication)" $ do
            let expr = EBin OpMul (ELit (LitInt 3)) (ELit (LitInt 4))
            optimizeExpr expr `shouldBe` ELit (LitInt 12)

        it "simplifies AND with TRUE" $ do
            let expr = EBin OpAnd (ELit (LitBool True)) (ECol (ColumnRef Nothing "x"))
            optimizeExpr expr `shouldBe` ECol (ColumnRef Nothing "x")

        it "simplifies AND with FALSE" $ do
            let expr = EBin OpAnd (ELit (LitBool False)) (ECol (ColumnRef Nothing "x"))
            optimizeExpr expr `shouldBe` ELit (LitBool False)

        it "simplifies OR with TRUE" $ do
            let expr = EBin OpOr (ELit (LitBool True)) (ECol (ColumnRef Nothing "x"))
            optimizeExpr expr `shouldBe` ELit (LitBool True)

        it "simplifies OR with FALSE" $ do
            let expr = EBin OpOr (ELit (LitBool False)) (ECol (ColumnRef Nothing "x"))
            optimizeExpr expr `shouldBe` ECol (ColumnRef Nothing "x")

        it "optimizes full SELECT statement" $ do
            let ast = StmtSelect SelectStmt
                    { ssSelect = NE.fromList [SelectAll]
                    , ssFrom = Just $ FromClause (NE.fromList [TableRef "t"])
                    , ssWhere = Just $ WhereClause $
                        EBin OpAnd (ELit (LitBool True)) (EBin OpEq (ECol (ColumnRef Nothing "x")) (ELit (LitInt 1)))
                    }
            case optimize ast of
                StmtSelect ss ->
                    ssWhere ss `shouldBe` Just (WhereClause $ EBin OpEq (ECol (ColumnRef Nothing "x")) (ELit (LitInt 1)))
                _ -> expectationFailure "Expected Select statement"
