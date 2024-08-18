# 第17章：SQL 方言与双向转换

## 17.1 SqlDialect 体系

`SqlDialect`（`sql/dialect/`，40 文件）定义了 40+ 种数据库的 SQL 方言差异。每种方言是一个枚举实例或子类。

### 17.1.1 方言差异的维度

| 维度 | 示例差异 |
|------|---------|
| 标识符引用 | MySQL: `` `name` ``, Oracle: `"NAME"`, SQL Server: `[name]` |
| 字符串引号 | MySQL: `'hello'`, PostgreSQL: `'hello'` (与标识符引号不同) |
| 分页语法 | MySQL: `LIMIT 10 OFFSET 5`, Oracle: `OFFSET 5 ROWS FETCH NEXT 10 ROWS ONLY` |
| 数据类型 | MySQL: `INT`, PostgreSQL: `INTEGER`, Oracle: `NUMBER(10)` |
| 函数名 | MySQL: `IFNULL`, PostgreSQL: `COALESCE`, Oracle: `NVL` |
| NULL 排序 | 默认升序时 NULL 在最后还是最前 |
| 布尔类型 | PostgreSQL: `TRUE/FALSE`, Oracle: 无原生布尔 |
| 日期函数 | `DATE_TRUNC` vs `TRUNC` vs `DATE_FORMAT` |
| 外连接语法 | `LEFT JOIN` vs `(+)` |

### 17.1.2 SqlDialect 关键方法

```java
// sql/SqlDialect.java
public class SqlDialect {
  // 标识符引用
  public String quoteIdentifier(String val) { ... }
  public StringBuilder quoteIdentifier(StringBuilder buf, String val) { ... }

  // 字符串字面量
  public void quoteStringLiteral(StringBuilder buf, String val) { ... }

  // 函数 unparse
  public void unparseCall(SqlWriter writer, SqlCall call, int leftPrec, int rightPrec) { ... }
  public void unparseDateTimeLiteral(SqlWriter writer, ...) { ... }
  public void unparseBoolLiteral(SqlWriter writer, ...) { ... }

  // NULL 排序
  public RelDataTypeSystem getDataTypeSystem() { ... }
  public NullCollation getNullCollation() { ... }

  // 分页支持
  public boolean supportsOffsetFetch() { ... }
  public void unparseFetchUsingAnsi(SqlWriter writer, ...) { ... }

  // 能力查询
  public boolean supportsAliasedValues() { ... }
  public boolean supportsNestedArrays() { ... }
  public CalendarPolicy getCalendarPolicy() { ... }
}
```

### 17.1.3 方言继承体系

```
SqlDialect (基类)
├── AnsiSqlDialect         — SQL 标准
├── CalciteSqlDialect      — Calcite 内部
├── MysqlSqlDialect        — MySQL/MariaDB
├── PostgresqlSqlDialect   — PostgreSQL
├── OracleSqlDialect       — Oracle
├── MssqlSqlDialect        — SQL Server
├── BigQuerySqlDialect     — Google BigQuery
├── HiveSqlDialect         — Apache Hive
├── SparkSqlDialect        — Apache Spark
├── ClickHouseSqlDialect   — ClickHouse
├── DorisSqlDialect        — Apache Doris
├── StarRocksSqlDialect    — StarRocks
├── SnowflakeSqlDialect    — Snowflake
├── TrinoSqlDialect        — Trino
├── DuckDBSqlDialect       — DuckDB
├── Db2SqlDialect          — IBM DB2
├── H2SqlDialect           — H2
├── HsqldbSqlDialect       — HyperSQL
├── PhoenixSqlDialect      — Apache Phoenix
├── VerticaSqlDialect      — Vertica
└── ... (40+ 种)
```

### 17.1.4 方言差异示例

**分页语法**：

```java
// MySQL
SELECT * FROM emp LIMIT 10 OFFSET 5

// Oracle (12c+)
SELECT * FROM emp OFFSET 5 ROWS FETCH NEXT 10 ROWS ONLY

// SQL Server
SELECT * FROM emp ORDER BY id OFFSET 5 ROWS FETCH NEXT 10 ROWS ONLY
```

**NULL 排序**：

```java
// PostgreSQL: NULLS FIRST (升序) / NULLS LAST (降序)
// MySQL: NULL 被视为最小值（升序时 NULL 在最前）
// Oracle: NULLS LAST (升序) / NULLS FIRST (降序)
```

## 17.2 RelToSqlConverter — 关系代数 → SQL

`RelToSqlConverter`（`rel/rel2sql/`，3 文件）将 RelNode 树转换回 SQL 字符串。这在联邦查询中至关重要——当 Calcite 需要将查询下推到外部数据库时，需要生成该数据库方言的 SQL。

### 17.2.1 核心流程

```
RelNode 树 → SqlNode 树 → SQL 字符串（按方言 unparse）
```

### 17.2.2 使用示例

```java
RelNode relNode = ...;  // 优化后的 RelNode 树

// 转换为 MySQL SQL
SqlDialect dialect = MysqlSqlDialect.DEFAULT;
RelToSqlConverter converter = new RelToSqlConverter(dialect);
SqlNode sqlNode = converter.visitChild(0, relNode).asStatement();
String sql = sqlNode.toSqlString(dialect).getSql();
// 输出: SELECT `name`, `salary` FROM `emp` WHERE `salary` > 1000 LIMIT 10
```

### 17.2.3 方言感知的 unparse

`SqlDialect.unparseCall()` 方法为每种方言定制 SQL 生成：

```java
// MysqlSqlDialect
@Override public void unparseCall(SqlWriter writer, SqlCall call, ...) {
  switch (call.getKind()) {
    case FETCH:
      // MySQL: LIMIT offset, count
      writer.keyword("LIMIT");
      ...
      break;
    default:
      super.unparseCall(writer, call, ...);
  }
}

// OracleSqlDialect
@Override public void unparseCall(SqlWriter writer, SqlCall call, ...) {
  switch (call.getKind()) {
    case FETCH:
      // Oracle: OFFSET ... ROWS FETCH NEXT ... ROWS ONLY
      writer.keyword("OFFSET");
      ...
      break;
  }
}
```

### 17.2.4 联邦查询中的下推

JDBC 适配器使用 RelToSqlConverter 将查询下推到远程数据库：

```
原始 SQL:
  SELECT e.name, d.dept_name
  FROM mysql.emp e, local_csv.dept d
  WHERE e.dept_id = d.id AND e.salary > 1000

Calcite 生成的下推 SQL (MySQL 方言):
  SELECT `name`, `dept_id` FROM `emp` WHERE `salary` > 1000

本地执行:
  HashJoin(e.dept_id = d.id)
    ← 下推到 MySQL 的结果
    ← CSV 扫描 dept 表的结果
```

## 17.3 从 StarRocks 视角：方言适配在跨引擎查询中的应用

StarRocks 作为多引擎查询网关时，方言适配至关重要：

1. **查询下推**：将过滤、聚合下推到外部数据源（MySQL、Elasticsearch、Hive）
2. **类型映射**：StarRocks 的 `DECIMAL` 需要映射为 MySQL 的 `DECIMAL`、Hive 的 `DECIMAL`
3. **函数替换**：`DATE_TRUNC` → MySQL 的 `DATE_FORMAT`、Hive 的 `TRUNC`
4. **分页适配**：不同数据源的分页语法差异

---

## 本章小结

SqlDialect 体系定义了 40+ 种数据库的 SQL 方言差异，涵盖标识符引用、分页语法、NULL 排序、函数名等维度。RelToSqlConverter 将 RelNode 树转换回 SQL 字符串，是联邦查询下推的核心组件。方言适配在跨引擎查询中至关重要——需要根据目标数据源的方言生成正确的 SQL。
