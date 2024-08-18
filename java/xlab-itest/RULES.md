# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the xlab-itest StarRocks Integration Testing Framework.

## Code Style

### Kotlin Standards

- **Kotlin Version**: 1.9.20
- **JVM Target**: 17
- **Style**: Official Kotlin Coding Conventions

### Commands

```bash
# Build
./gradlew build

# Test
./gradlew test

# Format with ktlint (if configured)
./gradlew ktlintFormat

# Check
./gradlew check
```

## Project Structure

```
java/xlab-itest/
├── xlab-framework/              # Core framework
│   ├── src/main/kotlin/        # Kotlin sources
│   ├── src/main/java/          # Java sources
│   └── src/main/resources/     # Resources (SQL, configs)
├── xlab-itest/                 # Integration tests
│   └── src/test/kotlin/        # Test sources
├── xlab-benchmark/             # Benchmark tests
│   └── src/test/kotlin/        # Benchmark sources
├── xlab-groovy/                # Groovy scripts
├── conf/                       # Configuration files
├── build.gradle.kts            # Root build
└── settings.gradle.kts         # Project settings
```

## Naming Conventions

- **Packages**: `com.starrocks.itest.{module}`
- **Classes**: `PascalCase` (e.g., `Suite`, `MVSuite`, `ConnectionPool`)
- **Interfaces**: `PascalCase` (e.g., `Worker`, `Block`)
- **Functions**: `camelCase` (e.g., `executeQuery`, `createMV`)
- **Variables**: `camelCase` (e.g., `connPool`, `querySet`)
- **Constants**: `SCREAMING_SNAKE_CASE` or `PascalCase` in companion objects
- **Test classes**: `ClassNameTest` or `ClassNameBench`

## Kotlin Coding Standards

### File Organization

```kotlin
package com.starrocks.itest.framework

// Imports grouped: stdlib, third-party, project
import java.sql.Connection
import org.slf4j.LoggerFactory
import com.starrocks.itest.framework.utils.MySQLUtil

// Class documentation
/**
 * Base test suite for StarRocks integration tests.
 *
 * Provides database connection management and common utilities
 * for writing integration tests.
 */
abstract class Suite {
    // Companion object for constants
    companion object {
        const val DEFAULT_TIMEOUT = 30000L
        val LOGGER = LoggerFactory.getLogger(Suite::class.java)
    }

    // Properties
    protected val conf: SRConf = SRConf.fromFile("conf/sr.yaml")
    protected val connPool: ConnectionPool = ConnectionPool(conf)

    // Abstract method
    abstract fun run()
}
```

### Null Safety

```kotlin
// Good - Explicit nullability
fun findTable(name: String): Table? {
    return tables.find { it.name == name }
}

// Good - Safe call
val size = table?.fields?.size ?: 0

// Good - Elvis operator
val timeout = config.timeout ?: DEFAULT_TIMEOUT

// Bad - Unnecessary null check
if (table != null) {
    return table.name  // Use ?. instead
}
```

### Immutability

```kotlin
// Good - Immutable val
val tables = listOf(table1, table2)

// Good - Mutable only when necessary
var retryCount = 0

// Good - Read-only collections
val fields: List<Field> = mutableListOf()

// Bad - Mutable when immutable suffices
var tables = listOf(table1)  // Use val
```

### Extension Functions

```kotlin
// Good - Extension for utilities
fun Connection.executeQuery(sql: String): ResultSet {
    return this.createStatement().executeQuery(sql)
}

// Usage
conn.executeQuery("SELECT * FROM t")
```

## Testing Standards

### Test Structure

```kotlin
package com.starrocks.itest.framework

import org.junit.jupiter.api.Test
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.AfterEach
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ConnectionPoolTest {
    private lateinit var pool: ConnectionPool

    @BeforeEach
    fun setUp() {
        val conf = SRConf.fromFile("conf/test.yaml")
        pool = ConnectionPool(conf)
    }

    @AfterEach
    fun tearDown() {
        pool.close()
    }

    @Test
    fun `should create connection pool`() {
        assertTrue(pool.isInitialized())
    }

    @Test
    fun `should return valid connection`() {
        val conn = pool.getConnection()
        assertTrue(conn.isValid(5))
        conn.close()
    }
}
```

### Test Naming

Use backticks for readable test names:
```kotlin
@Test
fun `should rewrite query using materialized view`() { }

@Test
fun `should throw exception for invalid SQL`() { }
```

### Assertions

```kotlin
// Good - Kotlin test assertions
assertEquals(expected, actual)
assertTrue(condition)
assertNull(value)
assertFailsWith<SQLException> { /* code */ }

// Good - AssertJ style (if available)
assertThat(result).isEqualTo(expected)
assertThat(list).hasSize(3)
```

## SQL Style

### Formatting

```sql
-- Good - Uppercase keywords, aligned
CREATE TABLE IF NOT EXISTS lineitem (
    l_orderkey      BIGINT,
    l_partkey       BIGINT,
    l_suppkey       BIGINT,
    l_linenumber    INT,
    l_quantity      DECIMAL(15, 2),
    l_extendedprice DECIMAL(15, 2),
    l_discount      DECIMAL(15, 2),
    l_tax           DECIMAL(15, 2),
    l_returnflag    VARCHAR(1),
    l_linestatus    VARCHAR(1),
    l_shipdate      DATE,
    l_commitdate    DATE,
    l_receiptdate   DATE
)
DUPLICATE KEY(l_orderkey, l_linenumber)
DISTRIBUTED BY HASH(l_orderkey)
PROPERTIES("replication_num" = "1");
```

### Materialized Views

```sql
-- Good - Clear MV definition
CREATE MATERIALIZED VIEW mv_lineitem_summary
AS
SELECT
    l_returnflag,
    l_linestatus,
    SUM(l_quantity) AS sum_qty,
    SUM(l_extendedprice) AS sum_base_price,
    AVG(l_discount) AS avg_discount
FROM lineitem
GROUP BY l_returnflag, l_linestatus;
```

## Error Handling

### Exceptions

```kotlin
// Good - Try-catch with specific exception
try {
    executeQuery(sql)
} catch (e: SQLException) {
    LOGGER.error("SQL execution failed: ${e.message}")
    throw TestException("Query failed: $sql", e)
}

// Good - Using runCatching
runCatching {
    executeQuery(sql)
}.onFailure { e ->
    LOGGER.error("Query failed", e)
}.getOrThrow()
```

### Logging

```kotlin
// Good - Using logger
LOGGER.info("Starting test suite: ${this.javaClass.simpleName}")
LOGGER.debug("Executing SQL: $sql")
LOGGER.error("Failed to connect", exception)

// Bad - System.out
println("Debug info")  // Use LOGGER instead
```

## Configuration Management

### Configuration Classes

```kotlin
@Serializable
data class SRConf(
    val host: String = "127.0.0.1",
    val port: Int = 9030,
    val username: String = "root",
    val password: String = "",
    val database: String = "test"
) {
    companion object {
        fun fromFile(path: String): SRConf {
            val yaml = File(path).readText()
            return Yaml.decodeFromString(serializer(), yaml)
        }
    }
}
```

## Database Access

### Connection Pooling

```kotlin
class ConnectionPool(conf: SRConf) {
    private val dataSource = HikariDataSource().apply {
        jdbcUrl = "jdbc:mysql://${conf.host}:${conf.port}/${conf.database}"
        username = conf.username
        password = conf.password
        maximumPoolSize = 10
    }

    fun getConnection(): Connection = dataSource.connection
}
```

### Query Execution

```kotlin
// Good - Using try-with-resources pattern
fun executeQuery(sql: String): ResultSet {
    return connPool.getConnection().use { conn ->
        conn.createStatement().use { stmt ->
            stmt.executeQuery(sql)
        }
    }
}
```

## Benchmarking

### Benchmark Structure

```kotlin
class QueryBenchmark : MVSuite() {
    @Test
    fun benchmarkTPCDSQueries() {
        val queries = TPCQuerySet.loadTPCDS()
        val results = mutableMapOf<String, Long>()

        queries.forEach { (name, sql) ->
            val duration = measureTimeMillis {
                executeQuery(sql)
            }
            results[name] = duration
            println("$name: ${duration}ms")
        }

        // Output summary
        val avgTime = results.values.average()
        println("Average: ${avgTime}ms")
    }
}
```

## Git Workflow

### Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New feature/test
- `fix`: Bug fix
- `test`: Test changes
- `perf`: Performance improvement
- `refactor`: Code restructuring
- `docs`: Documentation

Examples:
```
feat: add TPC-DS query rewrite benchmark
fix: handle MV refresh timeout
test: add concurrent refresh test case
perf: optimize connection pool sizing
```

## Dependencies

### Adding Dependencies

```kotlin
// In build.gradle.kts
dependencies {
    implementation("org.example:library:1.0.0")
    testImplementation("org.example:test-lib:1.0.0")
}
```

### Version Catalog

```toml
# In gradle/libs.versions.toml
[versions]
kotlin = "1.9.20"
junit = "5.10.0"

[libraries]
kotlin-stdlib = { module = "org.jetbrains.kotlin:kotlin-stdlib", version.ref = "kotlin" }
junit-jupiter = { module = "org.junit.jupiter:junit-jupiter", version.ref = "junit" }
```

## Documentation

### KDoc Format

```kotlin
/**
 * Executes a SQL query and returns the result set.
 *
 * @param sql The SQL query to execute
 * @param timeoutMs Query timeout in milliseconds (default: 30000)
 * @return ResultSet containing query results
 * @throws SQLException if query execution fails
 * @throws TimeoutException if query exceeds timeout
 *
 * Example usage:
 * ```
 * val result = executeQuery("SELECT * FROM t")
 * while (result.next()) {
 *     println(result.getString(1))
 * }
 * ```
 */
fun executeQuery(sql: String, timeoutMs: Long = 30000): ResultSet
```

## Resources

- [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html)
- [JUnit 5 User Guide](https://junit.org/junit5/docs/current/user-guide/)
- [StarRocks SQL Reference](https://docs.starrocks.io/docs/sql-reference/)
