{-# LANGUAGE BangPatterns #-}

-----------------------------------------------------------------------------
-- |
-- Module      : Engine
-- Description : High-Performance STM-based Key-Value Store and Aggregation Engine
-- 
-- This module demonstrates Haskell's Software Transactional Memory (STM) as a
-- superior alternative to traditional C++ lock-free programming and fine-grained
-- mutexes. Key advantages:
-- 
-- 1. COMPOSABILITY: STM transactions can be composed using '>>=' (bind) or 'do'
--    notation. In C++, combining two lock-free operations atomically requires
--    complex custom code or coarse-grained locks.
--
-- 2. ZERO DEADLOCKS: STM automatically handles lock ordering and retry logic.
--    Unlike C++ mutexes where acquire(A); acquire(B) vs acquire(B); acquire(A)
--    causes deadlocks, STM detects conflicts and retries transparently.
--
-- 3. OPTIMISTIC CONCURRENCY: STM uses optimistic concurrency control - threads
--    execute speculatively and only commit if no conflicts occurred. This
--    eliminates contention compared to pessimistic locking.
--
-----------------------------------------------------------------------------

module Engine
    ( -- * Core Types
      Key
    , Value
    , State
    , EngineState
    , Operation(..)
      -- * STM Operations
    , applyOp
    , readKey
    , writeKey
    , incrementKey
    , transferValue
      -- * State Management
    , emptyState
    , newEngineState
    ) where

import           Control.Concurrent.STM
import           Data.Map.Strict        (Map)
import qualified Data.Map.Strict        as Map

-----------------------------------------------------------------------------
-- Core Data Structures
-----------------------------------------------------------------------------

-- | Keys are simple Strings for this engine.
type Key = String

-- | Values are integers (suitable for both storage and atomic aggregation).
type Value = Int

-- | The core state is an immutable Map stored in a TVar.
-- 
-- INVARIANT: Unlike C++ where we'd need std::mutex per bucket or fine-grained
-- locks, Haskell's STM with TVar provides atomic snapshots of the entire Map.
-- When a transaction commits, the entire update is atomic and consistent.
type State = Map Key Value

-- | EngineState wraps the TVar containing our state.
-- 
-- C++ ANALOGY: This is similar to std::atomic<std::unordered_map<Key,Value>>
-- but with composition capabilities. In C++, atomic<container> doesn't exist
-- because there's no way to compose multiple atomic operations on it atomically.
-- STM solves this through the STM monad which logs all reads/writes and validates
-- atomicity at commit time.
type EngineState = TVar State

-- | Operations supported by the Key-Value engine.
--
-- These ADTs represent pure descriptions of operations. The actual execution
-- happens inside the STM monad, allowing atomic composition of multiple
-- operations.
data Operation
    = Read  !Key                    -- ^ Read the value at a key (returns Maybe Value)
    | Write !Key !Value             -- ^ Write a value at a key
    | Increment !Key !Value         -- ^ Atomically increment a key's value
    deriving (Show, Eq)

-----------------------------------------------------------------------------
-- Pure State Transitions (Separated from STM/IO)
--
-- These functions are pure and have no IO or STM. They represent the 
-- business logic of state transformation, making them testable and
-- deterministic.
-----------------------------------------------------------------------------

-- | The empty state (empty Map).
emptyState :: State
emptyState = Map.empty

-- | Create a new engine state in IO (initialization only).
newEngineState :: IO EngineState
newEngineState = newTVarIO emptyState

-----------------------------------------------------------------------------
-- STM Operations
--
-- These operations run inside the STM monad, giving us atomicity and
-- composability for free. Contrast this with C++ where each function
-- would need to manage its own locking strategy, and composing two
-- atomic operations requires exposing lock internals.
-----------------------------------------------------------------------------

-- | Read a key's value from the state.
--
-- STM SEMANTICS: This creates a read entry in the transaction log.
-- If another thread modifies this key before we commit, the transaction
-- will automatically retry.
readKey :: Key -> EngineState -> STM (Maybe Value)
readKey key stateVar = do
    state <- readTVar stateVar
    pure $ Map.lookup key state

-- | Write a value to a key.
--
-- STM SEMANTICS: This creates a write entry in the transaction log.
-- The actual write only becomes visible to other threads when the
-- transaction successfully commits.
writeKey :: Key -> Value -> EngineState -> STM ()
writeKey key value stateVar = do
    state <- readTVar stateVar
    let !newState = Map.insert key value state
    writeTVar stateVar newState

-- | Atomically increment a key's value.
--
-- If the key doesn't exist, it's created with the increment value.
-- This is a classic read-modify-write operation that in C++ would require
-- either a mutex or a CAS loop. In STM, it's just a composed transaction.
incrementKey :: Key -> Value -> EngineState -> STM ()
incrementKey key delta stateVar = do
    state <- readTVar stateVar
    let current = Map.findWithDefault 0 key state
    let !newValue = current + delta
    let !newState = Map.insert key newValue state
    writeTVar stateVar newState

-- | Transfer value from one key to another atomically.
--
-- This demonstrates STM's COMPOSABILITY - a key advantage over C++ locking.
-- In C++, to atomically transfer between two accounts, we'd need to:
--   1. Acquire locks in a consistent global order (error-prone)
--   2. Or use a global lock (coarse-grained, low concurrency)
--   3. Or implement complex lock-free CAS retry loops
--
-- In Haskell STM, we simply compose two reads and two writes in one
-- transaction. The STM runtime guarantees atomicity and handles all
-- retry logic automatically.
transferValue :: Key -> Key -> Value -> EngineState -> STM ()
transferValue fromKey toKey amount stateVar = do
    -- Read source balance
    state <- readTVar stateVar
    let fromBalance = Map.findWithDefault 0 fromKey state
    
    -- Check for sufficient funds (business logic)
    -- In a real system, we might use 'check' to retry until funds available
    -- For this engine, we just clamp to zero
    let actualTransfer = min amount fromBalance
    
    -- Compute new balances
    let newFromBalance = fromBalance - actualTransfer
    let toBalance = Map.findWithDefault 0 toKey state
    let !newToBalance = toBalance + actualTransfer
    
    -- Write both updates atomically
    let !newState = Map.insert toKey newToBalance 
                  $ Map.insert fromKey newFromBalance state
    writeTVar stateVar newState

-- | Apply a single operation to the engine state.
--
-- This is the main entry point for executing operations. It returns the
-- result wrapped in STM, allowing callers to compose multiple operations
-- into larger atomic transactions.
applyOp :: Operation -> EngineState -> STM (Maybe Value)
applyOp (Read key) stateVar = readKey key stateVar
applyOp (Write key value) stateVar = do
    writeKey key value stateVar
    pure Nothing
applyOp (Increment key delta) stateVar = do
    incrementKey key delta stateVar
    pure Nothing

-----------------------------------------------------------------------------
-- Composed Transaction Examples
--
-- These show how STM transactions compose naturally, something that is
-- notoriously difficult in C++ concurrent programming.
-----------------------------------------------------------------------------

-- Example of a compound transaction that would be very difficult in C++:
-- atomically transfer between two keys, reading the new balance of both
--
-- compoundTransfer :: Key -> Key -> Value -> EngineState -> STM (Maybe Value, Maybe Value)
-- compoundTransfer from to amount stateVar = do
--     transferValue from to amount stateVar
--     newFrom <- readKey from stateVar
--     newTo <- readKey to stateVar
--     pure (newFrom, newTo)
-- 
-- In C++, making this atomic would require exposing internal lock details
-- or using a global lock. In Haskell, it's just function composition.
