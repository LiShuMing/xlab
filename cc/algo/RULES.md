# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the cc/algo algorithm implementations project.

## Code Style

### C++ Standards

- **C++ Version**: C++17
- **Compiler**: g++ (GCC)
- **Optimization**: `-O0 -g` for debug, `-O2` for release
- **Flags**: `-std=c++17 -fno-omit-frame-pointer`

### Commands

```bash
# Build specific problem
make leetcode_XXX

# Build and run
make run_leetcode_XXX

# Build all algorithms
make algo_all

# Clean
make clean

# Test build system
make test
```

## Project Structure

```
cc/algo/
├── src/
│   ├── leetcode/           # LeetCode solutions
│   ├── lcr/                # LCR (剑指Offer) problems
│   ├── algo/               # Core algorithms
│   ├── hackerrank/         # HackerRank solutions
│   ├── dailyprogrammer/    # Daily Programmer challenges
│   ├── msjd/               # Misc problems
│   ├── linux/              # Linux-specific
│   └── include/
│       └── fwd.h           # Common headers
├── python/                 # Python tests/utilities
├── bin/                    # Compiled binaries
└── Makefile
```

## Naming Conventions

### Files

- **LeetCode**: `leetcode_XXX.cc` (e.g., `leetcode_140.cc`)
- **LCR**: `lcr_XXX.cc` (e.g., `lcr_159.cc`)
- **Algorithms**: `algo_name.cc` (e.g., `algo_sort.cc`)
- **Others**: `hackerrank_name.cc`, `dp_name.cc`

### Code

- **Classes**: `PascalCase` (e.g., `Solution`, `LRUCache`)
- **Methods**: `camelCase` (e.g., `twoSum`, `maxDepth`)
- **Variables**: `snake_case` or `camelCase`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Private members**: `_leading_underscore` or trailing_

## File Template

```cpp
// src/leetcode/leetcode_XXX.cc
// Problem: [Problem Name]
// Link: https://leetcode.com/problems/...

#include "../include/fwd.h"

/**
 * Solution class for LeetCode problem XXX
 *
 * Time Complexity: O(...)
 * Space Complexity: O(...)
 */
class Solution {
public:
    ReturnType methodName(Parameters) {
        // Implementation
    }
};

// Test harness
int main() {
    Solution sol;
    // Test cases
    return 0;
}
```

## Include Header

All source files must include:

```cpp
#include "../include/fwd.h"
```

The `fwd.h` header provides:
- Standard library includes
- Common type aliases
- Utility functions

## Complexity Documentation

Every solution must document:

```cpp
/**
 * Problem: [Name]
 * Link: [URL]
 *
 * Approach:
 * [Brief description of the algorithm]
 *
 * Time Complexity: O(...)
 * Space Complexity: O(...)
 */
```

## Algorithm Categories

### Sorting (`src/algo/algo_sort.cc`)
- Comparison sorts: quicksort, mergesort, heapsort
- Linear sorts: counting, radix, bucket
- Hybrid sorts: Timsort, introsort

### Trees (`src/algo/algo_binary_tree.cc`)
- Traversals: inorder, preorder, postorder, level order
- Operations: insert, delete, search, validate
- Advanced: serialization, lowest common ancestor

### Graphs (`src/algo/algo_graph.cc`)
- Traversals: BFS, DFS
- Shortest path: Dijkstra, Bellman-Ford, Floyd-Warshall
- MST: Prim, Kruskal
- Topological sort

### Hash Tables (`src/algo/algo_hash_table.cc`)
- Implementation variants
- Collision resolution
- Resize strategies

### Caches (`src/algo/algo_cache.cc`)
- LRU (Least Recently Used)
- LFU (Least Frequently Used)
- FIFO, LIFO variants

### Concurrent (`src/algo/algo_lock_free*.cc`)
- Lock-free queues
- Memory ordering
- ABA problem solutions

## Testing Requirements

### C++ Test Harness

Every solution file must have a `main()` function:

```cpp
int main() {
    Solution sol;

    // Test case 1
    InputType input1 = ...;
    auto result1 = sol.method(input1);
    cout << "Test 1: " << (check(result1) ? "PASS" : "FAIL") << endl;

    // Test case 2
    // ...

    return 0;
}
```

### Python Tests

Add Python tests in `python/test/` when appropriate:

```python
# python/test/test_leetcode.py
def test_leetcode_140():
    # Test logic
    assert solution.word_break(s, word_dict) == expected
```

## Build System

### Makefile Targets

```makefile
# Build targets
leetcode_XXX      -> bin/leetcode_XXX
lcr_XXX           -> bin/lcr_XXX
algo_NAME         -> bin/algo_NAME
hackerrank_NAME   -> bin/hackerrank_NAME

# Run targets
run_leetcode_XXX  -> build and execute
run_lcr_XXX       -> build and execute
run_algo_NAME     -> build and execute
```

### Build Flags

```makefile
# Debug (default)
CXXFLAGS = -std=c++17 -O0 -fno-omit-frame-pointer -g

# Release
CXXFLAGS = -std=c++17 -O2
```

## Git Workflow

### Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New solution or algorithm
- `fix`: Bug fix in existing solution
- `docs`: Documentation updates
- `refactor`: Code restructuring
- `test`: Test additions

Examples:
```
feat: add solution for LeetCode 300 (LIS)
fix: correct boundary check in binary search
docs: add complexity analysis for algo_sort
```

## Common Patterns

### Two Pointers

```cpp
int left = 0, right = n - 1;
while (left < right) {
    // Process
    if (condition) left++;
    else right--;
}
```

### Sliding Window

```cpp
int left = 0;
for (int right = 0; right < n; right++) {
    // Expand window
    window.add(arr[right]);

    // Shrink if needed
    while (need_shrink()) {
        window.remove(arr[left++]);
    }
}
```

### DFS/BFS

```cpp
// DFS recursive
void dfs(node) {
    if (!node) return;
    visit(node);
    dfs(node->left);
    dfs(node->right);
}

// BFS iterative
void bfs(start) {
    queue<Node*> q;
    q.push(start);
    while (!q.empty()) {
        auto node = q.front(); q.pop();
        visit(node);
        for (auto neighbor : node->neighbors) {
            q.push(neighbor);
        }
    }
}
```

### Dynamic Programming

```cpp
// Bottom-up
vector<int> dp(n + 1);
dp[0] = base_case;
for (int i = 1; i <= n; i++) {
    dp[i] = transition(dp[i-1], ...);
}
return dp[n];

// Space optimized
int prev = base_case, curr;
for (int i = 1; i <= n; i++) {
    curr = transition(prev, ...);
    prev = curr;
}
return curr;
```

## Performance Guidelines

### Time Optimization

- Use hash maps for O(1) lookup: `unordered_map` / `unordered_set`
- Prefer iterative over recursive when stack depth > ~1000
- Early termination when answer found
- Avoid unnecessary copies (use references)

### Space Optimization

- In-place modification when allowed
- Reuse data structures
- Bit manipulation for boolean arrays
- Rolling array for DP

### Code Optimization

```cpp
// Good - Reserve capacity
vector<int> result;
result.reserve(n);

// Good - Reference to avoid copy
for (const auto& item : container) { }

// Good - Move semantics
result.push_back(std::move(item));
```

## Prohibited Patterns

1. **No magic numbers** - Use named constants
2. **No global variables** - Pass as parameters
3. **No recursion without base case** - Always terminate
4. **No undefined behavior** - Check array bounds
5. **No memory leaks** - Use smart pointers if allocating

## Documentation

### File Header

```cpp
/**
 * Problem XXX: [Problem Title]
 * Difficulty: [Easy/Medium/Hard]
 *
 * Description:
 * [Brief problem statement]
 *
 * Examples:
 * Input: ...
 * Output: ...
 *
 * Constraints:
 * - constraint 1
 * - constraint 2
 *
 * Tags: [array, dp, graph, etc.]
 */
```

### Algorithm Explanation

```cpp
/**
 * Approach: [Algorithm Name]
 *
 * Intuition:
 * [Why this approach works]
 *
 * Algorithm:
 * 1. Step one
 * 2. Step two
 * 3. Step three
 *
 * Proof of Correctness:
 * [Why the algorithm is correct]
 *
 * Time Complexity: O(...)
 * Space Complexity: O(...)
 */
```

## IDE Configuration

Recommended `.vscode/settings.json`:

```json
{
    "C_Cpp.default.cppStandard": "c++17",
    "C_Cpp.default.intelliSenseMode": "linux-gcc-x64",
    "files.associations": {
        "*.cc": "cpp"
    }
}
```

## Resources

- [LeetCode](https://leetcode.com/)
- [GeeksforGeeks](https://www.geeksforgeeks.org/)
- [HackerRank](https://www.hackerrank.com/)
- [CP-Algorithms](https://cp-algorithms.com/)
