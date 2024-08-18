# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the xlab-itest (StarRocks Integration Testing Framework) project.

## Project Architecture

xlab-itest is a comprehensive integration testing framework for StarRocks database, written in Kotlin with multi-module Gradle structure.

```
java/xlab-itest/
├── xlab-framework/              # Core testing framework
│   ├── src/main/kotlin/        # Framework utilities
│   │   ├── framework/          # Test framework
│   │   │   ├── Suite.kt        # Base test suite
│   │   │   ├── MVSuite.kt      # Materialized view test suite
│   │   │   ├── schema/         # Schema definitions
│   │   │   ├── mv/             # MV workers and tasks
│   │   │   └── utils/          # Utilities
│   │   └── schema/             # Schema definitions (Java)
│   └── src/main/resources/     # SQL templates and queries
│       ├── tpcds/              # TPC-DS queries
│       ├── tpch/               # TPC-H queries
│       └── materialization/    # MV definitions
├── xlab-itest/                 # Integration tests
│   └── src/test/kotlin/        # Test cases
├── xlab-benchmark/             # Benchmark tests
│   └── src/test/kotlin/        # Benchmark suites
│       ├── tpcds/              # TPC-DS benchmarks
│       ├── tpch/               # TPC-H benchmarks
│       ├── ssb/                # SSB benchmarks
│       └── cases/              # Specific benchmark cases
├── xlab-groovy/                # Groovy scripts
├── conf/                       # Configuration files
│   ├── sr.yaml                 # StarRocks config
│   ├── tsp.yaml                # Test specific
│   └── sr_env.yaml             # Environment config
├── build.gradle.kts            # Root build script
├── settings.gradle.kts         # Project settings
└── gradle/                     # Gradle wrapper
```

## Key Components

### Framework (`xlab-framework/`)

#### Suite (`framework/Suite.kt`)
Base test suite providing:
- Database connection management
- Configuration loading
- Test lifecycle hooks

```kotlin
abstract class Suite {
    val conf: SRConf = SRConf.fromFile("conf/sr.yaml")
    val connPool: ConnectionPool = ConnectionPool(conf)

    abstract fun run()
}
```

#### MVSuite (`framework/MVSuite.kt`)
Materialized view testing suite:
- MV creation and management
- Refresh scheduling
- Query rewrite testing

#### Schema (`framework/schema/`)
Table and schema definitions:
```kotlin
class Table(val name: String, val fields: List<Field>)
class Field(val name: String, val type: String)
```

#### Utilities (`framework/utils/`)
- `ConnectionPool` - Database connection pooling
- `MySQLUtil` - MySQL/StarRocks utilities
- `TPCQuerySet` - TPC query loaders
- `BrokerLoadUtil` - Data loading utilities
- `ShellCmd` - Shell command execution

### Integration Tests (`xlab-itest/`)

Integration test cases using the framework:
```kotlin
class BasicTest : Suite() {
    override fun run() {
        // Test implementation
        val result = executeQuery("SELECT COUNT(*) FROM lineitem")
        assert(result > 0)
    }
}
```

### Benchmarks (`xlab-benchmark/`)

Performance benchmarks:

#### TPC-DS Benchmarks (`benchmark/tpcds/`)
- TPC-DS with materialized views
- Query rewrite verification
- Performance comparison

#### TPC-H Benchmarks (`benchmark/tpch/`)
- TPC-H concurrent refresh tests
- Partitioned table benchmarks
- MV refresh performance

#### SSB Benchmarks (`benchmark/ssb/`)
- Star Schema Benchmark
- MV rewrite tests

#### Specific Cases (`benchmark/cases/`)
- `MultiMvsBench` - Multiple MVs performance
- `MultiJoinsBench` - Complex join benchmarks
- `RefreshSchedulerBench` - Refresh timing tests
- `HiveRefreshBench` - External table refresh

## Build System

### Gradle Commands

```bash
# Build all modules
./gradlew build

# Run tests
./gradlew test

# Run specific test
./gradlew :xlab-itest:test --tests "BasicTest"

# Run benchmarks
./gradlew :xlab-benchmark:test

# Clean build
./gradlew clean

# Generate wrapper
./gradlew wrapper
```

### Multi-Module Structure

```kotlin
// settings.gradle.kts
include("xlab-framework")    // Core framework
include("xlab-itest")        // Integration tests
include("xlab-benchmark")    // Benchmarks
include("xlab-groovy")       // Groovy scripts
```

## Dependencies

- **Kotlin** 1.9.20
- **JVM** 17
- **Spring JDBC** 5.2.8
- **MySQL Connector** 5.1.49
- **JUnit 5** (Jupiter)
- **Jackson** (JSON/YAML)
- **SLF4J + Log4j**

## Configuration

### StarRocks Configuration (`conf/sr.yaml`)

```yaml
host: 127.0.0.1
port: 9030
username: root
password: ""
database: test
```

### Loading Configuration

```kotlin
val conf = SRConf.fromFile("conf/sr.yaml")
val pool = ConnectionPool(conf)
```

## Common Tasks

### Writing a Test

```kotlin
package com.starrocks.itest.framework

class MyTest : Suite() {
    override fun run() {
        // Setup
        executeSql("CREATE TABLE IF NOT EXISTS t (id INT)")

        // Test
        val result = executeQuery("SELECT * FROM t")

        // Assert
        assert(result.isEmpty())

        // Cleanup
        executeSql("DROP TABLE t")
    }
}
```

### Writing a Benchmark

```kotlin
package com.starrocks.itest.benchmark

class MyBenchmark : MVSuite() {
    @Test
    fun benchmarkQueryRewrite() {
        // Create MV
        createMV("""
            CREATE MATERIALIZED VIEW mv1 AS
            SELECT * FROM lineitem WHERE l_shipdate >= '2023-01-01'
        """)

        // Run query
        val time = measureTimeMillis {
            executeQuery("SELECT * FROM lineitem WHERE l_shipdate >= '2023-01-01'")
        }

        println("Query time: ${time}ms")
    }
}
```

### Creating a Materialized View Test

```kotlin
class MVTest : MVSuite() {
    fun testMVRefresh() {
        // Create base table
        createTable("""
            CREATE TABLE sales (
                id INT,
                amount DECIMAL(10,2),
                dt DATE
            ) DUPLICATE KEY(id)
        """)

        // Create MV
        val mv = createMV("""
            CREATE MATERIALIZED VIEW mv_sales AS
            SELECT dt, SUM(amount) FROM sales GROUP BY dt
        """)

        // Insert data
        executeSql("INSERT INTO sales VALUES (1, 100.0, '2024-01-01')")

        // Trigger refresh
        refreshMV(mv.name)

        // Verify
        val result = executeQuery("SELECT * FROM mv_sales")
        assert(result.size == 1)
    }
}
```

## Testing with TPC Benchmarks

### Loading TPC-DS Queries

```kotlin
val tpcdsQueries = TPCQuerySet.loadTPCDS()
for ((name, sql) in tpcdsQueries) {
    val time = benchmarkQuery(sql)
    println("$name: ${time}ms")
}
```

### SSB Benchmark

```kotlin
class SSBTest : Suite() {
    fun testSSBWithMV() {
        // Create SSB schema
        createSSBTables()

        // Create MVs for common queries
        createMV("""
            CREATE MATERIALIZED VIEW mv_lineorder AS
            SELECT * FROM lineorder WHERE lo_orderdate >= '2023-01-01'
        """)

        // Run SSB queries
        for (query in ssbQueries) {
            val result = executeQuery(query)
            // Verify results
        }
    }
}
```

## Prohibited Actions

1. **DO NOT** commit database passwords
2. **DO NOT** hardcode connection strings
3. **DO NOT** skip cleanup in tests
4. **DO NOT** use blocking I/O in async contexts
5. **DO NOT** ignore exceptions in tests

## Performance Considerations

- Use connection pooling for concurrent tests
- Clean up tables/MVs after tests
- Use appropriate timeouts for long-running queries
- Monitor memory usage in benchmarks

## Resources

- [StarRocks Documentation](https://docs.starrocks.io/)
- [Kotlin Documentation](https://kotlinlang.org/docs/)
- [Gradle Documentation](https://docs.gradle.org/)
- [JUnit 5 Documentation](https://junit.org/junit5/)

## Communication Style

- Reference SQL syntax for StarRocks specifically
- Include example test cases
- Document expected behavior
- Explain MV (materialized view) concepts
