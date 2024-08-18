# Chapter 10: Processors 流水线模型

## 10.1 为什么需要流水线模型？

ClickHouse 早期使用"拉取式"执行模型：Interpreter 层直接调用 Storage 的 `read()` → 返回 Block 流。这有两个问题：
1. 无法并行执行多个操作（如同时读取 + 过滤 + 聚合）
2. 无法表达复杂的数据流（如 JOIN 的两侧输入）

Processors 模型将执行抽象为一个 DAG（有向无环图），每个 Processor 是一个计算节点，数据在节点之间流式传递。

> **第一性原理**：为什么选择 Push 模型而非 Volcano 拉取模型？Volcano 模型（每行一次 `next()` 调用）在 OLTP 中表现尚可，但在 OLAP 的百万行批次中虚函数调用开销不可接受。Push 模型让数据主动流动，每个 Processor 处理整个 Block（65536 行），摊薄了调度开销。更重要的是，Push 模型天然支持背压——当 Sink 端处理不过来时，Source 自动暂停。

## 10.2 IProcessor — 处理器基类

`src/Processors/IProcessor.h` — 所有 Processor 的基类：

```cpp
class IProcessor
{
public:
    // 输入/输出端口
    InputPorts inputs;
    OutputPorts outputs;

    // 处理状态
    enum class Status
    {
        NeedData,       // 需要输入数据（等待上游推送）
        PortFull,       // 输出端口已满（等待下游消费）
        Finished,       // 处理完成（不再产出数据）
        Ready,          // 准备好执行 work()
        Async,          // 需要异步等待（网络 I/O 等）
        ExpandPipeline, // 需要扩展 Pipeline（如初始化 JOIN 右侧）
    };

    // 准备阶段（不执行计算，只检查端口状态）
    virtual Status prepare() = 0;

    // 执行阶段（实际计算）
    virtual void work() = 0;
};
```

**端口模型**：每个 Processor 有若干 InputPort 和 OutputPort，数据通过端口以 Block 为单位传递：

```
Source → [OutputPort] → [InputPort] → Transform → [OutputPort] → [InputPort] → Sink
```

**状态机**：

```
         ┌──────────────────────────────┐
         │                              │
    NeedData ←── prepare() ── Ready ────┤
         │                │         │   │
         │           work()    PortFull  │
         │                │         │   │
         │                ↓         │   │
         │           NeedData       │   │
         │                │         │   │
         │                ↓         │   │
         │            Finished ←────┘   │
         │                              │
         └──────────────────────────────┘
```

### 端口连接与数据传递

`src/Processors/Port.h` — InputPort 和 OutputPort 的连接机制：

```cpp
class OutputPort
{
    Block data;           // 待发送的数据
    InputPort * connected = nullptr;  // 连接的输入端口

    void push(Block block)
    {
        data = std::move(block);
        // 如果 connected->needData 为 true，通知 Executor
    }

    bool canPush() const
    {
        // 检查下游是否可以接收数据
        return connected && !connected->hasData();
    }
};

class InputPort
{
    Block data;           // 接收到的数据
    OutputPort * connected = nullptr;  // 连接的输出端口

    bool hasData() const { return data.has_value(); }

    Block pull()
    {
        auto block = std::move(data);
        data = {};
        return block;
    }
};
```

**连接方式**：

```cpp
// 将 Processor A 的输出连接到 Processor B 的输入
connect(A.outputs[0], B.inputs[0]);
```

### ExpandPipeline — 动态 Pipeline 扩展

`Status::ExpandPipeline` 是一个特殊状态，用于在运行时动态扩展 Pipeline 拓扑：

```
场景: Hash Join 初始化时需要创建右侧读取 Pipeline

初始 Pipeline:
  ReadFromLeftTable → JoiningTransform → ExpressionTransform → Sink

JoiningTransform::prepare():
  if (!right_pipeline_initialized)
  {
      // 返回 ExpandPipeline，通知 Executor 需要扩展
      return Status::ExpandPipeline;
  }

JoiningTransform::expandPipeline():
  // 创建右侧读取 Pipeline
  auto right_source = std::make_shared<ReadFromRightTable>(...);
  auto right_pipeline = QueryPipelineBuilder()
      .init(Pipe(right_source))
      .build();

  // 将右侧 Source 的输出连接到 JoiningTransform 的第二个输入
  connect(right_pipeline.getHeader(), inputs[1]);

  return expanded_pipeline;
```

## 10.3 Processor 类型

| 类型 | 输入端口 | 输出端口 | 作用 |
|------|----------|----------|------|
| `ISource` | 0 | 1 | 产生数据（读表、读文件） |
| `ISink` | 1 | 0 | 消费数据（写表、写网络） |
| `ITransformer` | 1 | 1 | 变换数据（过滤、投影、聚合） |
| `IInflatingTransformer` | 1 | 1 | 可能输出更多行（展开数组） |
| `ICursorInflatingTransformer` | 1 | 1 | 游标式展开 |
| `IMultipleInputsProcessor` | N | 1 | 多输入（JOIN、UNION） |
| `IMultipleOutputsProcessor` | 1 | N | 多输出（广播、复制） |

### ISource — 数据源

```cpp
class ISource : public IProcessor
{
    // 只有一个 OutputPort
    // 产生 Block 的核心方法
    virtual Chunk generate() = 0;

    Status prepare() override
    {
        if (output.canPush())
            return Status::Ready;  // 可以产出数据
        return Status::PortFull;   // 下游还没消费完
    }

    void work() override
    {
        auto chunk = generate();
        if (chunk)
            output.push(std::move(chunk));
        else
            output.finish();  // 数据产完
    }
};
```

### ISink — 数据汇

```cpp
class ISink : public IProcessor
{
    // 只有一个 InputPort
    // 消费 Block 的核心方法
    virtual void consume(Chunk chunk) = 0;

    Status prepare() override
    {
        if (input.hasData())
            return Status::Ready;
        if (input.isFinished())
            return Status::Finished;
        return Status::NeedData;
    }

    void work() override
    {
        auto chunk = input.pull();
        consume(std::move(chunk));
    }
};
```

## 10.4 QueryPipeline — 流水线构建

`src/QueryPipeline/QueryPipelineBuilder.h` — QueryPipeline 是 Processor DAG 的容器：

```cpp
class QueryPipelineBuilder
{
    // 添加 Source
    void init(Pipe pipe);

    // 添加 Transform（串联在当前 Pipeline 末端）
    void addSimpleTransform(TransformParams params);

    // 添加 Sink
    void setSinks(ProcessorCreatorWithPorts creator);

    // 构建 Pipeline
    QueryPipeline build();
};
```

### Pipeline 拓扑示例

**简单查询**：`SELECT col FROM t WHERE col > 10`

```
ReadFromMergeTree (Source)
      │
      ↓
FilterTransform (WHERE)
      │
      ↓
ExpressionTransform (Projection)
      │
      ↓
TCPHandler Sink
```

**JOIN 查询**：`SELECT a.x, b.y FROM a JOIN b ON a.id = b.id`

```
ReadFromMergeTree(a) ──→ JoiningTransform ←── ReadFromMergeTree(b)
                              │
                              ↓
                        ExpressionTransform
                              │
                              ↓
                         TCPHandler Sink
```

**聚合查询**：`SELECT key, count() FROM t GROUP BY key`

```
ReadFromMergeTree (Source)
      │
      ↓
AggregatingTransform (两阶段聚合)
      │
      ↓
ExpressionTransform
      │
      ↓
TCPHandler Sink
```

**UNION ALL 查询**：`SELECT a FROM t1 UNION ALL SELECT b FROM t2`

```
ReadFromMergeTree(t1) ──→ UnionTransform ←── ReadFromMergeTree(t2)
                                │
                                ↓
                          ExpressionTransform
                                │
                                ↓
                           TCPHandler Sink
```

## 10.5 PipelineExecutor — 执行引擎

`src/Processors/Executors/PipelineExecutor.h` — 单线程执行引擎：

```cpp
class PipelineExecutor
{
    void execute()
    {
        // 拓扑排序所有 Processor
        auto order = topologicalSort(processors);

        // 事件循环
        while (!is_finished)
        {
            for (auto & processor : order)
            {
                auto status = processor->prepare();
                if (status == Status::Ready)
                    processor->work();
            }
        }
    }
};
```

### PullingAsyncPipelineExecutor

`src/Processors/Executors/PullingAsyncPipelineExecutor.h` — 异步拉取执行引擎，用于服务器向客户端推流：

```cpp
class PullingAsyncPipelineExecutor
{
    // 拉取下一个 Block（非阻塞，支持超时）
    bool pull(Block & block, uint64_t milliseconds = 0);

    // 内部使用线程池并行执行 Pipeline
    // 主线程从 Sink 端拉取结果
};
```

**执行模型**：
1. 将 Pipeline 分割为独立子图
2. 每个子图分配一个线程
3. 数据在子图间通过 `Port` 传递（带背压）
4. 主线程从最终 Sink 拉取 Block

### PushingAsyncPipelineExecutor

`src/Processors/Executors/PushingAsyncPipelineExecutor.h` — 异步推送执行引擎，用于 INSERT：

```cpp
class PushingAsyncPipelineExecutor
{
    // 推送一个 Block 到 Pipeline
    void push(Block block);

    // 结束推送
    void finish();
};
```

**INSERT 场景**：

```
Client Data → PushingAsyncPipelineExecutor.push(block)
  │
  ├── ExpressionTransform (类型转换/计算默认值)
  │
  └── MergeTreeSink (写入 Part)
```

### CompletedPipelineExecutor

`src/Processors/Executors/CompletedPipelineExecutor.h` — 无交互执行引擎，用于 DDL/DML：

```cpp
class CompletedPipelineExecutor
{
    // 执行 Pipeline 直到完成，不需要拉取/推送数据
    // 用于: CREATE TABLE, ALTER TABLE, SYSTEM 命令等
    void execute();
};
```

## 10.6 背压机制

当 Sink 端消费速度慢于 Source 端产生速度时，背压机制防止内存溢出：

```
Source → [Port: full] → Transform → [Port: empty] → SlowSink
                     ↑
                     └── Source 被 PortFull 状态阻塞
                         直到 Transform 消费了数据
```

实现：`OutputPort::push(Block)` 检查连接的 `InputPort` 是否有空间。如果没有，返回 `PortFull`，Source 的 `prepare()` 返回 `PortFull`，Executor 暂停该 Processor。

### 背压传播示例

```
场景: 客户端网络慢，无法快速消费查询结果

TCPHandler Sink → 缓冲区满 → PortFull
  ↑
ExpressionTransform → 输出端口满 → PortFull
  ↑
AggregatingTransform → 输出端口满 → PortFull
  ↑
ReadFromMergeTree Source → PortFull → 暂停读取

效果: 整个 Pipeline 停止，直到客户端消费数据
  → 防止内存无限增长
  → 但可能导致读取超时（max_execution_time）
```

### 内存控制

```cpp
// Pipeline 执行时的内存跟踪
// 每个 Query 有 MemoryTracker，记录内存使用
// 当超过 max_memory_usage 时抛出异常

// 设置:
max_memory_usage = 10GB              ← 单查询内存上限
max_memory_usage_for_user = 50GB     ← 单用户内存上限
memory_overcommit_ratio_denominator  ← 超卖比
```

## 10.7 多线程执行

### Pipeline 内并行

当 Pipeline 中有多个 Source（如多个 Part 并行读取），Executor 自动使用多线程：

```
PipelineExecutor 的线程模型:
  1. 将 Processor DAG 拓扑排序
  2. 识别可以并行的子图（无数据依赖的分支）
  3. 每个子图分配一个线程
  4. 主线程协调执行

示例: 读取 3 个 Parts
  Thread 1: ReadFromMergeTree(Part A) → FilterTransform
  Thread 2: ReadFromMergeTree(Part B) → FilterTransform
  Thread 3: ReadFromMergeTree(Part C) → FilterTransform
  Main:     AggregatingTransform → ExpressionTransform → Sink
```

### 执行器线程池

ClickHouse 使用全局线程池执行 Pipeline：

```cpp
// 全局线程池
GlobalThreadPool::initialize(max_threads, max_free_threads, queue_size);

// 每个查询从全局池获取线程
// 线程数由 max_threads 设置控制
// 默认: min(物理核心数, max_threads)
```

> **侧边栏 · 与 Spark 对比**：Spark 使用 Exchange 作为 Stage 间的数据交换，通过磁盘 shuffle 实现。ClickHouse 的 Processor 模型更接近 Flink 的算子链——数据在内存中直接传递，不落盘。代价是 Pipeline 必须能完整放入内存（除了 Grace Hash Join 等特殊实现）。

> **侧边栏 · 与 StarRocks 对比**：StarRocks 的 Pipeline 类似 ClickHouse 的 Processors，但使用固定大小的 Morsel（批次）驱动执行，并支持 Query-level 的优先级调度。ClickHouse 的调度粒度更粗——整个 Pipeline 在一个线程组内执行，直到完成或超时。

## 10.8 Pipeline 优化

### Pipeline 重排

在构建 Pipeline 后，Executor 可以对 Processor 进行优化重排：

```
优化 1: 算子融合 (Operator Fusion)
  FilterTransform + ExpressionTransform → FusedTransform
  减少一次 Block 拷贝

优化 2: 延迟物化
  SELECT col1, col2 FROM t WHERE col3 = 1
  → 先读 col3，过滤后再读 col1, col2（PREWHERE 思想）

优化 3: 下推聚合
  GROUP BY + LIMIT → TopN 优化（避免完整排序）
```

### QueryPlan 到 QueryPipeline 的转换

```
QueryPlan (声明式):
  ReadFromMergeTree → FilterStep → AggregatingStep → ExpressionStep → LimitStep

QueryPipeline (命令式):
  MergeTreeSource → FilterTransform → AggregatingTransform → ExpressionTransform → LimitTransform → Sink

转换规则:
  每个 QueryPlan Step → 一个或多个 Processor
  Step 之间的数据流 → Port 连接
  多输入 Step (JOIN) → ExpandPipeline 动态扩展
```

## 10.9 本章小结

```
QueryPlan Steps → QueryPipelineBuilder → QueryPipeline → Executor
                                                     │
                                                     ├── PipelineExecutor (单线程)
                                                     ├── PullingAsyncPipelineExecutor (异步拉取)
                                                     ├── PushingAsyncPipelineExecutor (异步推送)
                                                     └── CompletedPipelineExecutor (无交互)

Processor 状态机:
  NeedData ←→ Ready ←→ PortFull → Finished
                ↑
           ExpandPipeline (动态扩展)

背压机制:
  OutputPort::push() → 检查下游是否有空间 → PortFull → 暂停上游

核心设计决策:
  - Push 模型 + 背压 — 数据从 Source 推向 Sink，端口满时自动暂停
  - DAG 拓扑 — 支持任意复杂的执行图（JOIN 两侧、UNION 多路）
  - ExpandPipeline — 运行时动态扩展 Pipeline（JOIN 右侧初始化）
  - 多线程并行 — 无依赖的子图分配到不同线程
```

**关键文件地图**：
```
src/Processors/IProcessor.h                   → Processor 基类
src/Processors/Port.h                         → 端口连接与数据传递
src/Processors/ISource.h                      → Source 基类
src/Processors/ITransformer.h                 → Transform 基类
src/Processors/ISink.h                        → Sink 基类
src/QueryPipeline/QueryPipelineBuilder.h      → Pipeline 构建器
src/Processors/Executors/PipelineExecutor.h   → 单线程执行器
src/Processors/Executors/PullingAsyncPipelineExecutor.h → 异步拉取执行器
src/Processors/Executors/PushingAsyncPipelineExecutor.h → 异步推送执行器
src/Processors/Executors/CompletedPipelineExecutor.h    → 无交互执行器
```
