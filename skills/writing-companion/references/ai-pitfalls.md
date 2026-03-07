# AI Pitfalls in OLAP/Systems Code

## Category 1: Memory Hierarchy Blindness

**AI Pattern**: Generic data structures without cache consideration

**Example**:
```cpp
// AI-generated
std::unordered_map<std::string, std::shared_ptr<State>> table;

// Problems:
// - String as key: heap allocation per lookup
// - shared_ptr: atomic refcount, cache coherence traffic
// - Node-based hash table: pointer chasing, cache misses
```

**What to write about**:
- Why pointer chasing kills performance on modern CPUs
- Arena allocation vs heap allocation
- Small string optimization (SSO) importance

---

## Category 2: Abstraction Overload

**AI Pattern**: Using "modern C++" features that inhibit optimization

**Example**:
```cpp
// AI-generated
virtual void update(State* s, Value v) = 0;  // Virtual dispatch
std::function<void(State&, Value)> updater;  // Type erasure

// Problems:
// - Virtual: prevents inlining, vtable lookup
// - std::function: heap allocation + indirect call
```

**What to write about**:
- CRTP vs virtual functions
- Templates vs type erasure
- When zero-cost abstraction isn't zero-cost

---

## Category 3: Happy Path Myopia

**AI Pattern**: Code that works but fails catastrophically at scale

**Example**:
```cpp
// AI-generated
void aggregate(Block& block) {
    for (auto& row : block) {
        auto state = new AggregateState();  // No limit!
        hash_table[key] = state;
        update(state, row);
    }
}

// Missing:
// - Memory limit check
// - Spill to disk when memory full
// - Exception safety (leak on throw)
// - Two-level conversion for high cardinality
```

**What to write about**:
- Memory budget enforcement
- Graceful degradation strategies
- Exception safety guarantees

---

## Category 4: Concurrency Naivety

**AI Pattern**: "Thread-safe" code that doesn't scale or is subtly broken

**Example**:
```cpp
// AI-generated
class Counter {
    std::mutex mtx;
    int count = 0;
public:
    void increment() {
        std::lock_guard<std::mutex> lock(mtx);
        count++;
    }
};

// Problems:
// - Lock contention kills scalability
// - False sharing if multiple counters in array
// - std::atomic would be better for simple cases
```

**What to write about**:
- Lock-free vs locked structures
- False sharing and cache line padding
- Thread-local storage patterns

---

## Category 5: Algorithm Textbook Direct Translation

**AI Pattern**: "Correct" algorithms that ignore hardware reality

**Example**:
```cpp
// AI-generated quicksort (textbook)
void quicksort(int* arr, int n) {
    if (n <= 1) return;
    int pivot = arr[n/2];
    int* left = new int[n];   // Dynamic allocation per recursion!
    int* right = new int[n];
    // ... partition into left/right
    quicksort(left, left_size);
    quicksort(right, right_size);
}

// Problems:
// - Allocates per recursive call
// - Branch-heavy partition
// - No tail recursion optimization
// - Ignores introsort (O(n²) protection)
```

**What to write about**:
- pdqsort innovations (branch-free partitioning)
- Introsort: quicksort + heapsort fallback
- Pattern detection (already sorted, reverse sorted)

---

## How to Use These in Writing

**Structure for AI Critique Articles**:
1. Show the AI-generated code (innocuous looking)
2. Demonstrate the failure mode (benchmark or reasoning)
3. Explain the underlying hardware/software principle
4. Show production-grade alternative
5. Generalize: what to check when reviewing AI code

**Tone**: Not "AI is bad", but "AI doesn't know what we know about production systems"
