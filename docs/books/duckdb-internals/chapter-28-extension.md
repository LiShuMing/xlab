# 第28章：Extension 机制

> DuckDB 的零依赖哲学不意味着功能匮乏——它意味着"核心零依赖，功能按需加载"。Extension 机制是这一哲学的实现手段：Parquet 读取、JSON 解析、HTTP 客户端……都不是内置的，但一行 `INSTALL` + `LOAD` 即可用。

## 28.1 Extension 加载器：动态库加载与符号解析

### Extension 的注册与加载

```cpp
// src/main/extension/
// Extension 加载流程：
// 1. INSTALL <extension>   — 下载扩展到 ~/.duckdb/extensions/
// 2. LOAD <extension>      — 加载扩展的动态库，调用注册函数
```

DuckDB 的扩展分为三类：

| 类型 | 编译方式 | 加载方式 | 例子 |
|------|----------|----------|------|
| 内置扩展 | 编译进主二进制 | 自动可用 | icu, parquet (可选) |
| 可加载扩展 | 独立动态库 (.so/.dll) | INSTALL + LOAD | httpfs, json, spatial |
| 存储扩展 | 独立动态库 | ATTACH 时指定 | sqlite, postgres |

### 动态库加载机制

```cpp
// src/include/duckdb/main/extension.hpp
struct Extension {
    string name;
    extension_entry_t entry_function;  // 扩展入口函数
    string version;
};
```

加载流程：
1. 在 `~/.duckdb/extensions/<version>/<platform>/` 下查找动态库
2. 使用平台 API（`dlopen`/`LoadLibrary`）加载动态库
3. 解析入口函数符号（约定为 `<extension>_init`）
4. 调用入口函数，传入 `DatabaseInstance` 指针
5. 扩展通过 `DatabaseInstance` 注册函数、类型、存储扩展等

### 自动加载

DuckDB 支持扩展的自动加载——当用户使用未注册的功能时，自动查找并加载对应扩展：

```sql
SELECT * FROM 'data.parquet';  -- 自动加载 parquet 扩展
SELECT * FROM read_json('data.json');  -- 自动加载 json 扩展
```

自动加载通过 `ExtensionHelper` 实现——它维护功能名到扩展名的映射，在遇到未注册功能时自动触发加载。

## 28.2 Parquet 扩展深度

### Arrow ↔ DuckDB 类型映射

Parquet 使用 Apache Arrow 的类型系统，DuckDB 使用自己的 `LogicalType`。两者之间的映射是 Parquet 扩展的核心：

| Parquet 类型 | DuckDB 类型 | 注意事项 |
|-------------|------------|---------|
| BOOLEAN | BOOLEAN | |
| INT32 | INTEGER | |
| INT64 | BIGINT | |
| FLOAT | FLOAT | |
| DOUBLE | DOUBLE | |
| BYTE_ARRAY / FIXED_LEN_BYTE_ARRAY | VARCHAR / BLOB | 取决于逻辑类型注解 |
| DECIMAL | DECIMAL | 精度可能不同 |
| TIMESTAMP | TIMESTAMP | 时区处理 |
| LIST | LIST | 嵌套类型递归映射 |
| STRUCT | STRUCT | 字段名和类型递归映射 |
| MAP | MAP | 转为 LIST(STRUCT(key, value)) |

### RowGroup 并行读取

Parquet 文件按 RowGroup 组织——每个 RowGroup 包含所有列的数据块。DuckDB 的 Parquet 读取利用这一点实现并行：

```
RowGroup 0: [col0_chunk][col1_chunk]...[colN_chunk]
RowGroup 1: [col0_chunk][col1_chunk]...[colN_chunk]
RowGroup 2: [col0_chunk][col1_chunk]...[colN_chunk]

Thread 1 → 读取 RowGroup 0 的所需列
Thread 2 → 读取 RowGroup 1 的所需列
Thread 3 → 读取 RowGroup 2 的所需列
```

每个线程读取一个 RowGroup，利用列裁剪只读取查询所需的列。这与 DuckDB 自身存储的 RowGroup 并行扫描策略一致——只是数据源从磁盘块变成了 Parquet 文件。

### 谓词下推

Parquet 扩展支持将过滤条件下推到 RowGroup 级别：

1. 利用 RowGroup 的统计信息（min/max/null_count）跳过不满足条件的 RowGroup
2. 利用 Page Index（如果可用）进一步跳过数据页
3. 只解压满足条件的数据页

## 28.3 JSON 扩展

### Schema 推导

JSON 没有固定的 Schema——同一个字段的值类型可能在不同行不同。DuckDB 的 JSON 扩展实现了智能的 Schema 推导：

```sql
SELECT * FROM read_json_auto('data.json');
-- 自动推断列名、类型、嵌套结构
```

推导策略：
1. 采样前 N 行（默认 10,000 行）
2. 对每个字段，收集所有出现的类型
3. 使用类型合并规则确定最终类型（如 INT → BIGINT → DOUBLE → VARCHAR）
4. 嵌套对象映射为 STRUCT，数组映射为 LIST

### JSONLogicalType

DuckDB 引入了 `JSONLogicalType`——一种特殊的逻辑类型，表示"可能是 JSON"的值。在绑定阶段，JSON 列的值被解析为 `VARCHAR`（原始字符串）或 `STRUCT/LIST`（结构化），取决于查询的上下文。

## 28.4 Delta Lake Extension

Delta Lake 是 Databricks 开发的开放湖格式，基于 Parquet 文件 + JSON 事务日志。DuckDB 的 Delta 扩展：

1. 读取 Delta 事务日志（JSON 格式），确定活跃文件列表
2. 利用时间旅行功能支持 `VERSION AS OF` 和 `TIMESTAMP AS OF`
3. 只读取活跃的 Parquet 文件（跳过已删除的文件）
4. 将 Delta 的统计信息传递给 DuckDB 的谓词下推

与 Iceberg 的对比：Iceberg 使用二进制清单文件（Avro/Parquet），Delta 使用 JSON 日志。两者都是"文件列表 + 元数据"的架构，但元数据格式不同。DuckDB 的扩展只需理解元数据格式，Parquet 读取复用现有逻辑。

## 本章小结

DuckDB 的 Extension 机制是"核心零依赖，功能按需加载"的工程实现：

- **动态库加载**：平台原生的 dlopen/LoadLibrary + 约定符号名
- **自动加载**：功能名 → 扩展名的映射，用户无感知
- **TableFunction 作为扩展接口**：`read_parquet`、`read_json` 都是 TableFunction——四个回调（bind、init_global、init_local、function）统一了数据源扩展
- **存储扩展**：自定义 Catalog + TransactionManager，支持 SQLite/Postgres 等外部数据库

与 PostgreSQL 扩展的对比：PostgreSQL 扩展可以修改查询计划器、添加自定义索引类型、定义新的执行器节点。DuckDB 的扩展更受限——主要是函数注册和存储扩展。但这也意味着 DuckDB 扩展更安全——不会破坏核心查询引擎的正确性。
