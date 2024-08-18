# 第13章：Physical Plan —— 从逻辑到物理

> 逻辑计划回答"做什么"，物理计划回答"怎么做"。同一个 `LogicalComparisonJoin` 可以映射为 HashJoin、MergeJoin 或 NestedLoopJoin——这个选择决定了查询的执行效率。

## 13.1 PhysicalPlanGenerator：逻辑→物理的翻译器

```cpp
// src/execution/physical_plan/physical_plan_generator.cpp
unique_ptr<PhysicalOperator> PhysicalPlanGenerator::CreatePlan(unique_ptr<LogicalOperator> op) {
    // 根据 LogicalOperatorType 分派到不同的 CreatePlan 重载
    switch (op->type) {
        case LogicalOperatorType::LOGICAL_GET:
            return CreatePlan(op->Cast<LogicalGet>());
        case LogicalOperatorType::LOGICAL_FILTER:
            return CreatePlan(op->Cast<LogicalFilter>());
        case LogicalOperatorType::LOGICAL_COMPARISON_JOIN:
            return CreatePlan(op->Cast<LogicalComparisonJoin>());
        // ... 50+ 种映射
    }
}
```

### 映射策略

逻辑算子到物理算子的映射不是 1:1 的——有些逻辑算子有多种物理实现：

| 逻辑算子 | 物理实现 | 选择条件 |
|----------|----------|----------|
| LogicalComparisonJoin | PhysicalHashJoin | 默认（等值条件） |
| | PhysicalPiecewiseMergeJoin | 非等值范围条件 |
| | PhysicalNestedLoopJoin | 任意条件 |
| | PhysicalIEJoin | 多个范围条件 |
| | PhysicalCrossProduct | 无条件 Join |
| LogicalAggregate | PhysicalHashAggregate | 默认分组聚合 |
| | PhysicalPerfectHashAggregate | 小基数分组（NDV < 256） |
| | PhysicalPartitionedAggregate | 大基数分区的并行聚合 |
| | PhysicalUngroupedAggregate | 无分组（整表聚合） |
| LogicalGet | PhysicalTableScan | 从本地表读取 |
| | PhysicalColumnDataScan | 从内存 ColumnData 读取 |
| LogicalOrder + LogicalLimit | PhysicalTopN | TopN 优化合并 |

## 13.2 PhysicalOperator 体系

```cpp
// src/include/duckdb/execution/physical_operator.hpp
class PhysicalOperator {
public:
    PhysicalOperatorType type;        // 物理算子类型枚举
    vector<LogicalType> types;        // 输出列类型
    idx_t estimated_cardinality;      // 估算基数

    // 算子执行接口
    virtual OperatorResultType Execute(ExecutionContext &context,
                                       DataChunk &input,
                                       DataChunk &output,
                                       GlobalOperatorState &gstate,
                                       OperatorState &lstate);
    // Sink 接口（Pipeline Breaker）
    virtual SinkResultType Sink(ExecutionContext &context,
                                DataChunk &chunk,
                                OperatorSinkInput &input);
    virtual SinkFinalizeType Finalize(Pipeline &pipeline,
                                       Event &event,
                                       ClientContext &context,
                                       OperatorSinkInput &input);
};
```

### Source → Operator → Sink 三角色模型

物理算子按在 Pipeline 中的角色分为三种：

```
Pipeline: [Source] → [Operator] → [Operator] → [Sink]
```

**Source（数据源）**：产生 DataChunk。如 `PhysicalTableScan`、`PhysicalColumnDataScan`。
**Operator（中间算子）**：消费一个 DataChunk，产出一个 DataChunk。如 `PhysicalFilter`、`PhysicalHashJoin::Probe`。
**Sink（汇聚点）**：消费 DataChunk 但不产出——它是 Pipeline 的终点。如 `PhysicalHashAggregate`、`PhysicalHashJoin::Build`。

每个物理算子可以同时实现多个接口——`PhysicalHashJoin` 既是 Sink（构建端），又包含 Operator 逻辑（探测端）。这种设计让一个物理算子可以跨越两个 Pipeline。

## 13.3 Pipeline 构建：Plan → MetaPipeline → Pipeline

物理计划生成后，`Executor` 将其分解为 Pipeline DAG：

```
物理计划：
  PhysicalProjection
    PhysicalHashAggregate (Sink)
      PhysicalFilter
        PhysicalTableScan (Source)

Pipeline DAG：
  Pipeline 1: PhysicalTableScan → PhysicalFilter → PhysicalHashAggregate(Sink)
  Pipeline 2: PhysicalHashAggregate(Source) → PhysicalProjection
```

**Pipeline 的分界点是 Sink 算子**——HashAggregate 是一个 Sink，它消费完所有输入后才能输出。因此物理计划在 HashAggregate 处被切分为两个 Pipeline：Pipeline 1 做聚合的构建，Pipeline 2 做聚合结果的读取和投影。

Pipeline 的执行模型是 **push-based**——Source 产生一个 DataChunk，推给第一个 Operator，Operator 处理后推给下一个，直到 Sink 消费。这不同于 Volcano 的 pull-based 模型（每个算子调用 `child.Next()` 获取一行）。

---

# 第14章：Pipeline 执行模型

## 14.1 Pipeline 的核心抽象

```cpp
// src/include/duckdb/parallel/pipeline.hpp
class Pipeline {
    vector<reference<PhysicalOperator>> operators;  // 算子链
    PhysicalOperator *sink;                          // 终点 Sink
    shared_ptr<PipelineEvent> event;                 // 完成事件
};
```

Pipeline 是一组**线性排列**的物理算子链——从 Source 到 Sink，没有分支。分支（如 Join 的两个输入）通过多个 Pipeline + Pipeline DAG 表达。

### 为什么选择 Pipeline 而非 Volcano

| 特性 | Volcano (Pull) | Pipeline (Push) |
|------|---------------|-----------------|
| 调用方向 | 下游调用上游 `Next()` | 上游推数据给下游 |
| 每行虚函数调用 | N 次（N=算子数） | 1 次（整个 Pipeline） |
| 数据局部性 | 差（每行跳转多次） | 好（整批数据顺序处理） |
| 分支处理 | 自然（递归拉取） | 需要 Pipeline DAG |
| 向量化兼容 | 需要特殊处理 | 天然兼容 |

DuckDB 选择 Pipeline 的核心原因：**向量化执行 + Push-based 天然契合**。一个 DataChunk（2048 行）从 Source 产生后，顺序流过所有 Operator，最终到达 Sink。每个算子处理 2048 行的批量数据，缓存友好。

## 14.2 OperatorResultType：数据流的状态机

```cpp
enum class OperatorResultType {
    NEED_MORE_INPUT,    // 需要更多输入数据
    HAVE_MORE_OUTPUT,   // 还有输出数据未消费
    FINISHED,           // 执行完毕
    BLOCKED,            // 被阻塞（等待异步操作）
};
```

每个 Operator 的 `Execute` 方法返回 `OperatorResultType`，控制 Pipeline 的数据流：

- `NEED_MORE_INPUT`：当前 DataChunk 处理完毕，从 Source 获取下一个 Chunk
- `HAVE_MORE_OUTPUT`：当前输入产生了部分输出，但还有更多——Pipeline 应该继续调用 Execute 而不获取新输入
- `FINISHED`：算子不再需要数据（如 LIMIT 已满足）
- `BLOCKED`：算子等待外部事件（如异步 I/O）

## 14.3 Pipeline Breaker：Sink 的本质

Sink 算子是 Pipeline 的"断点"——它必须消费所有输入后才能输出。典型的 Sink：

- `PhysicalHashAggregate`：必须看到所有行才能计算聚合结果
- `PhysicalHashJoin::Build`：必须构建完整的 Hash 表才能开始探测
- `PhysicalOrder`：必须看到所有行才能排序

Sink 打破了 Pipeline 的连续性，将一个 Pipeline 分为两个。这是不可避免的——聚合和 Join 构建本质上需要"看到全部数据"。优化器的目标之一就是减少不必要的 Pipeline Breaker。

---

# 第15章：并行执行框架

## 15.1 TaskScheduler：固定线程池

```cpp
// src/include/duckdb/parallel/task_scheduler.hpp
class TaskScheduler {
    // 创建 N 个工作线程（N = CPU 核数）
    // 使用 ConcurrentQueue 分发任务
    // 工作窃取：空闲线程从其他线程的队列中窃取任务
};
```

TaskScheduler 在 DatabaseInstance 初始化时创建，生命周期与数据库实例相同。它使用 `moodycamel::ConcurrentQueue`（`src/include/duckdb/parallel/concurrentqueue.hpp`）作为任务队列——这是一个无锁的、高并发的队列实现。

## 15.2 PipelineExecutor 的多线程执行

```cpp
// src/include/duckdb/parallel/pipeline_executor.hpp
class PipelineExecutor {
    // 为 Pipeline 中的每个算子创建 OperatorState
    // 执行循环：Source → Operator → ... → Sink
    // 支持 morsel-driven parallelism：每个线程处理一个"morsel"（一个 DataChunk）
};
```

多线程并行的方式是 **morsel-driven**——每个线程从 Source 获取一个"morsel"（一个 DataChunk 的数据量），独立执行 Pipeline 的所有算子，最终 Sink 汇聚所有线程的结果。

```
Thread 1: Source(chunk_0) → Filter → HashAggregate.Sink(chunk_0)
Thread 2: Source(chunk_1) → Filter → HashAggregate.Sink(chunk_1)
Thread 3: Source(chunk_2) → Filter → HashAggregate.Sink(chunk_2)
...
Sink 汇聚所有线程的部分聚合结果，执行 Finalize 合并
```

## 15.3 两种并行粒度

DuckDB 有两种并行方式：

1. **Pipeline 内并行**（Morsel-driven）：多个线程同时执行同一个 Pipeline，每个线程处理不同的数据切片
2. **Pipeline 间并行**：多个独立 Pipeline 可以同时执行（如 HashJoin 的 Build Pipeline 和 Probe Pipeline）

这两种并行可以组合——HashJoin 的 Build Pipeline 和 Probe Pipeline 各自内部又可以用多个线程执行。

## 15.4 与 Spark 执行模型的对比

| 维度 | Spark | DuckDB |
|------|-------|--------|
| 并行单位 | Task（一个分区） | Morsel（一个 DataChunk） |
| 调度方式 | DAG Scheduler → TaskScheduler | TaskScheduler 直调 |
| 数据交换 | Shuffle（网络 + 磁盘） | Pipeline 内推（内存指针） |
| 容错 | RDD 血统重算 | 无容错（嵌入式不需要） |
| 延迟 | 毫秒级（调度+序列化） | 微秒级（函数调用） |

Spark 的并行是"进程间并行"——不同 Task 可能在不同机器上。DuckDB 的并行是"线程间并行"——不同 Morsel 在同一进程的不同核心上。代价差了三个数量级。
