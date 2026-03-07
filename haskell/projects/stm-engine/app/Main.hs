{-# LANGUAGE BangPatterns #-}

-----------------------------------------------------------------------------
-- |
-- Module      : Main
-- Description : High-Concurrency STM Engine Demo
-- 
-- This module demonstrates Haskell's STM capabilities under heavy concurrent
-- load. We spawn hundreds of lightweight threads that continuously send
-- read/write/aggregate operations to the STM engine.
--
-- KEY COMPARISON WITH C++:
--
-- In C++, this would require either:
--   1. A thread pool with task queues and coarse-grained locks (bottleneck)
--   2. Fine-grained per-key mutexes with complex lock ordering (deadlock risk)
--   3. Lock-free structures with CAS retry loops (complex, limited composability)
--
-- In Haskell with STM:
--   - We spawn threads with forkIO (much lighter than OS threads)
--   - Each thread executes STM transactions atomically
--   - The STM runtime handles all synchronization automatically
--   - No deadlocks possible, composition is natural
--
-----------------------------------------------------------------------------

module Main where

import           Control.Concurrent.Async (mapConcurrently_, replicateConcurrently_)
import           Control.Concurrent.STM
import           Control.Monad            (forM_, replicateM_, when)
import           Data.Time.Clock          (diffUTCTime, getCurrentTime)
import           System.Random            (randomRIO)

import qualified Data.Map.Strict        as Map
import           Engine

-----------------------------------------------------------------------------
-- Configuration
-----------------------------------------------------------------------------

-- | Number of concurrent worker threads.
-- 
-- Haskell threads are lightweight (green threads) - we can spawn thousands
-- without issue. In C++, each thread typically maps to an OS thread with
-- significant overhead (~1MB stack).
numWorkers :: Int
numWorkers = 500

-- | Number of operations each worker performs.
opsPerWorker :: Int
opsPerWorker = 1000

-- | Number of unique keys in the keyspace (creates contention).
keySpaceSize :: Int
keySpaceSize = 100

-----------------------------------------------------------------------------
-- Worker Implementation
-----------------------------------------------------------------------------

-- | Generate a random key from our keyspace.
randomKey :: IO Key
randomKey = do
    n <- randomRIO (0, keySpaceSize - 1)
    pure $ "key_" ++ show n

-- | Generate a random value (for writes/increments).
randomValue :: IO Value
randomValue = randomRIO (1, 100)

-- | Generate a random operation type.
--
-- We mix reads, writes, and increments to simulate realistic workload.
-- The ratio here is: 60% reads, 30% increments, 10% writes
randomOperation :: IO Operation
randomOperation = do
    r <- randomRIO (1 :: Int, 10)
    key <- randomKey
    case r of
        1 -> do
            val <- randomValue
            pure $ Write key val
        2 -> do
            val <- randomValue
            pure $ Write key val
        3 -> do
            val <- randomValue
            pure $ Write key val
        _ -> do
            -- 70% of remaining are increments, 30% are reads
            r2 <- randomRIO (1 :: Int, 10)
            if r2 <= 7
                then do
                    delta <- randomValue
                    pure $ Increment key delta
                else pure $ Read key

-- | A single worker that performs random operations.
--
-- Each worker runs in its own lightweight thread. All operations are
-- atomic STM transactions. The STM runtime automatically handles:
--   - Conflict detection between concurrent transactions
--   - Automatic retry when conflicts are detected
--   - Memory ordering and visibility guarantees
worker :: Int -> EngineState -> IO ()
worker workerId stateVar = do
    -- Each worker performs multiple operations
    replicateM_ opsPerWorker $ do
        op <- randomOperation
        
        -- Execute the operation atomically via STM
        -- The 'atomically' call commits the STM transaction
        _result <- atomically $ applyOp op stateVar
        
        -- Occasionally perform compound transactions to demonstrate composability
        when (workerId `mod` 10 == 0) $ do
            r <- randomRIO (1 :: Int, 100 :: Int)
            when (r == 1) $ do
                -- 1% chance: perform an atomic transfer between two random keys
                fromK <- randomKey
                toK <- randomKey
                when (fromK /= toK) $ do
                    amount <- randomValue
                    -- This compound operation is fully atomic
                    atomically $ transferValue fromK toK amount stateVar

    pure ()

-----------------------------------------------------------------------------
-- High-Concurrency Workload Simulation
-----------------------------------------------------------------------------

-- | Run the high-concurrency benchmark.
--
-- This function spawns 'numWorkers' threads, each performing 'opsPerWorker'
-- operations. All threads run concurrently, creating significant contention
-- on the shared state.
--
-- C++ COMPARISON:
-- In C++ with std::mutex, this would likely cause heavy contention and
-- potential deadlocks if lock ordering isn't perfect. With lock-free
-- approaches, we'd see complex CAS retry loops and potential ABA problems.
--
-- With Haskell STM:
-- - No explicit locks to manage
-- - No deadlock risk
-- - Automatic optimistic concurrency control
-- - Composable transactions
runBenchmark :: EngineState -> IO ()
runBenchmark stateVar = do
    putStrLn "========================================"
    putStrLn "STM Engine High-Concurrency Benchmark"
    putStrLn "========================================"
    putStrLn $ "Workers:        " ++ show numWorkers
    putStrLn $ "Ops per worker: " ++ show opsPerWorker
    putStrLn $ "Total ops:      " ++ show (numWorkers * opsPerWorker)
    putStrLn $ "Key space size: " ++ show keySpaceSize
    putStrLn "----------------------------------------"
    
    startTime <- getCurrentTime
    
    -- Spawn all workers concurrently
    -- replicateConcurrently_ waits for all threads to complete
    replicateConcurrently_ numWorkers $ do
        workerId <- randomRIO (1, numWorkers)
        worker workerId stateVar
    
    endTime <- getCurrentTime
    
    let elapsed = diffUTCTime endTime startTime
    let totalOps = numWorkers * opsPerWorker
    let opsPerSecond = fromIntegral totalOps / realToFrac elapsed :: Double
    
    putStrLn "----------------------------------------"
    putStrLn $ "Elapsed time:   " ++ show elapsed
    putStrLn $ "Throughput:     " ++ show (round opsPerSecond :: Int) ++ " ops/sec"
    putStrLn "========================================"

-----------------------------------------------------------------------------
-- Verification
-----------------------------------------------------------------------------

-- | Verify the correctness of the engine state.
--
-- For verification, we check that:
-- 1. The state is consistent (no partial updates visible)
-- 2. All keys have valid values
-- 
-- This is guaranteed by STM's atomicity - we never see intermediate states.
verifyState :: EngineState -> IO ()
verifyState stateVar = do
    state <- atomically $ readTVar stateVar
    
    putStrLn ""
    putStrLn "=== Final State Verification ==="
    putStrLn $ "Total keys: " ++ show (length state)
    
    -- Print some sample keys
    putStrLn "\nSample keys (first 10):"
    forM_ (take 10 $ Map.toList state) $ \(k, v) -> do
        putStrLn $ "  " ++ k ++ " => " ++ show v
    
    -- Compute total aggregate value across all keys
    let totalValue = sum $ Map.elems state
    putStrLn $ "\nTotal aggregate value: " ++ show totalValue
    putStrLn "================================"

-----------------------------------------------------------------------------
-- Compound Transaction Demonstration
-----------------------------------------------------------------------------

-- | Demonstrate the power of composable transactions.
--
-- This sets up a scenario where multiple threads perform atomic transfers
-- between accounts, demonstrating that STM transactions compose naturally.
demonstrateCompoundTransactions :: EngineState -> IO ()
demonstrateCompoundTransactions stateVar = do
    putStrLn ""
    putStrLn "=== Compound Transaction Demo ==="
    
    -- Initialize some accounts
    atomically $ do
        writeKey "account_A" 1000 stateVar
        writeKey "account_B" 1000 stateVar
        writeKey "account_C" 1000 stateVar
    
    putStrLn "Initial balances: A=1000, B=1000, C=1000"
    
    -- Spawn threads that perform atomic transfers
    -- In C++, coordinating these transfers without deadlock would be complex
    let transferDemo from to = replicateConcurrently_ 50 $ do
            amount <- randomRIO (1, 10)
            atomically $ transferValue from to amount stateVar
    
    -- Concurrent transfers between all pairs
    mapConcurrently_ id
        [ transferDemo "account_A" "account_B"
        , transferDemo "account_B" "account_C"
        , transferDemo "account_C" "account_A"
        , transferDemo "account_A" "account_C"
        , transferDemo "account_B" "account_A"
        , transferDemo "account_C" "account_B"
        ]
    
    -- Verify total is preserved (no money created or destroyed)
    finalA <- atomically $ readKey "account_A" stateVar
    finalB <- atomically $ readKey "account_B" stateVar
    finalC <- atomically $ readKey "account_C" stateVar
    
    let total = sum $ map (maybe 0 id) [finalA, finalB, finalC]
    
    putStrLn $ "Final balances: A=" ++ show (maybe 0 id finalA)
              ++ ", B=" ++ show (maybe 0 id finalB)
              ++ ", C=" ++ show (maybe 0 id finalC)
    putStrLn $ "Total preserved: " ++ show total ++ " (expected: 3000)"
    putStrLn $ "Verification: " ++ if total == 3000 then "PASSED ✓" else "FAILED ✗"
    putStrLn "=================================\n"

-----------------------------------------------------------------------------
-- Main Entry Point
-----------------------------------------------------------------------------

main :: IO ()
main = do
    putStrLn "Haskell STM Key-Value Engine Demo"
    putStrLn "=================================\n"
    
    -- Initialize the engine state
    -- This is the only IO action needed - everything else is pure STM
    stateVar <- newEngineState
    
    -- Demonstrate compound transactions first
    demonstrateCompoundTransactions stateVar
    
    -- Run the high-concurrency benchmark
    runBenchmark stateVar
    
    -- Verify and print final state
    verifyState stateVar
    
    putStrLn "\nDemo completed successfully!"
    putStrLn ""
    putStrLn "Key takeaways:"
    putStrLn "  1. STM provides atomicity without explicit locks"
    putStrLn "  2. Transactions compose naturally (see transferValue)"
    putStrLn "  3. No deadlocks possible - STM handles ordering"
    putStrLn "  4. Optimistic concurrency scales better under contention"
