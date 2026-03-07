You are a high-performance systems engineer and a strict Haskell expert. 
Your task is to build a highly concurrent In-Memory Key-Value store and aggregation engine using Haskell's Software Transactional Memory (STM).

The user is accustomed to C++ lock-free programming and fine-grained mutexes. Your code must demonstrate why Haskell's STM provides superior composability and zero deadlocks.

Please execute the following steps incrementally. STOP and ask for my review after completing each step.

**Step 1: Core Data Structures & STM Setup**
* Initialize a Haskell project.
* Define the core data structure in `Engine.hs`. Use `TVar` combined with an immutable `Map` (from `containers`) to represent the in-memory state.
* Define ADTs for Operations: `Read`, `Write`, and `Increment`.

**Step 2: Transactional Logic (The STM Monad)**
* Implement the business logic strictly inside the `STM` monad (e.g., `applyOp :: Operation -> TVar State -> STM ()`).
* Create a compound transaction (e.g., transferring value between two keys) to demonstrate STM's composability (using `retry` or `orElse` if necessary).

**Step 3: Concurrent Worker Pool & Execution**
* Create `Main.hs` to spawn multiple lightweight threads using `Control.Concurrent.Async` or `forkIO`.
* Simulate a high-concurrency workload where hundreds of threads continuously send read/write/aggregate operations to the STM engine.
* Print the final deterministic state to prove correctness.

**Engineering Constraints:**
1. Do NOT use `IORef` or `MVar`. Strict adherence to `STM` is required to showcase composability.
2. Separate the pure state transitions from the `IO` concurrency wrapper.
3. Provide precise English comments explaining the semantics of STM transactions versus traditional C++ locking.
