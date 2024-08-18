# 第 30 章：Spark 4.0 关键新特性 — 从 SQL Scripting 到 Variant

## 设计动机

Spark 4.0（2025 年发布）是自 Spark 3.0 引入 Adaptive Query Execution 以来最大的版本跨越。它的主题可以概括为三个词：**声明式、半结构化、低延迟**。

Spark 3.x 用 5 年时间将批处理 SQL 优化到了极限——AQE、DSv2、Columnar Shuffle、Pandas UDF。这些优化的共同特征是"让已有的范式更快"。Spark 4.0 的方向不同——它不是在已有范式上加速，而是**扩展范式本身**：
- 从 SQL → SQL Scripting（让 SQL 能做控制流）
- 从强类型 → Variant（让 SQL 能处理无模式/半结构化数据）
- 从微批 → Real-time（sub-millisecond 延迟）
- 从粗粒度状态 → 多变量状态 + TTL（让流处理更精细）

这些特性不是各自独立的——它们在同一个架构下互相增强。SQL Scripting 可以用 Variant 解析 JSON → MERGE INTO 写到 Iceberg 表 → 同时 Real-time Streaming 监听着同一张表的变更。

## 核心原理

### 30.1 SQL Scripting — 过程式控制流走进 SQL

SQL 是一种声明式语言——你描述"想要什么"，引擎决定"怎么做"。但数据工程中常见的模式（条件写入、循环分批处理、异常路径）在纯 SQL 中难以表达。现有方案是绕道 Python/Scala 脚本来实现控制流，然后在循环体中跑 SQL。

SQL Scripting（SPARK-48400）为 Spark SQL 引入了一套完整的过程式编程结构——直接在内核中执行：

```sql
-- 条件分支
BEGIN
  DECLARE max_date DATE DEFAULT CURRENT_DATE();
  
  IF max_date > '2025-01-01' THEN
    INSERT INTO recent_orders
    SELECT * FROM orders WHERE order_date > max_date - INTERVAL 30 DAYS;
  ELSE
    INSERT INTO archived_orders
    SELECT * FROM orders WHERE order_date <= '2025-01-01';
  END IF;
END;

-- 循环分批处理
BEGIN
  DECLARE processed INT DEFAULT 0;
  DECLARE batch_size INT DEFAULT 10000;
  
  WHILE processed < 1000000 DO
    INSERT INTO batch_results
    SELECT * FROM big_table LIMIT batch_size OFFSET processed;
    SET processed = processed + batch_size;
  END WHILE;
END;

-- 异常处理
BEGIN TRY
  INSERT INTO target_table SELECT * FROM source WHERE condition = 'risky';
END TRY
BEGIN CATCH
  INSERT INTO error_log VALUES ('Failed to insert risky data', CURRENT_TIMESTAMP());
END CATCH;
```

实现原理：SQL Scripting 在 Catalyst 解析层（ANTLR）被展开为特殊的 `ScriptingCommand` 逻辑计划节点。每个 `IF`/`WHILE`/`BEGIN` 块被拆分为一个嵌套的 `LogicalPlan` 子树的序列——这些子树按顺序被 `SparkConnectPlanner`（或传统 DataFrame 执行路径）逐个执行。

关键的实现细节：
- **变量绑定**（`DECLARE`）：通过 session 临时表存储（`spark_temp_scripting_vars`）
- **循环迭代**（`WHILE`）：校验条件是否为 True → 计算体子树 → 递增 → 重复校验 → 直到条件为 False
- **异常处理**（`TRY/CATCH`）：内层子树抛异常 → 不终止查询 → 执行 CATCH 子树

SQL Scripting 不是完整的存储过程引擎（它不编译成函数，不能跨 session 持久化），但涵盖 80% 的日常控制流需求。

### 30.2 Variant — 半结构化数据的 First-Class 类型

现代数据中有大量"半结构化 JSON 字符串"——Kafka 主题中塞满 `{"user_id": 123, "event": "click", "properties": {"button": "buy", "page": 5, "tags": ["sale", "new"]}}`。传统做法是：
- 存成 STRING → 每次用 `get_json_object()` 解析 → 慢 + 重复解析
- 存成 STRUCT → Schema 必须预先定义 → 格式有变化就崩溃
- 存成 MAP → 深层嵌套无法表达

Variant（SPARK-48401）是 Spark 4.0 的新原生类型，**将 JSON 数据和它的元数据（结构、类型）作为一个二进制编码单元存储**：

```
Variant 的二层编码:
  Metadata segment:
    ├── field_names: ["user_id", "event", "properties", ...]
    ├── field_types: [LONG, STRING, OBJECT, ...]
    ├── field_offsets: [0, 8, 16, ...]
    └── total_size: 256 bytes

  Value segment (columnar binary):
    ├── user_id:    7B 00 00 00 00 00 00 00  (64-bit LE = 123)
    ├── event:      05 63 6C 69 63 6B 00 00   (string "click")
    └── properties: <nested metadata + value recursively>

与 STRING '{"user_id": 123, "event": "click"}' 对比:
  STRING: 35 bytes JSON text → 每次使用要重新解析 → 遍历 JSON 树
  Variant: 20 bytes binary → 不需要重新解析 → 直接提取字段 → 2-5× 快
```

Variant 的存取操作：
```sql
-- 创建包含 Variant 列的表
CREATE TABLE events (
  id LONG,
  payload VARIANT
);

-- 通过 variant_get() 解析字段 (零文本解析成本):
SELECT 
  variant_get(payload, '$.user_id', 'long') AS user_id,
  variant_get(payload, '$.event', 'string') AS event,
  variant_get(payload, '$.properties.button', 'string') AS button
FROM events;

-- Variant 的 MERGE INTO (Schema Evolution):
MERGE INTO customer_profiles t
USING (
  SELECT 
    variant_get(payload, '$.user_id', 'long') AS user_id,
    variant_get(payload, '$.new_field', 'string') AS new_field
  FROM events
) s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET t.new_field = s.new_field;
-- Spark 自动为 target table 添加 new_field 列 (schema evolution)!
```

Variant 与 Iceberg 的 `schema_on_read` 配合使用特别有效——数据以 Variant 二进制存储，Iceberg 的 Time Travel 期间不同类型映射由 Variant 的元数据段保证。

### 30.3 Streaming Symmetric Join V4 — 流式 Join 的状态优化

第 25 章中介绍的 `StreamingSymmetricHashJoinExec` 在 Spark 4.0 经过了重大改进（V4）：

```
V1-V3 (Spark 2.3-3.5):
  - 两侧 state store 全量存储在 RocksDB
  - 每个 join key match 都产生一次 state 查询
  - Watermark 清理通过 per-key version check
  
V4 (Spark 4.0):
  - Block-based state management: 侧边 data 按 partition block 组织
    而非 per-key → 减少 RocksDB 的 random access
  - Compressed state representation: 用列式编码存储 join state
    → 内存占用降低 30-50%
  - Adaptive state caching: 活跃 key 的 state 缓存在 JVM heap
    → 命中率 > 90% 时 RocksDB 访问量降低 10×
  - Parallel state cleanup: 多个线程并行处理 watermark
    → watermark 清理的延迟降低 3-5×
```

### 30.4 MERGE INTO Schema Evolution — 自动演化 target 表结构

传统 `MERGE INTO` 的 target 表的 schema 必须是"已知且固定"的。Spark 4.0 支持 **MERGE INTO 驱动的 Schema Evolution**：

```sql
MERGE INTO sales_summary AS target
USING daily_sales AS source
ON target.date = source.date
WHEN MATCHED THEN UPDATE SET
  target.total = source.total,
  target.new_category_total = source.new_category_total  -- 新列!
WHEN NOT MATCHED THEN INSERT *;
-- Spark 自动: ALTER TABLE sales_summary ADD COLUMN new_category_total DOUBLE;
-- 然后执行正常的 MERGE
```

Schema Evolution 的限制：
- 只允许添加新列，不允许移除或重命名现有列
- 新列必须是 NULL 可容的类型（允许有 NULL 值）
- 冲突检测：如果新列已在 target 中存在但类型不一致 → 报错而不是尝试转换

### 30.5 TransformWithState — 多状态变量 + TTL 的有状态处理框架

第 25 章详细介绍了 `TransformWithState`。在 Spark 4.0 的语境中总结：

```
API 特性:
  - ValueState[T]： 单值状态
  - ListState[T]：  有序列表状态
  - MapState[K,V]： 键值映射状态
  - TimerState：    支持 processing time 和 event time 定时器
  - TTL：           每个 state 变量独立的时间到期策略

RocksDB Column Family 隔离:
  ValueState   → CF: "__values__"
  ListState    → CF: "__lists__"
  MapState     → CF: "__maps__"
  TimerState   → CF: "__timers__"

TTL 清理:
  RocksDB compaction filter 在 compaction 时扫描 column family
  → 识别 key 的 TTL 是否过期 → 自动删除 → 不需要用户代码介入
```

这个 API 是 Spark 4.0 中流处理的最大升级——把状态管理从"暗藏在聚合内部"提升为"用户可组合的基础设施"。

### 30.6 Real-Time Mode — 毫秒以下的流处理延迟

`RealTimeTrigger` 和 `RealTimeStreamScanExec` 构成了 Spark 4.0 的低延迟流处理方案：

```
MicroBatch (默认):          latency = batch_interval + processing_time
                             最小 ≈ 100ms
  
RealTime (Spark 4.0):      latency = processing_time
                             最小 ≈ 1ms (取决于 source 的可用延迟)

区别:
  MicroBatch: 等待一个完整的 batch interval → source 的所有 partition 都就绪 → 执行
  RealTime:   不等待 interval, source 的任何 partition 就绪 → 立即执行部分 batch
              → 丢失的 partition 在下个 batch 补上
              → end offset 不是完整的数据范围, 而是"当前就绪的 partition 范围"
  
代价:
  - 不能保证每个 batch 的 end offset 单调递增
  - Progress report 中的 end offsets 可能不完整
  - Watermark 计算更复杂 (需要考虑"部分 partition 未到达"的情况)
```

### 30.7 Collations — 字符串排序的语言学感知

Spark 长久以来都用**二进制排序**（UTF-8 byte order）做 `ORDER BY string_col`。这意味着 `ORDER BY` 的结果不遵循任何人类语言的排序规则：

```sql
-- 二进制排序 (Spark 3.x):
SELECT * FROM names ORDER BY name;
-- result: "Étienne", "eager", "Éclair" (É的UTF-8编码 > e的UTF-8编码)

-- 法语排序 (Spark 4.0):
SELECT * FROM names ORDER BY name COLLATE fr_FR;
-- result: "eager", "Éclair", "Étienne"
-- 因为法语 collation 规则中 É 排在 e 后的位置
```

Collation 的支持通过 ICU4J 库实现在 Spark 内部的 StringType 上。关键实现点是 `CollationAwareUTF8String`——一个在 UTF-8 字节上附加了 collation 排序函数的包装器。

### 30.8 其他关键新特性

**XML 文件格式支持**：
```sql
SELECT * FROM xml.`/data/config.xml`;
-- InferSchema option → 自动推断 XML 结构 → Variant 或 STRUCT 列
```

**Multi-Delimiter CSV**：
```sql
SELECT * FROM csv.`/data/file.csv` WITH (sep='|||', multiDelimiter=true);
```

**Scala 2.13 升级**：
Spark 4.0 是最后一个支持 Scala 2.12 的版本，默认已用 Scala 2.13 编译。这对库依赖的影响主要在于 Jackson、Guava 等使用了新版本。

**Connect → Pipelines → Native 的全链路集成**：
第 26-28 章的三个技术栈在 Spark 4.0 中首次集成了完整的链路：
- Python Client (Connect gRPC) → Plan proto → Server 解析
  → Pipeline Graph (声明式依赖) → Native Engine Plugin 注入 → Velox/Photon 执行

这是一条 "Python 代码 → gRPC → 声明式图 → Native C++ 引擎 → NVMe 存储" 的完整路径——从最顶层的用户 API 到最底层的硬件指令全部打通。

**Variant Extraction Pushdown**：
在 DSv2 的 `ScanBuilder` 中新增 `SupportsPushDownVariantExtractions`——当 scan 后面跟了 `variant_get(payload, '$.field1')` 这类操作时，扫描可以直接下推到 Parquet reader，只读取需要的 Variant 字段而非全部二进制数据。

**Streaming MERGE INTO 的改进**：
- 支持 `WHEN NOT MATCHED BY SOURCE` 子句
- Deletion Vector 自动处理（不需要全量重写原始文件）
- Source-side 的 watermark 推进用于清理 inactive state

## 关键代码片段

### 示例：SQL Scripting IF-THEN-ELSE 的执行

```scala
// SparkConnectPlanner.processScriptingCommand (简化):
case IfElse(condition, thenBody, elseBody) =>
  val condDF = evaluateExpression(condition)  // 执行条件表达式
  val condResult = condDF.collect().head.getBoolean(0)  // 获取 bool 结果
  
  if (condResult) {
    thenBody.foreach(cmd => executeScriptingCommand(cmd))
  } else {
    elseBody.foreach(cmd => executeScriptingCommand(cmd))
  }
```

### 示例：Variant 存储的二进制格式

```
对于 JSON: {"a": 1, "b": "hello"}
Variant Binary (简化):
  [header: version=1, flags=0]
  [metadata: num_fields=2]
  [field 0: name="a", offset=0, type=INT64]
  [field 1: name="b", offset=8, type=STRING(len=5)]
  [values: 01 00 00 00 00 00 00 00 | 05 68 65 6C 6C 6F 00 00]
            ^-- 1 (int64)              ^-- "hello" (5 chars + 2 bytes pad)
```

## 硬件视角

**Variant 的缓存友好性**：

Variant 二进制格式把字段的 metadata 和 values 分开存储，对 CPU cache 非常友好：
```
STRING JSON column:    读取 1 个字段  → 扫描整个 JSON 字符串 (~100 bytes)
                        → evict cache lines of other data → cache miss on next column

VARIANT column:        读取 1 个字段  → 只访问 metadata segment (8-16 bytes)
                        + value segment (specific offset range)
                        → 不 pollute cache lines of unaccessed fields
```

在高并行度的查询（100+ 并发扫描同一张 Variant 表）中，这种 cache 行为的差异可能导致 **30-50% 吞吐差异**——因为 L2/L3 cache 中的有效数据密度不同。

**SQL Scripting 的 Statement-at-a-Time 执行模型**：

SQL Scripting 不是编译成一个执行计划——每个 `IF`/`WHILE` 等语句是**独立的** Spark Job。这意味着：
```
BEGIN
  WHILE i < 100 DO
    INSERT INTO t SELECT * FROM s WHERE part = i;
  END WHILE;
END;
```

这个循环是 100 个独立的 Spark Jobs——每个 Job 都有 Job 启动开销（~200ms Driver 处理时间）。Pipeline 执行模式下 Job 启动开销占总时间 50%+，而 single-statement 模式下可以忽略。对于高频循环（>100 次），这推动了"将循环内联化为一个 batch plan"的优化需求——尚未在 Spark 4.0 中落地。

## AI 时代反思

Spark 4.0 的新特性中最吸引 AI Agent 的无疑是 **SQL Scripting** 和 **Variant**。

**SQL Scripting** 让 AI Agent 生成数据管道代码时不用再"跳出 SQL → Python → 回到 SQL"。Agent 可以生成完整的纯 SQL 脚本——包含条件、循环、异常处理。这对代码生成的简化很显著：LLM 在"段落间一致性"方面远弱于"段落内一致性"——所以一个完整的 polyglot（SQL + Python + SQL）管道相比一个纯 SQL Scripting 管道更 buggy。

**Variant** 通过消除"JSON string → parse → typed column"的转换步骤，减少了 LLM 需要生成的代码量。传统方案中 LLM 需要生成：`get_json_object(payload, '$.a.b.c')`、CAST、fallback 默认值、NULL 处理。Variant 的方案：`variant_get(payload, '$.a.b.c', 'string')`——一条语句，零重复解析，内置 NULL 处理。

更重要的是，**Variant 的类型推断了 AI Agent 的 schema 需求**。当 LLM Agent 发现用户在查询 Kafka JSON 数据时，它不需要问"a.b.c 是什么类型？需要 CAST 吗？"——Variant 的 `variant_get()` 在二进制层已包含类型信息，可以直接提取。这降低了一层 AI-human 交互的复杂度。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/api/src/main/scala/org/apache/spark/sql/scripting/SqlScriptingParser.scala` | SQL Scripting ANTLR 解析器 | |
| `sql/connect/server/src/main/scala/.../planner/SparkConnectPlanner.scala` | SQL Scripting 的 distribute 执行，processScriptingCommand | |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/types/VariantType.scala` | VariantType，Variant 的 Catalyst 类型定义，metadata+value 编码 | |
| `common/variant/src/main/java/org/apache/spark/variant/VariantVal.java` | VariantVal Java 包装，二进制格式解析 | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/read/SupportsPushDownVariantExtractions.java` | DSv2 Variant Pushdown 接口 | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/catalyst/collations/CollationFactory.java` | Collation 创建，ICU4J 集成 | |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/collations/CollationAwareUTF8String.scala` | CollationAwareUTF8String，collation-aware 字符串比较 | |
| `sql/core/src/main/scala/.../execution/streaming/RealTimeStreamScanExec.scala` | RealTimeStreamScanExec，低延迟扫描算子 | |
| `sql/core/src/main/scala/.../runtime/RealTimeModeAllowlist.scala` | RealTime 模式白名单（兼容的 Source/Sink 算子） | |
| `sql/core/src/main/scala/.../stateful/transformwithstate/ttl/TTLState.scala` | TTLState，时间到期策略（global/event_time/processing_time） | |
| RPC 定义在 `sql/connect/common/src/main/protobuf/spark/connect/base.proto` | RealTimeTrigger, SqlCommand, MergeAction 等的 proto 定义 | |
