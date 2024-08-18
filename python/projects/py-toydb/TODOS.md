# TO-FIX

## Known Issues

(None currently tracked)

## Potential Improvements

### Performance
- [ ] Add indexing for faster queries on large datasets
- [ ] Implement query result caching
- [ ] Optimize query evaluation order
- [ ] Add bulk operations for better performance

### Features
- [ ] Add pagination for query results
- [ ] Support for async storage backends
- [ ] Add more storage backends (YAML, MessagePack, SQLite)
- [ ] Query result sorting options
- [ ] Aggregation operations (sum, avg, count, group_by)
- [ ] Full-text search
- [ ] Schema validation
- [ ] Data migration tools

### API
- [ ] Consider fluent update API
  ```python
  db.update(where('status') == 'pending').set({'status': 'active'})
  ```
- [ ] Add upsert operation (update or insert)
- [ ] Batch operations with better error handling

### Documentation
- [ ] Add more examples
- [ ] Create tutorial/guide
- [ ] Add performance comparison with other databases
- [ ] Document query optimization tips

---

# FIXED

- ✅ Type hints added for all public APIs
- ✅ Poetry configuration for modern Python packaging
- ✅ pytest configuration with coverage
- ✅ Context manager support for proper resource cleanup
- ✅ Middleware system for extensible storage

---

# NOTES

## Design Decisions

### Why Document-Oriented?
- Flexibility in data structure
- Natural fit for Python dicts
- No schema migrations needed
- Good for prototyping

### Why Pure Python?
- No compilation needed
- Easy to install
- Easy to understand/modify
- Portable across platforms

### Storage Model
- Simple dict-based storage
- Easy to understand and debug
- Human-readable JSON format
- Pluggable storage backends

## Performance Considerations

ToyDB is optimized for:
- Simplicity over speed
- Small to medium datasets (< 100k docs)
- Read-heavy workloads
- Prototyping and learning

For production use with large datasets, consider:
- SQLite for local storage
- PostgreSQL/MongoDB for server databases

## Architecture Notes

### Query Evaluation
- Queries are evaluated by iterating all documents
- No indexing currently implemented
- Short-circuit evaluation for logical operators

### Storage Interface
- Simple read/write/close contract
- Storage handles serialization
- Middleware wraps storage for extensibility

### Thread Safety
- Storage implementations should be thread-safe
- ToyDB instance methods are not thread-safe
- Use separate instances per thread
