# TO-FIX

## Current Limitations

- [ ] Parser only supports basic SELECT statements
  - Missing: INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE
  - Missing: JOIN operations
  - Missing: Subqueries
  - Missing: Aggregate functions (COUNT, SUM, AVG, etc.)

- [ ] Analyzer is incomplete
  - Needs proper type checking
  - Needs table/column resolution from catalog
  - Needs validation of expressions

- [ ] Planner produces simple plans only
  - No join ordering optimization
  - No index selection
  - No predicate pushdown

- [ ] Executor lacks operators
  - Missing: Hash Join, Nested Loop Join
  - Missing: Hash Aggregate, Sort Aggregate
  - Missing: Sort operator
  - Missing: Top/Limit operator

- [ ] Storage needs implementation
  - Segment persistence not complete
  - WAL not implemented
  - No recovery protocol
  - Index is stub only

---

# FIXED

(No completed fixes yet)

---

# NOTES

## Design Decisions

### Column-Oriented Storage
- Chosen for analytical query performance
- Better compression ratios
- Vectorized execution potential

### Async I/O
- Tokio for runtime
- Non-blocking operations for concurrent queries
- Scalable to many connections

### Delete Vectors
- Roaring bitmaps for efficient compression
- Soft deletes for MVCC support
- Lazy cleanup during compaction

## Future Improvements

### Query Processing
- [ ] Cost-based optimizer with statistics
- [ ] Vectorized execution (columnar batches)
- [ ] Parallel query execution
- [ ] Query caching

### Storage
- [ ] LSM-tree integration for writes
- [ ] Tiered storage (hot/warm/cold)
- [ ] Replication support
- [ ] Cloud storage backends (S3, GCS)

### SQL Support
- [ ] Full SQL-92 compliance
- [ ] Window functions
- [ ] CTEs (Common Table Expressions)
- [ ] Prepared statements

### Performance
- [ ] LLVM code generation
- [ ] Adaptive query execution
- [ ] Automatic indexing suggestions
- [ ] Workload-based optimization

## Research Areas

- Learned indexes (e.g., RMI)
- GPU acceleration for queries
- Distributed transaction protocols
- Columnar compression algorithms
