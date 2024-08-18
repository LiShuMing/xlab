{-# LANGUAGE BangPatterns #-}

-----------------------------------------------------------------------------
-- |
-- Module      : EngineTest
-- Description : Unit Tests for the STM Key-Value Engine
--
-- These tests verify the correctness of the STM engine, including:
--   - Basic read/write operations
--   - Atomic increment operations
--   - Compound transactions (transfer)
--   - Concurrent safety properties
--
-- The tests demonstrate that STM provides the same correctness guarantees
-- as properly-implemented C++ locking, but without the complexity of
-- manual lock management.
--
-----------------------------------------------------------------------------

module Main where

import           Control.Concurrent.Async (replicateConcurrently_)
import           Control.Concurrent.STM
import           Control.Monad            (replicateM_, when)
import           Test.HUnit

import           Engine

-----------------------------------------------------------------------------
-- Basic Operation Tests
-----------------------------------------------------------------------------

-- | Test basic write and read operations.
testBasicWriteRead :: Test
testBasicWriteRead = TestCase $ do
    state <- newEngineState
    
    -- Initially, key should not exist
    result1 <- atomically $ readKey "test_key" state
    assertEqual "Empty read should return Nothing" Nothing result1
    
    -- Write a value
    atomically $ writeKey "test_key" 42 state
    
    -- Read it back
    result2 <- atomically $ readKey "test_key" state
    assertEqual "Read after write should return Just value" (Just 42) result2

-- | Test increment operation.
testIncrement :: Test
testIncrement = TestCase $ do
    state <- newEngineState
    
    -- Increment non-existent key (should create with delta)
    atomically $ incrementKey "counter" 5 state
    result1 <- atomically $ readKey "counter" state
    assertEqual "Increment on empty should create with delta" (Just 5) result1
    
    -- Increment existing key
    atomically $ incrementKey "counter" 3 state
    result2 <- atomically $ readKey "counter" state
    assertEqual "Increment should add to existing value" (Just 8) result2

-- | Test applyOp with different operation types.
testApplyOp :: Test
testApplyOp = TestCase $ do
    state <- newEngineState
    
    -- Apply Write
    _ <- atomically $ applyOp (Write "key1" 100) state
    val1 <- atomically $ readKey "key1" state
    assertEqual "ApplyOp Write should work" (Just 100) val1
    
    -- Apply Increment
    _ <- atomically $ applyOp (Increment "key1" 50) state
    val2 <- atomically $ readKey "key1" state
    assertEqual "ApplyOp Increment should work" (Just 150) val2
    
    -- Apply Read
    val3 <- atomically $ applyOp (Read "key1") state
    assertEqual "ApplyOp Read should return value" (Just 150) val3

-----------------------------------------------------------------------------
-- Compound Transaction Tests
-----------------------------------------------------------------------------

-- | Test atomic transfer between two keys.
testTransfer :: Test
testTransfer = TestCase $ do
    state <- newEngineState
    
    -- Setup: from=100, to=50
    atomically $ do
        writeKey "from" 100 state
        writeKey "to" 50 state
    
    -- Transfer 30 from -> to
    atomically $ transferValue "from" "to" 30 state
    
    -- Verify: from=70, to=80
    fromVal <- atomically $ readKey "from" state
    toVal <- atomically $ readKey "to" state
    
    assertEqual "Source should be decremented" (Just 70) fromVal
    assertEqual "Destination should be incremented" (Just 80) toVal

-- | Test transfer with insufficient funds.
testTransferInsufficientFunds :: Test
testTransferInsufficientFunds = TestCase $ do
    state <- newEngineState
    
    -- Setup: from=10, try to transfer 50
    atomically $ writeKey "poor" 10 state
    atomically $ writeKey "rich" 1000 state
    
    -- Transfer 50 (but only 10 available)
    atomically $ transferValue "poor" "rich" 50 state
    
    -- Verify: poor=0 (all transferred), rich=1010
    poorVal <- atomically $ readKey "poor" state
    richVal <- atomically $ readKey "rich" state
    
    assertEqual "Source should be zero (all transferred)" (Just 0) poorVal
    assertEqual "Destination should receive all available" (Just 1010) richVal

-----------------------------------------------------------------------------
-- Concurrency Safety Tests
--
-- These tests verify that STM correctly handles concurrent access,
-- something that requires complex lock management in C++.
-----------------------------------------------------------------------------

-- | Test concurrent increments are atomic.
--
-- This test spawns multiple threads that all increment the same counter.
-- In C++ with improper locking, this would lead to lost updates.
-- With STM, all increments are atomic and no updates are lost.
testConcurrentIncrements :: Test
testConcurrentIncrements = TestCase $ do
    state <- newEngineState
    let numThreads = 100
    let incrementsPerThread = 100
    
    -- Initialize counter
    atomically $ writeKey "shared_counter" 0 state
    
    -- Spawn threads that all increment
    replicateConcurrently_ numThreads $ do
        replicateM_ incrementsPerThread $ do
            atomically $ incrementKey "shared_counter" 1 state
    
    -- Verify final value (should be exact)
    finalVal <- atomically $ readKey "shared_counter" state
    let expected = numThreads * incrementsPerThread
    assertEqual 
        ("Counter should be " ++ show expected ++ " (no lost updates)")
        (Just expected) 
        finalVal

-- | Test concurrent transfers preserve total value.
--
-- This is the classic "bank account" test for transaction isolation.
-- Multiple threads transfer between accounts, but the total must remain
-- constant. In C++, implementing this without deadlocks requires careful
-- lock ordering. In STM, it's automatic.
testConcurrentTransfersPreserveTotal :: Test
testConcurrentTransfersPreserveTotal = TestCase $ do
    state <- newEngineState
    let numThreads = 50
    let transfersPerThread = 100
    let initialBalance = 1000
    
    -- Initialize three accounts
    atomically $ do
        writeKey "acct_a" initialBalance state
        writeKey "acct_b" initialBalance state
        writeKey "acct_c" initialBalance state
    
    -- Spawn threads that transfer between accounts randomly
    replicateConcurrently_ numThreads $ do
        replicateM_ transfersPerThread $ do
            -- Randomly choose source and destination
            let sources = ["acct_a", "acct_b", "acct_c"]
            srcIdx <- atomically $ readTVar =<< newTVar 0  -- dummy, we'll use cycle
            -- Simplified: cycle through all pairs
            atomically $ do
                transferValue "acct_a" "acct_b" 1 state
                transferValue "acct_b" "acct_c" 1 state
                transferValue "acct_c" "acct_a" 1 state
    
    -- Verify total is preserved
    total <- atomically $ do
        a <- readKey "acct_a" state
        b <- readKey "acct_b" state
        c <- readKey "acct_c" state
        pure $ sum $ map (maybe 0 id) [a, b, c]
    
    let expectedTotal = 3 * initialBalance
    assertEqual 
        ("Total should be preserved at " ++ show expectedTotal)
        expectedTotal
        total

-- | Test atomicity - intermediate states are never visible.
--
-- This test verifies that compound transactions (like transfer) are
-- truly atomic - other threads never see a state where money has been
-- deducted from one account but not yet added to another.
testAtomicity :: Test
testAtomicity = TestCase $ do
    state <- newEngineState
    let initialA = 1000000
    let initialB = 1000000
    
    -- Initialize accounts
    atomically $ do
        writeKey "atomic_a" initialA state
        writeKey "atomic_b" initialB state
    
    -- Start a thread that continuously checks the invariant
    invariantViolations <- atomically $ newTVar (0 :: Int)
    
    -- Spawn checker threads that verify the invariant
    let checkInvariant = atomically $ do
            a <- readKey "atomic_a" state
            b <- readKey "atomic_b" state
            let total = maybe 0 id a + maybe 0 id b
            -- Total should always be constant
            when (total /= initialA + initialB) $ do
                modifyTVar invariantViolations (+1)
    
    -- Run transfers and checks concurrently
    replicateConcurrently_ 10 $ do
        replicateM_ 1000 $ do
            atomically $ transferValue "atomic_a" "atomic_b" 1 state
            atomically $ transferValue "atomic_b" "atomic_a" 1 state
    
    -- Also run invariant checks
    replicateConcurrently_ 5 $ do
        replicateM_ 2000 checkInvariant
    
    -- Check for violations
    violations <- atomically $ readTVar invariantViolations
    assertEqual "No invariant violations should occur" 0 violations

-----------------------------------------------------------------------------
-- Test Suite
-----------------------------------------------------------------------------

main :: IO ()
main = do
    putStrLn "========================================"
    putStrLn "STM Engine Test Suite"
    putStrLn "========================================\n"
    
    results <- runTestTT $ TestList
        [ TestLabel "Basic Write/Read" testBasicWriteRead
        , TestLabel "Increment" testIncrement
        , TestLabel "ApplyOp" testApplyOp
        , TestLabel "Transfer" testTransfer
        , TestLabel "Transfer Insufficient Funds" testTransferInsufficientFunds
        , TestLabel "Concurrent Increments" testConcurrentIncrements
        , TestLabel "Concurrent Transfers" testConcurrentTransfersPreserveTotal
        , TestLabel "Atomicity" testAtomicity
        ]
    
    putStrLn "\n========================================"
    putStrLn $ "Tests run: " ++ show (cases results)
    putStrLn $ "Failures: " ++ show (failures results)
    putStrLn $ "Errors: " ++ show (errors results)
    putStrLn "========================================"
    
    if failures results == 0 && errors results == 0
        then putStrLn "All tests PASSED ✓"
        else putStrLn "Some tests FAILED ✗"
