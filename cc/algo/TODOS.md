# TO-FIX

## Known Issues

- [ ] Some LeetCode solutions lack comprehensive test cases
- [ ] Complexity analysis missing in some older files
- [ ] Could add more edge case handling
- [ ] Some solutions could be optimized further

## Potential Improvements

### New Problems to Add
- [ ] More LeetCode hard problems (target: 50 hard)
- [ ] System design problems
- [ ] Multi-threading problems
- [ ] Database query problems

### Algorithm Enhancements
- [ ] Add AVL tree implementation
- [ ] Add Red-Black tree
- [ ] Add B-Tree for databases
- [ ] Add LSM tree basics
- [ ] Add Bloom filter
- [ ] Add Count-Min sketch
- [ ] Add HyperLogLog

### Testing
- [ ] Add automated test runner
- [ ] Add performance benchmarks
- [ ] Add fuzz testing
- [ ] Add property-based tests

### Documentation
- [ ] Add complexity cheat sheet
- [ ] Add algorithm visualizations
- [ ] Add video explanations
- [ ] Add interview tips

---

# FIXED

- ✅ Initial project structure established
- ✅ Makefile with comprehensive build rules
- ✅ 150+ LeetCode solutions
- ✅ 100+ LCR solutions
- ✅ 20+ core algorithm implementations
- ✅ Python test utilities

---

# NOTES

## Study Path Recommendations

### Beginner
1. Start with Easy array problems
2. Learn basic sorting
3. Practice string manipulation
4. Study simple tree traversals

### Intermediate
1. Master two pointers and sliding window
2. Learn BFS/DFS thoroughly
3. Practice dynamic programming patterns
4. Understand binary search variants

### Advanced
1. Advanced DP (bitmask, interval, tree)
2. Graph algorithms (shortest path, MST)
3. Advanced data structures (segment tree, trie)
4. System design problems

## Common Interview Patterns

| Pattern | Frequency | Problems |
|---------|-----------|----------|
| Two Pointers | High | 15, 11, 42 |
| Sliding Window | High | 3, 76, 209 |
| Binary Search | High | 33, 153, 34 |
| BFS | High | 102, 200, 127 |
| DFS | High | 98, 104, 226 |
| DP | High | 70, 198, 300 |
| Topological Sort | Medium | 207, 210 |
| Union Find | Medium | 200, 547 |
| Trie | Medium | 208, 212 |
| Segment Tree | Low | 307, 315 |

## Performance Tips

- Sorting: O(n log n) is usually acceptable
- Searching: Aim for O(log n) or O(1)
- DP: Space can often be optimized from O(n²) to O(n)
- Graphs: Consider adjacency list vs matrix
- Strings: KMP for pattern matching avoids backtracking

## Resources

- LeetCode discussion forums
- NeetCode roadmap
- Blind 75 list
- Sean Prasad's patterns
