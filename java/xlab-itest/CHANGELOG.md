# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### In Progress
- More TPC-DS query coverage
- Hive external table benchmarks
- Concurrent MV refresh tests

## [1.1.0] - 2024-XX-XX

### Added
- **TPC-DS Benchmark Suite**
  - Query 01, 02, 05, 08, 09, 11, 18, 26, 27, 31, 32, 33, 38, 39, 41, 46, 47, 49, 50, 51, 53, 56, 64, 66, 68, 69, 72, 75, 76, 77, 80, 86, 87, 90, 95, 97
  - MV rewrite benchmarks
  - Query performance comparison (with/without MV)

- **TPC-H Benchmark Suite**
  - Concurrent refresh benchmarks
  - Partitioned table benchmarks
  - MV refresh performance tests

- **SSB Benchmark Suite**
  - Star Schema Benchmark queries
  - MV rewrite verification
  - Flat table vs normalized comparison

- **Custom Benchmark Cases**
  - MultiSameTablesBench - Multiple identical tables
  - MultiMvsBench - Multiple materialized views
  - MultiJoinsBench - Complex multi-table joins
  - RefreshSchedulerBench - Refresh timing and delays
  - HiveRefreshBench - Hive external table refresh

### Changed
- Improved connection pool management
- Better error handling in MV refresh
- Enhanced query result validation

### Fixed
- Connection leak in long-running tests
- Race condition in concurrent refresh tests
- Timeout handling in large query execution

## [1.0.0] - 2024-XX-XX

### Added
- **Core Framework (xlab-framework)**
  - Suite base class for tests
  - MVSuite for materialized view tests
  - Connection pooling with HikariCP
  - Configuration management (YAML)
  - SQL execution utilities
  - TPC query loaders (TPC-DS, TPC-H, SSB)

- **Schema Definitions**
  - MTable - Table metadata
  - MMaterializedView - MV metadata
  - MSSBSchema - SSB schema definitions
  - Field and type definitions

- **MV Framework**
  - Enumerator for MV enumeration
  - Worker pattern for concurrent operations
  - MVWorker for MV-specific tasks
  - Block abstraction for batch operations

- **Utilities**
  - ConnectionPool - Database connection management
  - MySQLUtil - MySQL/StarRocks utilities
  - MySQLSession - Session management
  - TPCQuerySet - TPC query loading
  - BrokerLoadUtil - Data loading with broker
  - ShellCmd - Shell command execution
  - DecimalUtil - Decimal arithmetic
  - RandUtil - Random data generation
  - Recorder - Test recording

- **Integration Tests (xlab-itest)**
  - BasicTest - Framework functionality tests
  - MV creation and refresh tests
  - Query rewrite verification

- **Configuration**
  - sr.yaml - StarRocks connection config
  - sr_env.yaml - Environment-specific settings
  - tsp.yaml - Test-specific parameters
  - gradle/libs.versions.toml - Version catalog

- **Build System**
  - Multi-module Gradle project
  - Kotlin 1.9.20
  - JVM 17 target
  - JUnit 5 testing
  - Jackson for JSON/YAML

### Project Structure
```
xlab-itest/
├── xlab-framework/              # Core framework
│   ├── src/main/kotlin/        # Kotlin sources
│   ├── src/main/java/          # Java sources
│   └── src/main/resources/     # SQL templates
├── xlab-itest/                 # Integration tests
├── xlab-benchmark/             # Benchmarks
├── xlab-groovy/                # Groovy scripts
├── conf/                       # Configurations
├── build.gradle.kts            # Root build
└── settings.gradle.kts         # Project settings
```

### Dependencies
- Kotlin 1.9.20
- JVM 17
- Spring JDBC 5.2.8
- MySQL Connector 5.1.49
- JUnit 5 (Jupiter)
- Jackson 2.11.2
- SLF4J + Log4j

### Features
- Database integration testing
- Materialized view lifecycle testing
- TPC benchmark execution
- Performance benchmarking
- Concurrent test execution
- Configuration-driven tests

## [0.9.0] - 2023-XX-XX

### Added
- Initial framework implementation
- Basic connection management
- Simple test cases

## [0.1.0] - 2023-XX-XX

### Added
- Project initialization
- Gradle setup
- Basic module structure

## Roadmap

### Short Term
- [ ] Complete TPC-DS all 99 queries
- [ ] Add more MV rewrite test cases
- [ ] Improve benchmark reporting

### Medium Term
- [ ] Async/await support with Kotlin coroutines
- [ ] Web UI for benchmark results
- [ ] Integration with CI/CD pipelines

### Long Term
- [ ] Support for other databases (ClickHouse, Doris)
- [ ] Distributed testing capabilities
- [ ] Machine learning-based performance prediction
