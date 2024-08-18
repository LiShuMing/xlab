# 第29章：C API 与语言绑定

> DuckDB 的核心是 C++，但它的灵魂是可嵌入的。C API 是这个灵魂的接口——所有语言绑定（Python、R、Java、Go、Node.js、WASM）都通过 C API 与 DuckDB 对话。

## 29.1 C API 设计

### 不透明句柄模式

所有 C API 类型都是不透明指针：

```cpp
// src/include/duckdb/main/capi/capi_internal.hpp
duckdb_database   → DatabaseWrapper (shared_ptr<DuckDB>)
duckdb_connection → Connection*
duckdb_result     → DuckDBResultData (unique_ptr<QueryResult>)
duckdb_prepared_statement → PreparedStatementWrapper
duckdb_data_chunk → DataChunk*
duckdb_vector     → Vector*
duckdb_value      → Value*
```

不透明指针隐藏了 C++ 的 ABI 复杂性——调用者只需 `#include "duckdb.h"`，无需知道内部实现。

### 两阶段结果 API

```cpp
// CAPIResultSetType 枚举：
// 1. 废弃的物化 API：duckdb_value_int32(result, col, row)
//    → 物化整个结果，按列分配数组
// 2. 基于 Chunk 的 API：duckdb_fetch_chunk(result)
//    → 逐块返回 DataChunk，匹配 DuckDB 的向量化执行模型
```

基于 Chunk 的 API 是推荐方式——它不会一次性物化所有行，而是逐块流式返回，内存效率更高。

### Arrow 集成

```cpp
// src/main/capi/arrow-c.cpp
// 双向转换：
duckdb_to_arrow_schema()          // DuckDB → Arrow Schema
duckdb_data_chunk_to_arrow()      // DuckDB → Arrow Array
duckdb_schema_from_arrow()        // Arrow → DuckDB Schema
duckdb_data_chunk_from_arrow()    // Arrow → DuckDB DataChunk
```

Arrow C Data Interface 实现了零拷贝数据交换——这是 DuckDB 与 Python 数据科学生态无缝集成的技术基础。

### 扩展 C API

`duckdb_ext_api_v1` 结构体包含 **400+ 函数指针**，覆盖整个稳定 C API。扩展初始化时通过 `GetAPI(info, version)` 获取函数指针表：

```
扩展加载时：
1. dlsym 解析 <name>_init_c_api 符号
2. 创建 ExtensionAccess 回调结构（SetError / GetDatabase / GetAPI）
3. 调用 init 函数，传入 access
4. 扩展调用 access.GetAPI() 获取函数指针表
5. 扩展使用函数指针注册函数、类型等
```

这种设计让 C API 扩展永远不直接链接 DuckDB 符号——通过函数指针间接调用，实现版本韧性。

## 29.2 Python 绑定：从 C API 到 duckdb.sql() 的包装链

### 调用链

```
duckdb.sql(query) / conn.execute(query)
  → Cython/C 包装器
    → duckdb_query(connection, query, &result)
      → Connection::Query(query)
        → Parser → Binder → Planner → Optimizer → Executor
          → unique_ptr<QueryResult>
        → DuckDBTranslateResult() 包装为 duckdb_result
```

### 多种结果格式

```python
import duckdb
result = duckdb.sql("SELECT * FROM my_table")

result.df()          # → Pandas DataFrame（通过 Arrow 零拷贝互转）
result.fetchnumpy()  # → numpy 数组
result.fetchall()    # → Python 元组列表
result.fetchone()    # → 单个 Python 元组
result.fetchdf_chunk()  # → 流式 DataFrame 块
```

Pandas DataFrame 转换使用 Arrow 作为中间格式：DuckDB DataChunk → Arrow RecordBatch → Pandas DataFrame。零拷贝的关键是 Arrow C Data Interface——数据在进程内以 Arrow 格式传递，无需序列化。

### Relation API

```python
conn = duckdb.connect()
rel = conn.table("my_table")
result = rel.filter("amount > 100").project("user_id, SUM(amount)").execute()
```

Relation API 构建关系表达式树，惰性求值。`execute()` 时转换为 SQL 执行。

## 29.3 WASM 编译：DuckDB-Wasm 的工作原理

### 架构

DuckDB-Wasm 不是简单的"编译到 WASM"——它需要适配浏览器的独特约束：

```
浏览器环境约束：
1. 单线程（无 SharedArrayBuffer 时）→ DuckDB 的 TaskScheduler 退化为单线程
2. 无文件系统 → Emscripten MEMFS 提供虚拟文件系统
3. 内存受限 → BufferManager 在 WASM 线性内存约束下工作
4. 主线程不能阻塞 → 用 Web Worker + Promise 包装同步调用
```

### 扩展加载

```cpp
// src/main/extension/extension_load.cpp
// WASM_LOADABLE_EXTENSIONS 模式下：
// 1. EM_ASM_PTR 调用 JavaScript 的 runtime.whereToLoad() 获取扩展 URL
// 2. XMLHttpRequest 同步下载扩展二进制
// 3. FS.writeFile() 写入 Emscripten 虚拟文件系统
// 4. dlopen() 在内存文件上工作
```

### Arrow 数据交换

DuckDB-Wasm 使用 Arrow C Data Interface 与 JavaScript 生态零拷贝交互：

```
DuckDB-Wasm (C++)
  → ArrowSchema / ArrowArray 结构（C Data Interface）
    → Apache Arrow JS 读取
      → Vega / Observable Plot / Polars 可视化
```

这是 DuckDB-Wasm 在浏览器中实用的关键——列式数据以 Arrow 格式直接传递给 JavaScript，无需 JSON 序列化。

### 异步执行模型

```
浏览器主线程 ←→ Web Worker
                  ↓
              DuckDB-Wasm（同步执行）
                  ↓
              JavaScript Promise 包装
                  ↓
              await db.sql("SELECT ...")
```

DuckDB-Wasm 在 Web Worker 中运行同步的 DuckDB 调用，通过 Promise 将结果异步返回给主线程——避免阻塞 UI。

## 本章小结

DuckDB 的语言绑定策略是"C API + 最小包装"：

| 语言 | 绑定方式 | 特色 |
|------|----------|------|
| C/C++ | 直接链接 | 零开销 |
| Python | C API + Cython | Arrow 零拷贝、Pandas 互操作 |
| R | C API | 类似 Python |
| Java | JNI + C API | JDBC 兼容 |
| Go | cgo + C API | database/sql 接口 |
| Node.js | N-API + C API | 流式结果 |
| WASM | Emscripten | Web Worker + Arrow |

与 SQLite 的对比：SQLite 也有类似的 C API + 语言绑定模式，但 SQLite 的 C API 是面向行的（`sqlite3_step` 一次一行）。DuckDB 的 C API 是面向块的（`duckdb_fetch_chunk` 一次 2048 行）——这是列式执行模型在 API 层面的体现。
