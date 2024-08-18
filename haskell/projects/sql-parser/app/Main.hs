{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : Main
Description : SQL Parser and Optimizer Demo Application

A simple CLI demonstrating the SQL parser and optimizer.
-}
module Main where

import Data.Text (Text)
import qualified Data.Text as T
import qualified Data.Text.IO as TIO

import Parser (parseSQL)
import Optimizer (optimize)

main :: IO ()
main = do
    TIO.putStrLn "SQL Parser and Optimizer Demo"
    TIO.putStrLn "=============================="
    TIO.putStrLn ""
    TIO.putStrLn "Enter SQL (or 'quit' to exit):"
    loop

loop :: IO ()
loop = do
    TIO.putStr "> "
    input <- TIO.getLine
    if T.toLower (T.strip input) == "quit"
        then TIO.putStrLn "Goodbye!"
        else do
            case parseSQL input of
                Left err -> TIO.putStrLn $ T.pack (show err)
                Right ast -> do
                    TIO.putStrLn "\nParsed AST:"
                    TIO.putStrLn $ T.pack (show ast)
                    let optimized = optimize ast
                    TIO.putStrLn "\nOptimized AST:"
                    TIO.putStrLn $ T.pack (show optimized)
                    TIO.putStrLn ""
            loop
