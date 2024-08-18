# TO-FIX

## Known Issues

### Current Limitations
- [ ] Not all TPC-DS queries implemented (35/99)
- [ ] No async/concurrent test execution framework
- [ ] Limited error reporting in benchmarks
- [ ] No benchmark result persistence
- [ ] Manual configuration for each environment
- [ ] No Docker support for test isolation
- [ ] Limited test coverage for edge cases
- [ ] No performance regression detection

### Technical Debt
- [ ] Some utility functions could be more generic
- [ ] Error messages could be more descriptive
- [ ] Need better logging configuration
- [ ] Test cleanup could be more robust

## Planned Improvements

### Testing
- [ ] Complete TPC-DS query set (99 queries)
- [ ] Complete TPC-H query set (22 queries)
- [ ] Add more SSB queries
- [ ] Add concurrency stress tests
- [ ] Add performance regression tests
- [ ] Add chaos engineering tests
- [ ] Add data correctness validation

### Benchmarking
- [ ] Benchmark result storage (database or files)
- [ ] Historical performance tracking
- [ ] Performance comparison tools
- [ ] Graphical benchmark reports
- [ ] CI/CD integration for performance gates

### Framework
- [ ] Kotlin coroutines support for async tests
- [ ] Parallel test execution
- [ ] Better test isolation
- [ ] Docker Compose integration
- [ ] Kubernetes support
- [ ] Test data generation utilities

### Developer Experience
- [ ] IDE plugin for test running
- [ ] Live reload for tests
- [ ] Better debugging support
- [ ] Test result visualization
- [ ] Automated test documentation

### Integrations
- [ ] Jenkins/CI plugin
- [ ] Grafana dashboards
- [ ] Prometheus metrics
- [ ] Slack notifications
- [ ] JIRA integration for test tracking

### Documentation
- [ ] API documentation (KDoc)
- [ ] Architecture decision records
- [ ] Troubleshooting guide
- [ ] Contributing guide
- [ ] Video tutorials

---

# FIXED

- ✅ Multi-module Gradle project structure
- ✅ Core testing framework (Suite, MVSuite)
- ✅ Connection pooling
- ✅ Configuration management (YAML)
- ✅ TPC-DS partial query set (35 queries)
- ✅ TPC-H benchmark suite
- ✅ SSB benchmark suite
- ✅ Custom benchmark cases
- ✅ Materialized view testing support
- ✅ SQL execution utilities
- ✅ Basic integration tests

---

# NOTES

## Design Decisions

### Why Kotlin?
- Modern language features
- Null safety
- Coroutines support (future use)
- Interoperable with Java
- Concise syntax

### Why Gradle?
- Multi-module support
- Kotlin DSL
- Great IDE integration
- Flexible dependency management

### Why Multi-Module?
- Separation of concerns
- Framework can be used standalone
- Tests don't affect framework
- Benchmarks are independent

## Testing Philosophy

### Integration Testing
- Test against real database
- Validate actual query behavior
- Check MV rewrite correctness
- Measure real performance

### Benchmarking
- Consistent test data
- Warmup before measurement
- Multiple iterations
- Statistical analysis

## Performance Targets

### TPC-DS
- Query time < 10s for SF=1
- MV rewrite benefit > 50% for applicable queries

### TPC-H
- Refresh time < 30s for SF=1
- Concurrent refresh scales linearly

### SSB
- Query time < 5s for SF=1
- MV rewrite benefit > 70%

## Resources

### StarRocks
- Documentation: https://docs.starrocks.io/
- GitHub: https://github.com/StarRocks/starrocks

### TPC Benchmarks
- TPC-DS: http://www.tpc.org/tpcds/
- TPC-H: http://www.tpc.org/tpch/
- SSB: Star Schema Benchmark (modified from TPC-H)

### Kotlin
- Documentation: https://kotlinlang.org/docs/
- Coroutines: https://kotlinlang.org/docs/coroutines-overview.html
