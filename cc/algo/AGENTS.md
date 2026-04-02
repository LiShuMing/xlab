# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the cc/algo algorithm implementations project.

## Project Architecture

cc/algo is a collection of algorithm implementations, LeetCode solutions, and coding interview problems in C++.

```
cc/algo/
├── src/
│   ├── leetcode/           # LeetCode problem solutions (150+ problems)
│   │   └── leetcode_*.cc   # Individual problem files
│   ├── lcr/                # LCR (剑指Offer/LintCode) problems
│   │   └── lcr_*.cc        # LCR problem files
│   ├── algo/               # Core algorithm implementations
│   │   ├── algo_sort.cc    # Sorting algorithms
│   │   ├── algo_binary_tree.cc  # Binary tree operations
│   │   ├── algo_graph.cc   # Graph algorithms
│   │   ├── algo_hash_table.cc   # Hash table implementations
│   │   ├── algo_cache.cc   # Cache algorithms (LRU, LFU)
│   │   ├── algo_lock_free_queue.cc  # Lock-free data structures
│   │   └── ...
│   ├── hackerrank/         # HackerRank solutions
│   ├── dailyprogrammer/    # Reddit Daily Programmer challenges
│   ├── msjd/               # Miscellaneous JD problems
│   ├── linux/              # Linux-specific algorithms
│   └── include/
│       └── fwd.h           # Common headers and utilities
├── python/                 # Python test utilities
│   ├── test/               # pytest test suite
│   └── script/             # Helper scripts
├── bin/                    # Compiled binaries
└── Makefile               # Build system
```

## Key Components

### LeetCode Solutions (`src/leetcode/`)
- Individual files for each problem (e.g., `leetcode_140.cc`)
- Each file contains a `Solution` class with the solution
- Main function for testing the solution
- Uses common headers from `include/fwd.h`

### LCR Problems (`src/lcr/`)
- 剑指Offer (Chinese interview problems)
- LintCode problem solutions
- Similar structure to LeetCode files

### Algorithm Implementations (`src/algo/`)
Core algorithms organized by topic:
- **Sorting**: Various sorting implementations
- **Trees**: Binary tree operations, traversals
- **Graphs**: BFS, DFS, shortest path, etc.
- **Hash Tables**: Custom hash map implementations
- **Caches**: LRU, LFU cache implementations
- **Concurrent**: Lock-free data structures
- **Scheduling**: Task scheduling algorithms

### Build System
- Uses GNU Make
- Pattern rules for building specific problems
- Output to `bin/` directory

## Dependencies

- **g++** - C++ compiler
- **C++17** - Language standard
- **Python 3** - For testing utilities
- **pytest** - Python testing framework

## Building and Testing

```bash
# Build a specific LeetCode problem
make leetcode_140

# Build and run
make run_leetcode_140

# Build with custom arguments
make run_leetcode_140 ARGS="custom input"

# Build LCR problem
make lcr_159
make run_lcr_159

# Build algorithm implementation
make algo_sort
make run_algo_sort

# Build all algorithms
make algo_all

# Test build system
make test

# Clean binaries
make clean
```

## Coding Standards

### File Structure

```cpp
// File header: src/leetcode/leetcode_XXX.cc
#include "../include/fwd.h"  // Common headers

// Solution class
class Solution {
public:
    // Method signature matching LeetCode
    ReturnType methodName(Parameters) {
        // Implementation
    }
};

// Test main function
int main() {
    Solution solution;
    // Test cases
    auto result = solution.methodName(args);
    // Output results
    return 0;
}
```

### Include Header

All files should include the forward header:

```cpp
#include "../include/fwd.h"
```

This provides:
- Standard library headers (iostream, vector, string, etc.)
- Common utilities
- Using declarations

### Naming Conventions

- **Files**: `leetcode_XXX.cc`, `lcr_XXX.cc`, `algo_name.cc`
- **Classes**: `PascalCase` (e.g., `Solution`, `LRUCache`)
- **Methods**: `camelCase` (e.g., `wordBreak`, `maxProfit`)
- **Variables**: `snake_case` or `camelCase`

### Solution Class Pattern

```cpp
class Solution {
public:
    // Primary solution method
    vector<int> twoSum(vector<int>& nums, int target) {
        // Implementation
    }

    // Helper methods (private if needed)
private:
    void helper() { }
};
```

## Common Tasks

### Adding a LeetCode Solution

1. Create file: `src/leetcode/leetcode_XXX.cc`
2. Include `fwd.h`
3. Implement `Solution` class
4. Add test cases in `main()`
5. Build: `make leetcode_XXX`
6. Run: `make run_leetcode_XXX`

```cpp
// leetcode_1.cc - Two Sum
#include "../include/fwd.h"

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> seen;
        for (int i = 0; i < nums.size(); i++) {
            int complement = target - nums[i];
            if (seen.count(complement)) {
                return {seen[complement], i};
            }
            seen[nums[i]] = i;
        }
        return {};
    }
};

int main() {
    Solution sol;
    vector<int> nums = {2, 7, 11, 15};
    int target = 9;
    auto result = sol.twoSum(nums, target);
    // Print result
    for (int x : result) cout << x << " ";
    cout << endl;
    return 0;
}
```

### Adding an Algorithm Implementation

1. Create file: `src/algo/algo_name.cc`
2. Include `fwd.h`
3. Implement algorithm with clear comments
4. Add test cases
5. Document complexity

```cpp
// algo_name.cc
#include "../include/fwd.h"

/**
 * Algorithm: Binary Search
 * Time: O(log n)
 * Space: O(1)
 */
int binary_search(vector<int>& arr, int target) {
    int left = 0, right = arr.size() - 1;
    while (left <= right) {
        int mid = left + (right - left) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target) left = mid + 1;
        else right = mid - 1;
    }
    return -1;
}

int main() {
    vector<int> arr = {1, 2, 3, 4, 5};
    cout << binary_search(arr, 3) << endl;  // 2
    return 0;
}
```

## Complexity Documentation

Each solution should document:
- **Time Complexity**: Big-O notation
- **Space Complexity**: Big-O notation
- **Approach**: Brief explanation

```cpp
/**
 * Problem: Word Break II
 * Link: https://leetcode.com/problems/word-break-ii/
 *
 * Approach: DP + Backtracking
 * - Use DP to check if string can be segmented
 * - Use backtracking to generate all valid sentences
 *
 * Time: O(n^2 + 2^n) where n is string length
 * Space: O(n^2) for DP table + O(2^n) for results
 */
```

## Prohibited Actions

1. **DO NOT** commit compiled binaries
2. **DO NOT** modify `fwd.h` without careful consideration
3. **DO NOT** use platform-specific code without guards
4. **DO NOT** skip test cases in main()
5. **DO NOT** use `using namespace std;` in headers

## Testing with Python

```bash
cd python
pytest test/test_leetcode.py -v
```

## Performance Guidelines

- Prefer iterative over recursive for deep recursion
- Use `reserve()` for vectors when size is known
- Consider memory usage for large inputs
- Profile if unsure about performance

## Reading Order for New Contributors

1. `include/fwd.h` - Common utilities
2. `src/algo/algo_basic.cc` - Basic algorithms
3. `src/leetcode/leetcode_1.cc` - Simple example
4. `Makefile` - Build system

## Communication Style

- Be concise in code comments
- Include problem link in file header
- Explain complex algorithms briefly
- Show example input/output
