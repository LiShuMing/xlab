# 第 27 章：Pipelines — DataFrame DAG 的声明式编排

## 设计动机

数据工程中有一类常见的"富依赖性"难题：你有 5 张源表（MySQL CDC、Kafka Event、S3 Logs、Hive Dimension、REST API），它们需要被清洗、合并、聚合，最终输出到 3 个目标位置（BI Dashboard 表、ML 特征表、KPI Report）。这些数据流之间有复杂的依赖性——"特征表依赖清洗后的用户画像，用户画像又依赖 Event 和 Dimension 的 Join"。

用传统方式解决这个难题有两种路径：

1. **工作流调度器（Airflow/Dagster）**：每个步骤是一个独立的 Spark 作业，依赖表达在 DAG 文件的 task 级别。问题：步骤之间需要将中间结果物化到 HDFS/S3 → 下一个步骤再读回来 → I/O 浪费严重；且同一张"表"的多个步骤可能因调度窗口错位而产生不一致。

2. **手动 Python 串联**：写一个长脚本，把所有 DataFrame 操作串起来。问题：依赖关系隐含在代码执行顺序中，不可发现、不可检查、不可增量更新。

Spark Pipelines（Spark 4.0+，通过 Spark Connect 的 proto 协议暴露）提供了第三种路径：**声明式 Dataflow Graph**。用户用 SQL 或 Python 定义"哪些表/视图存在"以及"每个表的数据从哪来"，引擎负责规划依赖、并行执行、增量更新。

```
传统 ETL Pipeline:                    Spark Pipelines:
  (Python script)                       (Declarative Graph)
  df1 = read("A")                       CREATE TABLE target_a AS
  df2 = read("B")                         SELECT ... FROM source_1 JOIN source_2;
  df3 = df1.join(df2, ...)
  df3.write.mode("overwrite")           CREATE TABLE target_b AS
  df4 = read("C")                         SELECT ... FROM target_a JOIN source_3;
  df5 = df3.join(df4, ...)
  df5.write.mode("overwrite")           → 引擎自动识别:
  ...                                       a 依赖 source_1, source_2
  [依赖关系隐藏在代码顺序中]                   b 依赖 a, source_3
                                            并行执行 a + 不需要等待 b 的 source_3 读取
```

## 核心原理

### 27.1 Dataflow Graph — 元素、依赖与拓扑

Pipelines 的核心数据结构是 `DataflowGraph`——一个有向无环图（DAG），其中节点是以下几种元素：

```
Graph Elements:
  ┌── Table (物理表) —— 持久化在 catalog 中
  ├── MaterializedView (物化视图) —— 增量或全量刷新，持久化
  ├── TemporaryView (临时视图) —— 当前 pipeline run 的生命周期内存在
  ├── Sink (输出端) —— 数据写入外部系统（不持久化到 catalog）
  └── Flow (数据流) —— 从一个或多个 source/table 到一个目标 table/sink 的转换
        ├── ONCE Flow —— 只在 full_refresh 时运行一次（如 backfill）
        ├── STREAMING Flow —— 持续增量更新
        └── BATCH Flow —— 每次 run 时全量计算

依赖关系:
  Flow.target = Table/Sink
  Flow.sources = [Table, View, Source] → 由此推导 DAG 的拓扑顺序
```

每个 `Flow` 包含一个 `FlowFunction`——一个以 `(allInputs, availableInputs, configuration, queryContext, queryOrigin)` 为参数的 lambda，返回 `(usedInputs, DataFrame)`。这本质上是一个**延迟求值的 DataFrame 工厂**——只有等到 pipeline run 时，FlowFunction 才真正被调用。

```scala
// FlowFunction 的合约:
trait FlowFunction {
  def call(
      allInputs: Set[TableIdentifier],
      availableInputs: List[ResolvedInput],
      configuration: Map[String, String],
      queryContext: QueryContext,
      queryOrigin: QueryOrigin
  ): (Set[TableIdentifier], DataFrame)
  //   ^-- 实际使用的 inputs    ^-- 转换表达式
}
```

### 27.2 Pipeline 执行模型 — 从 Graph 到 Incremental Update

一个 Pipeline Run 的完整流程：

```
StartRun(graph_id, refresh_selection, full_refresh_selection, storage):
  
  Phase 1: Analysis
    ├── 解析所有 Flow 定义 → 确定依赖 DAG
    ├── 推断每个 Table 的 Schema（如果未显式指定）
    ├── 验证依赖的完整性（无缺失 input、无 DAG 循环）
    └── 确定执行批次: 哪些 table 需要 full_refresh，哪些增量更新
  
  Phase 2: Execution (拓扑顺序)
    for each batch in topological_order(graph, refresh_selection):
      并行执行 batch 中所有独立的 Flow:
        FlowExecution.execute(flow, queryContext):
          1. 调用 FlowFunction.call() → 获取 DataFrame
          2. 应用 schema evolution (合并新旧 schema)
          3. 写入 target table (full_refresh → overwrite, incremental → append/merge)
          4. 报告 progress event
  
  Phase 3: Logging & Cleanup
    ├── 记录 run metadata (duration, rows_written, errors)
    ├── 清理过期 snapshot → temp views 生存期结束
    └── 如果 dry_run=true → 到此为止，不真正写数据
```

**增量 vs 全量刷新的决策**：
- `full_refresh=true`：删除 target table 的所有已有数据 → 重新计算 → 写入
- `full_refresh=false`（默认）：尽可能增量更新——如果 target table 已存在且 schema 不变，只处理新增/变更的数据
- `ONCE` flow：只在 full_refresh 时执行一次（适用于一次性 backfill 或历史数据修正）

### 27.3 StreamingFlow vs CompleteFlow — 两种执行范式

Pipelines 区分两种 Flow 类型，对应不同的执行策略：

```
StreamingFlow:
  - FlowFunction 返回 streaming DataFrame (readStream → ...)
  - 执行: 启动一个 Structured Streaming query → 持续运行
  - 适用: 低延迟的增量更新（CDC、实时聚合）
  - 生命周期: StartRun 启动 → 持续运行 → 直到 graph 被 drop 或 run 被 cancel

CompleteFlow (BatchFlow):
  - FlowFunction 返回 batch DataFrame (read → ...)
  - 执行: 单次 Spark Job → 完成后该 flow 结束
  - 适用: 定时全量计算、每日报表
  - 生命周期: batch start → compute → finish

混合 Graph 示例:
  CREATE STREAMING TABLE live_metrics AS
    SELECT ... FROM kafka_events;        ← StreamingFlow (持续运行)
  
  CREATE TABLE daily_report AS
    SELECT ... FROM live_metrics
    WHERE date = CURRENT_DATE();          ← CompleteFlow (每天跑一次)
```

### 27.4 Pipeline SQL 语法 — 声明式定义

Pipelines 引入了一种扩展 SQL 语法用于声明 pipeline 结构：

```sql
-- 创建 streaming table (物化的、持续更新的表)
CREATE STREAMING TABLE orders_clean
PARTITIONED BY (order_date)
AS
  SELECT o.*, c.region
  FROM kafka_orders o
  JOIN dim_customers c ON o.customer_id = c.id
  WHERE o.amount > 0;

-- 创建 materialized view (增量刷新)
CREATE MATERIALIZED VIEW hourly_sales
AS
  SELECT window(event_time, '1 hour') AS hour,
         product_id,
         SUM(amount) AS total_sales,
         COUNT(*) AS order_count
  FROM orders_clean
  GROUP BY window(event_time, '1 hour'), product_id;

-- 创建 temporary view (仅在当前 run 生命期内存在)
CREATE TEMPORARY VIEW debug_filtered AS
  SELECT * FROM orders_clean WHERE amount > 10000;

-- 定义 ONCE flow (仅在 full refresh 时执行)
CREATE OR REFRESH STREAMING TABLE backfill_corrections
AS
  SELECT * FROM old_orders WHERE status = 'FIXED';  -- once = true
```

这些 SQL 语句通过 `DefineSqlGraphElements` RPC 提交——Server 端的 `SqlGraphRegistrationContext` 负责解析 SQL 并注册到 `DataflowGraph`。

### 27.5 Python DAG 定义 — API 级别的 Graph 构建

除了 SQL，Pipelines 也支持通过 Python API 显式构建 Graph：

```python
from pyspark.sql.pipelines import DataflowGraph

graph = DataflowGraph("my_pipeline")

# 定义输出
graph.define_output("processed_orders", output_type="TABLE")

# 定义 flow (用于从源到目标的转换)
graph.define_flow(
    flow_name="clean_orders",
    target="processed_orders",
    func=lambda: spark.readStream.table("raw_orders")
        .filter("amount > 0")
        .join(spark.table("dim_customers"), "customer_id")
)

# 执行
graph.start_run(storage="/pipelines/checkpoint", full_refresh=False)
```

API 背后的 proto 传递路径是：Python → `DefineOutput` RPC → Server 注册 Table → `DefineFlow` RPC → Server 注册 Flow → `StartRun` RPC → Server 执行。

### 27.6 与 Delta Live Tables（DLT）的关系

Spark Pipelines 在概念上与 Databricks 的 Delta Live Tables 高度重合，但有一个关键区别：

| 维度 | Delta Live Tables (Databricks) | Spark Pipelines (OSS) |
|------|-------------------------------|----------------------|
| 发布形式 | Databricks 专有服务 | Apache Spark 开源 (4.0+) |
| 接口 | DLT SQL/Python DSL | Spark Connect gRPC proto |
| 执行环境 | Databricks 托管 Cluster | 任意 Spark 部署 (K8s, YARN, Standalone) |
| 期望/验证 | 内置 Expectations DSL | 通过 UDF 实现检查 |
| Schema Evolution | 自动合并 | 通过 SchemaMergingUtils |
| 监控/日志 | Databricks UI | PipelineEvent 流 (通过 gRPC stream) |

Pipelines 是 DLT 概念的"开源等价物"——不提供 Databricks 的全套托管体验，但提供了所有核心的声明式编排能力，且通过 Spark Connect 的 gRPC 架构实现了语言无关的 API 暴露。

### 27.7 Pipeline Events — 进度与状态的 gRPC 流

Pipeline 在执行过程中产生一系列 `PipelineEvent` 消息——通过 gRPC server-streaming 发送给客户端：

```
PipelineEvent 类型:
  - RunProgress: run 状态变更 (RUNNING → COMPLETED / FAILED / CANCELED)
  - FlowProgress: 单个 flow 的 progress (读行数, 写行数, duration)
  - SchemaEvolution: schema 变更通知 (列增加/移除/类型变更)
  - ExpectationViolation: 数据质量校验失败 (行数, 规则描述)
  - Error: flow 执行失败 (exception message, stack trace)
```

这些 event 通过 `PipelineEventSender` 和 gRPC 的 `StreamObserver[PipelineEventResult]` 机制流式输出——客户端在发起 `StartRun` 时可以同时建立一个 event stream 的 pull 连接来监听进度。

### 27.8 Checkpoint & 状态管理

Pipelines 的 `storage` 参数指定 checkpoint 位置。与 Structured Streaming 的 checkpoint 目录类似，但更上层：

```
storage/
  ├── graph_metadata/     ← graph 定义 (哪些 table/view/flow 存在)
  ├── runs/
  │     └── <run_id>/
  │           ├── run_metadata (start_time, end_time, status)
  │           ├── flow_checkpoints/ (每个 flow 的 Structured Streaming checkpoint)
  │           └── events/ (event log)
  └── snapshots/
        └── <graph_version>/ (graph 定义的快照)
```

这会允许 pipeline 在 driver 崩溃后恢复——重用已完成的 flow 结果 + 只执行未完成的 flow。

## 关键代码片段

### 示例：Dataflow Graph 的增量执行批次划分

```
拓扑分析: graph = {
  source_1 → Flow-A → table_a
  source_2 → Flow-B → table_b
  table_a + table_b → Flow-C → table_c
  table_a → Flow-D → table_d
}

批次划分 (topological order with parallelism):
  Batch-0: [Flow-A, Flow-B]  ← 并行执行
  Batch-1: [Flow-C, Flow-D]  ← 并行执行 (依赖 Batch-0 完成)

refresh_selection = [table_c]:
  → 需要执行的 flow: [Flow-A, Flow-B, Flow-C]
  → 跳过 Flow-D (不需要 table_d)
  → 如果 table_a 已存在且无 schema 变更 → Flow-A 可缩短为增量更新
```

### 示例：FlowFunction 的延迟求值

```scala
// GraphExecution 调用 FlowFunction:
val (usedInputs, df) = flow.func.call(
    allInputs = graph.allTableIdentifiers,
    availableInputs = graph.getResolvedInputsForFlow(flow),
    configuration = flow.sqlConf,
    queryContext = QueryContext(currentCatalog, currentDatabase),
    queryOrigin = QueryOrigin(flow.sourceCodeLocation, QueryOriginType.FLOW_DEFINITION)
)

// 关键: call() 在 startRun 时才被调用
// → Flow 定义时只存储 lambda, 不执行任何 Spark job
// → 这允许 schema 变更在 run 时被发现和处理
```

## 硬件视角

**多 Flow 并行执行的 I/O 竞争**：

当 Pipeline 的 Batch-0 同时执行 5 个 Flow、每个 Flow 都在从 HDFS/S3 读取源表时，真正的 I/O 并行度由 Executor 数和 Disk/Network Bandwidth 双重决定：

```
场景: Batch-0 有 5 个独立的 Flow，每个读取 1TB 的 Parquet 源表

单 Executor:
  - 5 个 Flow 在同一个 Executor 内串行执行（Spark Scheduling）
  - 磁盘带宽: 2GB/s → 5TB / 2GB/s = 2500 秒（~42 分钟）

50 Executor (每 Flow 10 个):
  - 每个 Flow 共享 10 个 Executor → 10 并行度
  - 网络带宽（S3）: 10GbE = 1.25GB/s → 1TB / 1.25GB/s = 800 秒 per Flow
  - 但 5 Flow 同时争用网络 → 总吞吐 = 5 × 1TB / 1.25GB/s ≈ 66 分钟
  - 如果 YARN 调度器将 50 Executor 分散到不同网络网段 → 总吞吐上限提升
```

这就是为什么在生产中，Pipelines 的自定义 "flow 到 executor 的分配" 比默认的公平调度更高效——通过将互不竞争的 Flow 分配到不同的物理网段/磁盘路径。

**Schema Evolution 的存储开销**：

当 `SchemaMergingUtils` 将新 schema 合并到已存在的 Table 时（如新增一个列），Parquet 文件会因"旧文件缺少新列"而需要处理 NULL fallback——这不是存储开销（NULL 在 Parquet 中基本是免费的），但会对扫描性能产生影响——每行都需要 NULL check。如果 schema 频繁演变，定期 full_refresh 来统一所有 Parquet 文件的 schema 会提升读取性能。

## AI 时代反思

Declarative Pipeline 是 AI Agent 最适合操作的抽象级别之一。原因很简单：AI Agent 不擅长管理执行顺序（"先做 A 再做 B"是规划问题），但它擅长理解数据流（"X 来自 Y 和 Z 的 Join，这意味着 X 同时依赖 Y 和 Z"）。Pipelines 的声明式 DAG 正好降低了 AI Agent 的操作难度——Agent 只需要定义依赖关系，引擎负责执行。

更进一步，LLM 可以辅助构建 Pipeline 的"依赖发现"：
```
用户: "我有 tables: orders, customers, products, inventory。
     我需要: 1) 每小时的销售汇总 2) 低库存警告 3) 客户终身价值评分"

Agent: 
  1. 分析依赖:
     - hourly_sales: depends on orders (+ products for product name)
     - low_stock_alert: depends on inventory (+ orders for demand rate)
     - clv_score: depends on orders + customers
  
  2. 生成 Pipeline Graph:
     CREATE FLOW hourly_sales ... FROM orders JOIN products ...
     CREATE FLOW low_stock_alert ... FROM inventory JOIN orders ...
     CREATE FLOW clv_score ... FROM orders JOIN customers ...
  
  3. 建议: "这三个输出之间没有相互依赖 → 可以完全并行执行"
```

这种 "需求 → DAG 依赖图 → Pipeline 定义" 的转换是 LLM 的强项（模式匹配 + 领域知识），而 "DAG → 物理执行" 是 Spark 引擎的强项。两者分工清晰——且 Pipeline 的声明式 proto 接口正好是这两个世界之间的边界。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/connect/common/src/main/protobuf/spark/connect/pipelines.proto` | PipelineCommand 定义，CreateDataflowGraph/DefineOutput/DefineFlow/StartRun/DropDataflowGraph 等 RPC，PipelineEvent 流 | ~33 (message PipelineCommand) |
| `sql/pipelines/src/main/scala/.../pipelines/graph/Flow.scala` | Flow trait，FlowFunction 合约，QueryContext 定义，延迟求值模式 | ~38 (trait Flow), ~65 (trait FlowFunction) |
| `sql/pipelines/src/main/scala/.../pipelines/graph/FlowExecution.scala` | FlowExecution，单个 Flow 的执行逻辑，schema evolution 合并 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/GraphExecution.scala` | GraphExecution，拓扑排序 + 批次执行，增量/全量刷新决策 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/FlowAnalysis.scala` | FlowAnalysis，依赖分析，schema 推断，DAG 验证 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/FlowPlanner.scala` | FlowPlanner，Flow 到 Spark Plan 的映射 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/DataflowGraph.scala` | DataflowGraph，Graph 元素注册与管理，元素间依赖 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/elements.scala` | GraphElement 基础 trait，Table/View/Sink/Flow 等类型定义 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/DatasetManager.scala` | DatasetManager，Table 生命周期管理（创建/修改/drop） | |
| `sql/connect/server/src/main/scala/.../pipelines/PipelinesHandler.scala` | Spark Connect PipelinesHandler，proto PipelineCommand 分发 | ~42 (object PipelinesHandler) |
| `sql/connect/server/src/main/scala/.../pipelines/DataflowGraphRegistry.scala` | DataflowGraphRegistry，graph_id → DataflowGraph 映射，session 级别的 graph 管理 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/SqlGraphRegistrationContext.scala` | SqlGraphRegistrationContext，SQL 解析 → Graph 元素注册 | |
| `sql/pipelines/src/main/scala/.../pipelines/logging/FlowProgressEventLogger.scala` | PipelineEvent 日志，FlowProgress 记录 | |
| `sql/pipelines/src/main/scala/.../pipelines/graph/PipelineUpdateContextImpl.scala` | PipelineUpdateContext，refresh_selection + full_refresh_selection 的实现 | |
| `sql/pipelines/src/main/scala/.../pipelines/util/SchemaInferenceUtils.scala` | Schema 推断工具 | |
| `sql/pipelines/src/main/scala/.../pipelines/util/SchemaMergingUtils.scala` | Schema 合并（schema evolution），新旧 schema 的联合 | |
