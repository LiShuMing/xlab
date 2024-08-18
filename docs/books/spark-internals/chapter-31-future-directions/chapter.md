# 第 31 章：Spark 的发展方向 — 批流统一、Polyglot 生态与 Lakehouse AI

## 设计动机

本书用 30 章覆盖了 Spark 的各个模块——从 RPC 通信到 Catalyst 优化器、从 Shuffle 三个时代到 Native Engine、从 V1 到 DSv2 到 Iceberg/Delta。每个模块的讲述都围绕一个问题："为什么要有这个东西？它解决了什么问题？"

最后一章转个方向——不再解释已经存在的东西，而是将目光放到未来。如果 Spark 继续演化 5 年（到 2030 年代），它会走向哪里？

这一章不是预测——没有人能预测技术 5 年的精确发展。它是**趋势归纳**——基于 Spark 的开源社区讨论（dev@spark、JIRA Epic、SPIP）、竞争生态（Flink、StarRocks、DuckDB、Snowflake）的走向，和 AI Agent 带来的全新计算模式。

## 趋势归纳

### 31.1 批流一体 — 从"统一 API"到"统一 Runtime"

Spark 的批流统一目前只在 **API 层**——用户写相同的 `df.groupBy().agg()` 代码，批处理和流处理都能运行。但它们的 **Runtime** 是不同的——批处理走过 `FileFormatWriter` + `FileFormatScan`，流处理走过 `MicroBatchExecution` + `StateStore` + `Sink`。

下一个版本（Spark 4.1/4.2+）的方向是把这两个 Runtime **真正统一**：

```
当前: API 统一, Runtime 分离
  df.groupBy("dept").agg(sum("salary"))
  
  批 Runtime: scan → aggregate → write files → DONE
  流 Runtime: scan → aggregate + state store → sink → commit → REPEAT

未来: API 统一, Runtime 统一
  df.groupBy("dept").agg(sum("salary"))
  
  统一 Runtime: scan(input_mode=BATCH or STREAMING)
    → aggregate(state_mode=PERSIST or TRANSIENT)
    → write(output_mode=OVERWRITE or APPEND or UPDATE)
  
  Runtime 根据 input/output/aggregation 的组合自动决策:
    input=STREAMING + state=PERSIST + output=APPEND → Streaming query
    input=BATCH + state=TRANSIENT + output=OVERWRITE → Batch job
    input=STREAMING + state=PERSIST + output=OVERWRITE → Periodic full-refresh streaming
```

统一的 Runtime 意味着 **同一个 QueryExecution 可以处理批和流**——不是在 API 层包装差异，而是在物理算子层面消除差异。Velox 已经在走这个方向——其 `Task::execute()` 的内部实现不区分批或流，只是"读取一批数据 + 算子处理 + 输出结果"。

### 31.2 Polyglot 生态 — Spark 从 JVM 到 Any Language

Spark 的语言支持演化：
```
Spark 1.x: Scala, Java, Python
Spark 2.x: + R
Spark 3.x: + SQL (Spark Connect 使得任意语言都可接入)
Spark 4.x: + Go, Rust, Kotlin (通过 Connect gRPC)
Spark 5.x (推测): 所有 Connect 语言都是 first-class citizen
```

Polyglot 生态的关键推动因素是 **Spark Connect 的 proto 接口**：
```
当前状态:
  Python Client（成熟），Go Client（alpha），Rust Client（实验）
  JVM Client（等于传统 Spark Shell）

2030 年可能的状态:
  - Python Client: primary data science interface
  - Go Client:  cloud infrastructure (K8s operators, API servers)
  - Rust Client: high-performance ETL + WASM sandbox
  - Kotlin Client: Android/edge computing (Spark-on-Mobile? unlikely but tech possible)
  - C++ Client: embedded systems + IoT data ingestion
```

这其中最关键的是 **Go Client**——因为它打开了 Spark 与 K8s 生态的完整融合。K8s Operators 用 Go 编写是标准实践，如果 Operator 可以直接 `import sparkconnect` → `spark.sql("SELECT ...")` → 无需安装 JVM 或 Python interpreter。

### 31.3 Lakehouse AI — Spark 成为 AI 推理的"数据引擎"

Lakehouse AI（Databricks 提出）在 2025 年更多是营销术语，但其技术方向是正确的：

```
Lakehouse AI 的技术路径:
  数据存储层   → Iceberg/Delta 表作为"Feature Store"
                  ├── 特征表: user_features_v3 (Iceberg, snapshot-based time travel)
                  ├── 标签表: training_labels (Delta, append-only)
                  └── 模型元数据: model_metadata (表格式 + model versioning)

  数据处理层   → Spark SQL 用于特征工程 (ETL → feature table)
                  ├── PySpark UDF: custom aggregations, text processing
                  ├── Pandas UDF/TransformWithState: streaming feature computation
                  └── MERGE INTO: incremental feature update

  AI 推理层    → 模型以 Java/Python UDF 形式嵌入 Spark SQL
                  SELECT id, model_predict(features_table) AS prediction
                  FROM feature_table;

  Spark 在 AI 生态中的三重角色:
    1. 特征工程 (ETL → feature table)        ← Spark 的传统强项
    2. 推理加速 (batch inference on GPU)    ← Spark 的新兴角色
    3. 模型监控 (特征漂移检测从 streaming)    ← Spark + Structured Streaming
```

挑战：**GPU 资源的管理**。Spark 擅长 CPU 资源调度（每个 Executor 申请 N 个 core），但对 GPU 的支持仍在早期——`spark.task.resource.gpu.amount` 和 `ResourceProfile` 提供了基础设施，但 streaming GPU inference（每个 batch 分配 GPU 时间片）在 2026 年仍是痛点。

### 31.4 技术栈走向 — 从 Monolith 到微内核

Spark 的技术栈正在从一个"庞大的单体 JVM 应用"演变为"微内核 + 可插拔模块"：

```
Spark 1.x (2014):   Monolith JVM (SparkSubmit → everything in one jar)
Spark 2.x (2016):   Split: Catalyst 独立 + SQL/Streaming/MLlib 分开
Spark 3.x (2020):   DSv2 解耦外部 connector + Spark Connect 分离 Client/Server
Spark 4.x (2025):   Pipelines 独立规划层 + Native Engine plugin + Connect gRPC
Spark 5.x (推测):   Spark 内核可能小于 50MB + 所有算子基于 plugin 选择
                     - Plugin-Aggregation: Tungsten (JVM) vs Velox (C++) vs GPU (CUDA)
                     - Plugin-IO: HadoopFS vs S3A vs GCS vs CXL
                     - Plugin-Execution: MicroBatch vs RealTime vs Batch vs Continuous
```

这个演化的推动力是 **query engine 的 commoditization**——越来越多的引擎（Velox, DataFusion, DuckDB, StarRocks BE）提供了快速的 SQL 执行，Spark 最大的不同变成了 **不 是引擎本身，而是它上面的声明式接口 + 它下面的存储层**。Spark 的未来是把"引擎选择"变成用户的一个配置项——类似数据库的 storage engine 选择。

### 31.5 生态系统的博弈 — 竞争与共生

Spark 在 2026 年面临着一个比 2016 年复杂得多的竞争者格局：

```
每个竞争对 Spark 都构成某一种压力:

  DuckDB (嵌入 式 OLAP)  → 压力: "不用起 Spark 集群，单机就够了"
    回应: Pandas API on Spark + Arrow → 本地 Spark Local 模式
  
  StarRocks (MPP OLAP)  → 压力: "Join 比 Spark 快 3×"
    回应: Native Engine + CBO → 与 StarRocks 的物理算子效率拉近差距
  
  Snowflake (Cloud DW) → 压力: "完全不管理基础设施"
    回应: Spark Connect + K8s → "Serverless Spark with 0 Ops"
  
  Flink (Streaming)    → 压力: "真正的 continuous execution，不是 micro-batch"
    回应: RealTime mode + TransformWithState → 缩小与 Flink 的延迟差距
  
  LLM-based ETL        → 压力: "不需要写代码，描述需求，AI 生成管道"
    回应: SQL Scripting + Variant → 降低"AI 生成管道代码"的复杂度
```

套用一位 Spark 核心贡献者的话："Spark 的成功不是因为它在任何维度都是最快的——而是因为它在 10 亿个维度的综合得分最高。"这两年 Spark 的改进揭示了一个更成熟的方向：不是追赶每个竞争者，而是 **让 Spark 成为各种工具之间的连接点**——你可以用 Python pandas API 操作 S3 上的 Iceberg 数据、用 Go gRPC client 提交 SQL、用 Native Engine 加速物理执行、用 TransformWithState 做流式特征工程。

**Spark 不再是"取代一切"的引擎——它是"连接一切"的平台。**

### 31.6 LLM Agent 作为 Spark 用户 — 新的交互模型

本书的每个章节都有一节"AI 时代反思"，共同构成了一条线索：LLM Agent 如何使用、改变、理解 Spark？归纳这些反思：

**LLM Agent 在 Spark 上最强的能力**（当前）：
- 生成 SQL/DataFrame 代码（`df.groupBy().agg().collect()` 模式）
- 解释已有的查询计划（"这个 query plan 中的 stage-3 在做什么"）
- 发现表格式的元数据失配（"表按 date 分区但查询用 timestamp_utc 过滤"）

**LLM Agent 在 Spark 上最弱的能力**（当前）：
- 定位性能瓶颈的根本原因（"为什么慢？"→ 需要跨 GC log + query plan + YARN 的因果链）
- 调试复杂的物理计划异常（"未预期的 Exchange 节点"→ 需要理解整个 Catalyst 的物理 planning 过程）
- 理解 UDF 的执行开销（"这个 Pandas UDF 每 batch 只有 100 行"→ 需要跨 Python/JVM Arrow 的 visibility）

**这两种能力的差异揭示了一个核心模式**：LLM 擅长"语法层面"的操作（生成代码、解读计划），但在"运行时层面"的深度分析（因果链追踪、跨系统的关联）上显著弱于人类 SRE。这是因为网上有大量关于 Spark API 的文章，但几乎没有关于"为什么某个 Spark query 在凌晨 3 点突然慢了 10×"的分析文章。

**Spark Agent 的终极形态**（推测 2030）：
```
用户: "我的 ETL pipeline 变慢了，帮我查查"
Agent: 自动执行以下步骤:
  1. 从 Spark History Server 拉取最近 100 个 batch 的 Stage 指标
  2. 识别: Stage-2 的 Shuffle Read 时间从 30s → 240s（batch-55 开始）
  3. query YARN RM API → batch-55 同时段内 node-17 有 3 个 MapReduce job
  4. query OS monitoring → node-17 的 disk bandwidth 被 MapReduce 占用
  5. 报告: "batch-55 起 Shuffle 变慢 8×。根因: node-17 的磁盘带宽被
           MapReduce job-8130 和 job-8132 占用。建议 (1) 对 Shuffle 启用
           Celeborn 以解耦计算与 Shuffle 存储，或 (2) 隔离批处理 node pool"
  
  这不是"AI 写代码"——这是"AI 做 ticking diagnosis"。比代码生成高 10 倍价值。
```

### 31.7 数据技术栈的重心下移 — SQL 引擎不再是终点

审视 2006-2030 年的数据技术栈演化：
```
2006-2012:  数据存在哪? → Hadoop HDFS (解决存储)
2012-2018:  数据怎么算? → Spark, Flink, Hive, Tez (解决计算)
2018-2024:  数据怎么组织? → Iceberg, Delta, Hudi (解决表特性)
2024-2030:  数据如何被理解和访问? → AI Agent 通过自然语言访问数据
             底层引擎和存储层变得透明化 → 用户需求转换成查询 → 执行 → 结果
```

SQL 引擎（Spark 执行层）在这个过程中经历了一个"重心的下移"——从"用户接触 Spark 的方式"变成了"AI Agent 连接数据的方式"。Spark 用户不再是"人用 SQL 写查询"，而是"AI Agent 生成 PySpark/Connect proto Plan → Spark 执行"。

这改变了 Spark 的需求：
- 过去需要：更好的 SQL 覆盖率，更快的 Executor
- 未来需要：更标准的 gRPC/Arrow 接口，更丰富的 Plan introspection，更强的 metadat 暴露
  → 因为主要用户不再是 human，而是 AI Agent

Spark 在 AI 时代的未来——不是取代 AI，而是**被 AI 节点调用**。Spark 作为"数据到 AI 的管道引擎"比"SQL 的终端"更接近它未来的定位。

## 结语

本书始于一个 RDD 的分区，终于一个跨越 JVM、C++、Python、Go、gRPC、Arrow、Iceberg、Celeborn、AI Agent 的分布式查询生态。

Spark 的内核是一个分布式查询引擎。但经过 20 年的发展（2009-2029），它已成为一组标准和协议——让不同的语言、不同的存储、不同的计算范式通过统一的接口协同工作。

如果说这本书有一个"结论"的话，那就是：**性能可以堆砌代码来改善，但接口、协议和抽象的选择决定了整个生态的命运。** Spark 团队在每个关键的十字路口都选对了——RDD → DataFrame、Hive → DSv2、Py4J → gRPC、local shuffle → ESS → Celeborn。不是因为每个选择都是完美的，而是因为选择是在"理解问题"而不是"选择流行"上做出的。

这就是为什么这本书要覆盖第一性原理。Spark 不是 31 个章节能涵盖的——它是一个随时间演化的生态。理解它不在于记住每个 API 的名字，而在于理解为什么每个设计存在。当你理解了动机，你的知识的生存期是 20 年——不因为你记得 API，而因为你了解选择和取舍。

---

*本书献给所有试图理解"分布式查询引擎内部究竟发生了什么"的工程师。你们的提问、你们的 code review、你们的 "这个为什么这么慢"——这些问题定义了 Spark 为什么存在。*
