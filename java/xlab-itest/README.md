# xlab-itest

StarRocks Integration Testing Framework using Kotlin.

## Overview

xlab-itest is a comprehensive integration testing and benchmarking framework for [StarRocks](https://www.starrocks.io/) database. It provides utilities for writing integration tests, running TPC benchmarks (TPC-DS, TPC-H, SSB), and testing materialized view (MV) functionality.

## Features

- **Integration Testing Framework** - Base utilities for database integration tests
- **Materialized View Testing** - Specialized support for MV creation, refresh, and query rewrite
- **TPC Benchmarks** - TPC-DS, TPC-H, and SSB benchmark suites
- **Multi-Module Structure** - Framework, tests, and benchmarks as separate modules
- **Kotlin-First** - Modern Kotlin with coroutine support
- **Configuration-Driven** - YAML-based configuration for different environments

## Project Structure

```
xlab-itest/
├── xlab-framework/              # Core testing framework
│   ├── src/main/kotlin/         # Framework utilities
│   │   ├── framework/           # Test framework
│   │   │   ├── Suite.kt         # Base test suite
│   │   │   ├── MVSuite.kt       # Materialized view suite
│   │   │   ├── schema/          # Schema definitions
│   │   │   ├── mv/              # MV workers and tasks
│   │   │   └── utils/           # Utilities (connection, SQL, etc.)
│   │   └── schema/              # Schema definitions (Java)
│   └── src/main/resources/      # SQL templates and queries
│       ├── tpcds/               # TPC-DS queries
│       ├── tpch/                # TPC-H queries
│       └── materialization/     # MV definitions
├── xlab-itest/                  # Integration tests
│   └── src/test/kotlin/         # Test cases
├── xlab-benchmark/              # Benchmark tests
│   └── src/test/kotlin/         # Benchmark suites
│       ├── tpcds/               # TPC-DS benchmarks
│       ├── tpch/                # TPC-H benchmarks
│       ├── ssb/                 # SSB benchmarks
│       └── cases/               # Specific benchmark cases
├── xlab-groovy/                 # Groovy scripts
├── conf/                        # Configuration files
│   ├── sr.yaml                  # StarRocks connection config
│   ├── sr_env.yaml              # Environment-specific config
│   ├── tsp.yaml                 # Test-specific config
│   └── tsp2.yaml                # Alternative test config
└── gradle/                      # Gradle wrapper
```

## Requirements

- JDK 17+
- Gradle 8.0+
- StarRocks cluster (local or remote)
- MySQL JDBC driver (for StarRocks connection)

## Quick Start

### 1. Clone and Build

```bash
cd java/xlab-itest
./gradlew build
```

### 2. Configure StarRocks Connection

Create or edit `conf/sr.yaml`:

```yaml
host: 127.0.0.1
port: 9030
username: root
password: ""
database: test
```

### 3. Run Tests

```bash
# Run all tests
./gradlew test

# Run specific test
./gradlew :xlab-itest:test --tests "BasicTest"

# Run benchmarks
./gradlew :xlab-benchmark:test
```

## Writing Tests

### Basic Test

```kotlin
package com.starrocks.itest.framework

class MyTest : Suite() {
    override fun run() {
        // Create table
        executeSql("""
            CREATE TABLE IF NOT EXISTS t (
                id INT,
                name VARCHAR(100)
            )
            DUPLICATE KEY(id)
        """)

        // Insert data
        executeSql("INSERT INTO t VALUES (1, 'test')")

        // Query and verify
        val result = executeQuery("SELECT * FROM t")
        assert(result.next())
        assert(result.getInt("id") == 1)

        // Cleanup
        executeSql("DROP TABLE t")
    }
}
```

### Materialized View Test

```kotlin
class MVTest : MVSuite() {
    fun testMVQueryRewrite() {
        // Create base table
        createTable("""
            CREATE TABLE sales (
                id INT,
                amount DECIMAL(10,2),
                dt DATE
            ) DUPLICATE KEY(id)
        """)

        // Create MV
        createMV("""
            CREATE MATERIALIZED VIEW mv_daily_sales AS
            SELECT dt, SUM(amount)
            FROM sales
            GROUP BY dt
        """)

        // Insert data
        executeSql("INSERT INTO sales VALUES (1, 100.0, '2024-01-01')")

        // Refresh MV
        refreshMV("mv_daily_sales")

        // Query should use MV
        val plan = explainQuery("SELECT dt, SUM(amount) FROM sales GROUP BY dt")
        assert(plan.contains("mv_daily_sales"))
    }
}
```

## Running Benchmarks

### TPC-DS Benchmark

```kotlin
class TPCDSBenchmark : MVSuite() {
    @Test
    fun runTPCDSWithMV() {
        // Load queries
        val queries = TPCQuerySet.loadTPCDS()

        // Create MVs
        createMVsForTPCDS()

        // Run benchmark
        queries.forEach { (name, sql) ->
            val time = measureTimeMillis {
                executeQuery(sql)
            }
            println("$name: ${time}ms")
        }
    }
}
```

### Running from Command Line

```bash
# Run all benchmarks
./gradlew :xlab-benchmark:test

# Run specific benchmark
./gradlew :xlab-benchmark:test --tests "TPCDSWithMVBench"

# Run with output
./gradlew :xlab-benchmark:test --info
```

## Configuration

### StarRocks Configuration

`conf/sr.yaml`:

```yaml
# Connection settings
host: 127.0.0.1
port: 9030
username: root
password: ""
database: test

# Connection pool
poolSize: 10
timeout: 30000
```

### Test-Specific Configuration

`conf/tsp.yaml`:

```yaml
# Test parameters
iterations: 3
concurrency: 4
dataScale: "1g"
```

## Utilities

### Connection Pool

```kotlin
val pool = ConnectionPool(conf)
val conn = pool.getConnection()
conn.use {
    // Use connection
}
```

### SQL Execution

```kotlin
// Execute DDL/DML
executeSql("CREATE TABLE ...")
executeSql("INSERT INTO ...")

// Execute query
val rs = executeQuery("SELECT * FROM t")
while (rs.next()) {
    println(rs.getString(1))
}
```

### TPC Query Loading

```kotlin
// Load TPC-DS queries
val tpcdsQueries = TPCQuerySet.loadTPCDS()

// Load TPC-H queries
val tpchQueries = TPCQuerySet.loadTPCH()

// Load specific query
val q1 = TPCQuerySet.loadQuery("tpcds", "query01.sql")
```

## Modules

### xlab-framework

Core testing framework with:
- Database connection management
- SQL execution utilities
- Schema definitions
- Materialized view helpers
- TPC query loaders

### xlab-itest

Integration tests for:
- Basic functionality
- Edge cases
- Bug regression tests

### xlab-benchmark

Performance benchmarks:
- TPC-DS with/without MVs
- TPC-H concurrent refresh
- SSB with MV rewrite
- Custom benchmark cases

### xlab-groovy

Groovy scripts for:
- Data generation
- Cluster management
- Ad-hoc testing

## Best Practices

1. **Always cleanup** - Drop tables/MVs after tests
2. **Use connection pooling** - For concurrent tests
3. **Handle timeouts** - Set appropriate query timeouts
4. **Log properly** - Use LOGGER, not println
5. **Configure externally** - Use YAML configs, not hardcoded values

## Troubleshooting

### Connection Issues

```bash
# Test StarRocks connection
mysql -h 127.0.0.1 -P 9030 -u root
```

### Gradle Issues

```bash
# Clean and rebuild
./gradlew clean build

# Refresh dependencies
./gradlew --refresh-dependencies
```

## Contributing

1. Follow Kotlin coding conventions
2. Write tests for new features
3. Update documentation
4. Use meaningful commit messages

## License

MIT License

## Resources

- [StarRocks Documentation](https://docs.starrocks.io/)
- [Kotlin Documentation](https://kotlinlang.org/docs/)
- [TPC-DS Specification](http://www.tpc.org/tpcds/)
- [TPC-H Specification](http://www.tpc.org/tpch/)
