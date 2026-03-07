# Technical Writing Patterns

## Pattern 1: The Comparative Deep-Dive

Structure when comparing implementations (e.g., ClickHouse vs StarRocks aggregation):

```
1. Shared Problem Statement
   "Both engines face the same physical constraint..."

2. Divergent Philosophies
   - ClickHouse: Conservative, explicit, predictable
   - StarRocks: Aggressive, adaptive, cloud-native

3. Implementation Comparison (table format)
   | Aspect | ClickHouse | StarRocks | Trade-off Analysis |

4. Production Scenarios
   - When CH approach wins
   - When SR approach wins

5. Personal Stance
   "As someone maintaining..."
```

## Pattern 2: The AI Critique

When analyzing AI-generated code or discussing AI tooling:

```
1. The Promise (What AI claims to do)
2. The Blind Spot (What AI systematically misses)
   - Memory hierarchy ignorance
   - Defaulting to high-level abstractions
   - Missing failure modes

3. Concrete Example
   Show AI-generated code vs production-grade alternative

4. Human Reviewer's Role
   What to check, what to automate, what requires judgment

5. Future Outlook
   Where AI might actually help vs where human expertise remains essential
```

## Pattern 3: The Performance Regression War Story

Debugging narrative structure:

```
1. The Symptom
   "Query latency went from 50ms to 500ms after release..."

2. Initial Hypotheses (all wrong)
   What we thought first, why we were wrong

3. The Dig
   Tools used (perf, flamegraph, eBPF), dead ends

4. The Root Cause
   Often something seemingly unrelated

5. The Fix (and its trade-offs)

6. The Prevention
   What monitoring/code review could have caught this
```

## Pattern 4: Architecture Decision Record

When documenting major design choices:

```
Context: What constraints and requirements we faced
Decision: What we chose
Consequences: Positive and negative (be honest)
Alternatives Considered: Why rejected
Lessons: What we'd do differently
```

## Pattern 5: The SIMD/Optimization Breakdown

When explaining low-level optimizations:

```
1. The Naive Approach
   Simple, readable, slow

2. The Bottleneck Analysis
   Cache miss rate, branch prediction failures, etc.

3. The Optimized Approach
   Show intrinsics or compiler-generated assembly

4. The Numbers
   Before/after benchmarks with hardware specs

5. The Limits
   When does this stop working? (Amdahl's Law, memory bandwidth wall)
```

## Code Presentation Style

### For Source Analysis
```cpp
// ClickHouse/src/Interpreters/Aggregator.cpp:470
// Key insight: Arena allocation is O(1) because...
char* Arena::alloc(size_t size) {
    if (unlikely(head_pos + size > head_end))
        return allocSlow(size);  // Slow path clearly marked
    // Fast path: just pointer arithmetic
    return head_pos += size;
}
```

### For Comparison Tables
```
| Metric | Generic HashMap | ClickHouse Arena | Speedup |
|--------|----------------|------------------|---------|
| Allocation | O(log n) heap search | O(1) pointer bump | 10-100x |
| Cache locality | Pointer chasing | Sequential | 3-5x |
| Thread safety | Lock/mutex | Thread-local | No contention |
```

## Tone Markers

Use these verbal tics sparingly, for emphasis:

- "The thing is..." (before stating uncomfortable truth)
- "Here's the rub..." (before identifying core trade-off)
- "In production..." (grounding theory in reality)
- "As of [date]..." (acknowledging changing landscape)

## Forbidden Phrases in Technical Writing

- "Simply put" → Just put it, simply
- "It's easy to see" → If it's easy, show it
- "Best practice" → Say "common approach" and explain trade-offs
- "Modern" (without defining vs what) → Be specific: "post-2015", "AVX-512 era"
- "Scalable" (without defining to what scale) → Give numbers

## Opening Hooks That Work

- "I spent three days debugging a 2x performance regression that turned out to be..."
- "Most explanations of [X] miss the actual bottleneck..."
- "ClickHouse and StarRocks both claim to be fast. Here's where they make different bets..."
- "AI-generated code for [task] looks correct. Here's why it will fail in production..."

## Closing Arcs

- Return to opening problem, show how understanding evolved
- Open question for the community
- Long-term prediction ("In five years...")
- Connection to broader engineering principles
