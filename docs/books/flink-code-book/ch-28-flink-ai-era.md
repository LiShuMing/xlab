# 第 28 章 · AI 时代：Flink 与 LLM 推理、Agent 的碰撞

## 导读

- **一句话**：本章从 Flink 的流处理、状态管理、异步 IO 三大核心能力出发，探讨它们如何与 LLM 推理、Agent Memory、GPU 亲和调度等 AI 场景产生深层交汇。
- **前置知识**：LLM 推理基础（prefill/decode 阶段）、Agent/Function Calling 概念、GPU 计算基础、向量数据库基本原理。
- **读完本章你能回答**：
  - Flink 的流处理架构为什么天然适配 LLM 推理管道
  - Async IO 模式与 LLM API 调用的深层匹配关系
  - Flink State Backend 如何承载 Agent Memory 的两级缓存需求
  - GPU 亲和性调度在 Flink 上的可能实现路径
  - Flink AI Model 集成模块（OpenAI/Triton）的设计思路

---

## 28.1 — 设计动机

为什么 Flink 的架构天然适配 AI 推理场景？答案藏在三个基础能力的交汇处：**流处理、状态管理、异步 IO**。

LLM 推理不是一次性的批处理任务。用户对话是无限流，Agent 需要维护跨轮次的记忆，LLM API 调用天然是高延迟的异步操作——这三条特征分别对应 Flink 的三大核心能力：

**流处理匹配推理管道的连续性**。用户输入是无限流，推理请求持续产生，推理结果持续返回。批处理系统（如 Spark）每次都要冷启动推理管道，而 Flink 的常驻算子管道天然支持推理服务的在线运行。数据到达即触发推理，推理完成即下发结果，无需调度开销。

**状态管理匹配 Agent Memory 的持久性**。Agent 需要短期对话上下文（最近 N 轮）和长期知识记忆（向量检索），这正好对应 Flink 的 KeyedState（热数据、低延迟）和外部存储（冷数据、大容量）。State Backend 的分层存储模型与 Agent Memory 的冷热分层需求同构。

**异步 IO 匹配 LLM 调用的高延迟**。LLM API 的响应延迟通常在数百毫秒到数十秒之间。如果同步调用，一个并发度为 1 的算子每秒只能处理几条请求。Flink 的 AsyncDataStream 允许单个 Task 线程同时发起数千个并发请求而不阻塞——这本质上是一个内嵌的异步网关。

为什么这样设计？因为 Flink 解决的核心问题——**无界数据上的有状态计算**——与 AI 推理的核心问题——**无限请求流上的有记忆推理**——在结构上同构。Flink 放弃的不是"能不能做推理"，而是"是否要做专用推理引擎"。Flink 的定位是通用流处理引擎，它提供的不是最优的推理调度，而是最成熟的流式基础设施，让推理管道可以站在已有工程能力的肩膀上。

---

## 28.2 — 概念映射：Flink 架构到 AI 推理

Flink 的架构概念可以系统性地映射到 AI 推理场景：

| Flink 概念 | AI 推理对应 | 映射逻辑 |
|-----------|------------|---------|
| **流处理 DAG** | 推理 Pipeline | 预处理 -> 推理 -> 后处理的三段式管道，每段对应一个或多个算子 |
| **State Backend** | Agent Memory | KeyedState 存短期对话状态（热），VectorDB 存长期知识（冷） |
| **AsyncDataStream** | LLM API 调用 | 非阻塞等待外部服务响应，单线程高并发 |
| **Checkpoint** | 推理状态快照 | 故障恢复时还原 Agent 的完整对话上下文 |
| **反压** | 推理服务过载保护 | GPU 队列满时自动降速上游，防止 OOM |
| **ResourceProfile** | GPU 资源声明 | 算子声明对特定 GPU 型号的需求，调度器匹配 |

### 流处理 DAG 到推理 Pipeline

一个典型的 LLM 推理管道可以映射为 Flink DAG：

```
Source(Kafka) -> Map(预处理/tokenize) -> MapAsync(LLM推理) -> Map(后处理) -> Sink(Kafka)
```

预处理算子负责文本清洗、token 计数、上下文截断；MapAsync 算子负责调用 LLM API；后处理算子负责解析响应、提取结构化字段。整个管道常驻运行，数据到达即处理，与 checkpoint barrier/watermark 等流控机制协同工作。

### State Backend 到 Agent Memory

Agent Memory 的核心矛盾是"快但小"与"大但慢"的取舍。Flink 的 State Backend 天然提供了分层存储模型：

```
Agent Memory 两级缓存:
  L1 - Flink KeyedState (Heap/RocksDB)
       存储: 近 N 轮对话上下文、当前会话状态
       延迟: 微秒~毫秒级
       容量: 受 TaskManager 内存限制

  L2 - 外部 VectorDB (Milvus/Pinecone/Weaviate)
       存储: 历史对话 embedding、知识库向量索引
       延迟: 毫秒~秒级
       容量: TB 级
```

读写路径：推理时先从 KeyedState 读取当前用户的短期上下文（快），如果需要历史信息再查询 VectorDB（慢），将两部分拼装后发送给 LLM。推理完成后更新 KeyedState 并异步写入 VectorDB。

### Async IO 到 LLM API 调用

LLM API 调用的本质特征是高延迟、高并发。Flink 的 AsyncDataStream 通过 user-pacing model（第 10 章 mailbox）允许单条 Task 线程同时维护数百甚至数千个并发请求，而不阻塞算子处理。这等价于一个内嵌的 API Gateway。

### Checkpoint 到推理状态快照

Agent 的对话状态必须可恢复。Flink 的 Checkpoint 机制定期对 State 做快照，故障后从最近一次快照恢复。映射到 AI 场景：Agent 的短期对话上下文随 Checkpoint 持久化，重启后自动恢复到故障前的对话状态，无需用户重新描述上下文。

### 反压到推理服务过载保护

当 LLM 服务端队列满或 GPU 利用率饱和时，响应延迟急剧上升。Flink 的反压机制自动传导：MapAsync 算子的输出队列堆积 -> 反压到上游 -> Source 降速。这提供了一种无需额外代码的过载保护，等价于推理服务中的 rate limiter，但它是系统内置的、自适应的。

---

## 28.3 — 关键流程走读

### 28.3.1 AsyncDataStream + LLM API 的完整管道

一个生产级的 LLM 推理管道在 Flink 上的典型实现：

```java
// Source: 消费用户请求流
DataStream<ChatRequest> requests = env
    .addSource(new KafkaSource<>("chat-requests"));

// MapAsync: 异步调用 LLM API
DataStream<ChatResponse> responses = AsyncDataStream.unorderedWait(
    requests.keyBy(ChatRequest::getUserId),
    new AsyncFunction<ChatRequest, ChatResponse>() {
        private transient LLMClient llmClient;

        public void open(Configuration params) {
            llmClient = new LLMClient("https://api.openai.com/v1");
        }

        public void asyncInvoke(ChatRequest req, ResultFuture<ChatResponse> future) {
            llmClient.chatCompletion(req.getMessages())
                .thenAccept(resp -> future.complete(Collections.singleton(resp)))
                .exceptionally(ex -> {
                    future.completeExceptionally(ex);
                    return null;
                });
        }
    },
    30000, TimeUnit.MILLISECONDS,  // timeout=30s, LLM 推理可能较慢
    200                            // capacity=200, 并发请求数上限
);
```

关键参数解读：

- **unorderedWait**：不保证结果顺序，先返回的先下发。LLM 推理延迟因输入长度而异，有序等待会严重降低吞吐。使用 `unorderedWait` 让短请求不必等长请求。
- **capacity=200**：控制同时未完成的请求数。超过上限时，新请求在算子缓冲区排队，并触发反压传导到上游。这个参数需要根据 LLM 服务的 QPS 上限和 Flink TaskManager 的内存容量联合调优。
- **timeout=30s**：LLM 推理超时。超过此时间的请求触发 `AsyncFunction.timeout()` 回调，可自定义降级逻辑（如返回缓存结果或错误提示）。

`<org.apache.flink.streaming.api.datastream.AsyncDataStream:L#53>` 定义了默认队列容量 100，`<org.apache.flink.streaming.api.functions.async.AsyncFunction:L#87>` 定义了核心的 `asyncInvoke` 接口。

### 28.3.2 State Backend 承载 Agent Memory 的详细方案

两级缓存的读写路径需要精确设计：

**读路径**（推理前组装上下文）：

```
1. KeyBy(userId) 将同一用户的请求路由到同一算子实例
2. 从 ValueState<List<Message>> 读取近 N 轮对话（微秒级）
3. 若对话不足 N 轮或需要知识增强，查询 VectorDB：
   a. 将用户输入 embedding 化
   b. VectorDB.topK(embedding, k=5) 检索相关历史
   c. 拼装 system_prompt + 历史检索 + 近 N 轮对话 + 当前输入
4. 发送给 LLM API
```

**写路径**（推理后更新状态）：

```
1. 将 LLM 的回复追加到 ValueState<List<Message>>
2. 若 State 中对话轮数超过 N，截断最旧的轮次
3. 异步将截断的旧对话 embedding 化并写入 VectorDB
4. State 变更随 Checkpoint 持久化
```

关键设计决策：为什么把短期记忆放在 Flink State 而不是全部放 VectorDB？因为 Flink State 的访问延迟是微秒级（HeapStateBackend）或毫秒级（RocksDB），而 VectorDB 的网络往返加检索通常在 10ms 以上。短期对话上下文在每次推理时必须读取，放在 Flink State 内可以消除这个延迟。长期记忆只在需要时检索，放外部存储是合理的。

### 28.3.3 GPU 亲和调度的实现路径

Flink 当前能发现 GPU 资源（第 25 章 ExternalResource），但不能做 GPU 亲和性调度——即"把处理 X 模型的算子调度到已加载 X 模型权重的 GPU 节点上"。这是一个关键的缺失能力。

可能的三步扩展方案：

**第一步：ResourceProfile 扩展**。在 ResourceSpec 中声明 GPU 型号需求：

```java
ResourceSpec gpuSpec = ResourceSpec.newBuilder()
    .setCpuCores(2.0)
    .setTaskHeapMemoryMB(4096)
    .setExternalResource("gpu-model", 1.0)   // 声明需要 1 个 GPU
    .setExternalResource("gpu-a100", 1.0)    // 进一步声明 A100 型号
    .build();
```

`<org.apache.flink.runtime.clusterframework.types.ResourceProfile:L#46>` 中 ResourceProfile 已支持 ExternalResource 字段，扩展成本较低。

**第二步：RequirementMatcher 匹配**。`<org.apache.flink.runtime.slots.DefaultRequirementMatcher:L#31>` 的 `match()` 方法当前只比较 CPU/内存/ExternalResource 数量，需要扩展为比较 ExternalResource 的属性（如 GPU 型号字符串）。当算子声明 `gpu-a100` 需求时，只有带 A100 标签的 Slot 才能匹配。

**第三步：调度器适配**。SlotManager 在分配 Slot 时，除了检查资源数量，还要检查 GPU 型号标签。可以参考 StarRocks 的 Location-Aware Scheduling——将 BE 节点的磁盘位置信息纳入调度决策。Flink 的调度器同样可以将 GPU 型号作为 Slot 的拓扑属性，让调度决策考虑模型权重本地性。

`<org.apache.flink.externalresource.gpu.GPUDriver:L#99>` 的 `retrieveResourceInfo()` 方法当前只返回 GPU 索引号（如 "0,1"），扩展为返回 GPU 型号信息即可支撑上述方案。

### 28.3.4 Flink AI Model 集成模块

Flink 源码树中的 `flink-models/` 模块提供了对 OpenAI 和 Triton 两种推理服务的集成，是本章讨论的所有概念的工程实现。

**OpenAI 集成**（`flink-model-openai`）：

`<org.apache.flink.model.openai.AbstractOpenAIModelFunction:L#64>` 继承自 `AsyncPredictFunction`，通过 OpenAI 的异步 Java SDK 发起非阻塞请求。核心流程：

1. `open()` 中创建 `OpenAIClientAsync` 实例（L108）
2. `asyncPredict()` 对输入做 ContextOverflow 处理后调用 `asyncPredictInternal()`（L113-127）
3. 子类 `OpenAIChatModelFunction` 在 `asyncPredictInternal()` 中构建 `ChatCompletionCreateParams` 并异步调用（L86-106）
4. 错误处理支持三种策略：RETRY、FAILOVER、IGNORE（L227-243）

**Triton 集成**（`flink-model-triton`）：

`<org.apache.flink.model.triton.AbstractTritonModelFunction:L#62>` 同样继承 `AsyncPredictFunction`，但面向自建的 Triton Inference Server。与 OpenAI 集成的关键差异在于：

- 内置 Circuit Breaker（熔断器）：当 Triton 服务连续失败超过阈值时自动熔断，避免雪崩（L147-161）
- 内置 Health Checker：定期探测 Triton 健康状态，与熔断器联动（L164-199）
- HTTP 连接池复用：多个算子实例共享同一 JVM 内的 OkHttpClient，引用计数管理（L144）

两个集成模块的共性：都以 `AsyncPredictFunction` 为基类，都走异步非阻塞路径，都内建了超时和重试机制。这印证了 28.1 节的判断——Async IO 是 LLM API 调用的自然匹配。

`<org.apache.flink.table.functions.AsyncPredictFunction:L#35>` 本身继承 `AsyncTableFunction<RowData>`，通过 `eval()` 方法桥接到 Flink SQL 的 Model 语法，使得用户可以在 SQL 中直接调用 LLM：

```sql
-- 声明 Model
CREATE MODEL llm_chat
INPUT (prompt STRING)
OUTPUT (response STRING)
WITH (
  'provider' = 'openai',
  'openai.model' = 'gpt-4o',
  'openai.api-key' = 'sk-xxx'
);

-- 在 SQL 中使用
SELECT llm_chat(prompt) FROM chat_requests;
```

---

## 28.4 — 横向对比

### vs Ray Serve

Ray Serve 是专为 ML 推理设计的部署框架，核心模型是 Actor 模型。

| 维度 | Ray Serve | Flink |
|------|----------|-------|
| **编程模型** | Actor（有状态对象，独立生命周期） | 算子（DAG 节点，统一生命周期） |
| **状态管理** | Actor 内部自行管理，无统一抽象 | State Backend 统一管理，Checkpoint 自动持久化 |
| **并发模型** | 每个 Actor 独立处理请求，异步 await | AsyncDataStream 单线程高并发，mailbox 调度 |
| **流式集成** | 需要额外对接 Kafka 等消息队列 | 原生 Source/Sink，端到端 exactly-once |
| **弹性伸缩** | Autoscaler 基于 QPS 指标 | Adaptive Scheduler 基于资源画像 |

Ray 的 Actor 模型更适合"每个推理请求独立处理"的场景。但当推理管道需要多阶段编排（预处理 -> 推理 -> 后处理 -> 状态更新），且需要端到端的流控与容错时，Flink 的算子模型提供了更完整的工程保障。

### vs Triton Inference Server

Triton 是 NVIDIA 推出的专用推理服务，核心聚焦在 GPU 推理优化。

| 维度 | Triton | Flink |
|------|--------|-------|
| **定位** | 专用推理服务 | 通用流处理引擎 |
| **批处理** | Dynamic Batching（服务端聚合请求） | 无内建推理批处理，需应用层实现 |
| **模型管理** | 模型仓库、版本管理、热加载 | 无内建模型管理 |
| **GPU 优化** | TensorRT 集成、CUDA Graph、KV Cache 管理 | 无 GPU 推理优化 |
| **流处理** | 无 | 完整的流处理能力 |
| **状态管理** | Sequence Batching（有状态推理） | State Backend（通用状态管理） |

Triton 和 Flink 不是竞争关系，而是互补关系。Flink 负责数据编排、状态管理和流控，Triton 负责模型推理和 GPU 优化。Flink 的 `flink-model-triton` 模块正是这种互补的工程实现——Flink 算子通过 HTTP 调用 Triton 的推理接口，Triton 在服务端做 Dynamic Batching 和 GPU 调度。

### vs Kafka Streams + LLM

Kafka Streams 是轻量级的流处理方案，也可以对接 LLM API。

| 维度 | Kafka Streams + LLM | Flink |
|------|---------------------|-------|
| **异步 IO** | 无内建 AsyncFunction，需手动线程池 | AsyncDataStream 原生支持 |
| **状态管理** | RocksDB State Store，功能完备 | 多种 State Backend，Checkpoint 更成熟 |
| **反压** | 依赖 Kafka consumer 的 poll 机制 | 精确的信用制反压（第 11 章） |
| **部署模型** | 嵌入应用进程，简单 | 独立集群，运维复杂度高 |
| **SQL/Model 集成** | 无 | flink-models 模块，SQL 直接调用 LLM |

Kafka Streams 适合"简单管道 + 低运维"的场景。但当管道复杂度上升（多阶段编排、两级缓存状态、精确反控），Flink 的工程能力优势逐渐显现。AsyncDataStream 和 AsyncPredictFunction 是 Kafka Streams 无法等价替代的核心差异。

---

## 28.5 — 调优与实战陷阱

### AsyncFunction 的 capacity 配置

capacity 参数控制同时未完成的异步请求数上限。对 LLM 推理场景：

- **capacity 过小**（如 10）：并发请求数不足，GPU 利用率低，吞吐上不去。LLM API 的延迟通常 500ms-30s，如果 capacity=10，单个算子的最大吞吐约 20-200 QPS。
- **capacity 过大**（如 10000）：TaskManager 内存压力增大，因为每条未完成请求都需要缓冲区存储输入和输出。更严重的是，可能压垮下游 LLM 服务，导致超时率飙升。
- **调优建议**：从 LLM 服务的 QPS 上限出发。如果服务端最大 QPS 为 500，Flink 算子并行度为 4，则每个算子 capacity = 500 / 4 + buffer = 150 左右。同时观察 TaskManager 的堆内存使用率，确保不触发 OOM。

### LLM API 超时与重试策略

LLM API 的错误模式与常规数据库查询不同，需要针对性的策略：

- **超时设置**：Chat Completion 的延迟因输入/输出 token 数而异。短对话 500ms 可返回，长文档摘要可能需要 30s。建议 timeout 设为 P99 延迟的 2 倍。
- **重试策略**：LLM API 的 429（Rate Limit）和 503（Service Unavailable）是可重试的，但 400（Bad Request）和 401（Unauthorized）不可重试。`AbstractOpenAIModelFunction` 的 `ErrorHandlingStrategy` 支持 RETRY + FAILOVER/IGNORE 组合，建议对生产环境使用 RETRY + IGNORE（L227-243）。
- **降级逻辑**：在 `AsyncFunction.timeout()` 中实现降级，如返回缓存的历史回答或模板化响应，避免整条管道因 LLM 超时而失败。

### State 过大导致 Checkpoint 超时

Agent Memory 场景下，KeyedState 可能存储大量对话上下文。当 State 过大时，Checkpoint 的增量同步（RocksDB）或全量快照（Heap）耗时增加，可能导致：

- Checkpoint 超时，触发作业失败
- Restore 时间过长，影响 SLA

应对策略：
- 使用 RocksDB State Backend + Incremental Checkpoint，避免全量快照
- 控制单 Key 的 State 大小上限（如对话轮数 N 不超过 50 轮）
- 老数据及时归档到 VectorDB，减小 State 体积
- 适当增大 Checkpoint 间隔（如从 30s 调到 3min），降低 Checkpoint 频率

### GPU 资源碎片化

当 Flink 集群同时运行 CPU 密集型作业和 GPU 推理作业时，容易出现 GPU 资源碎片化：每个 TaskManager 都分到 1 个 GPU Slot，但 GPU 利用率只有 10%，而新提交的 GPU 作业无法获得资源。

应对策略：
- GPU 作业和 CPU 作业使用不同的 TaskManager 资源组（通过 `taskmanager.resource-id` 标签分组）
- GPU 作业使用细粒度 ResourceSpec，避免浪费
- 考虑 GPU Time-Sharing：多个小模型共享同一 GPU，通过 CUDA Stream 实现隔离

---

## 28.6 — 终极思考

Flink 对 AI 推理的意义，不在于替代专用推理引擎，而在于提供一个成熟的流式基础设施参照系。

**流处理天然适配无界数据**。用户输入是无限流，推理请求是无限流，推理结果也是无限流。批处理系统每次都要冷启动推理管道，而 Flink 的常驻算子管道让推理服务始终在线，数据到达即处理。

**状态管理天然适配 Agent Memory**。Agent 的核心挑战是记忆管理——短期对话上下文和长期知识库的协同。Flink 的 State Backend 提供了分层存储模型和自动 Checkpoint，Agent 无需关心 State 存储在内存还是 RocksDB，也无需自行实现故障恢复。

**Async IO 是 LLM API 与真实世界之间的桥梁**。LLM API 调用的本质是高延迟的外部服务调用，Flink 的 AsyncDataStream 让单条 Task 线程同时维持数百个并发请求而不阻塞，这为 LLM 推理管道提供了天然的并发模型。

**调度分层允许 GPU 和 CPU 混合集群协同工作**。Flink 的 ResourceProfile + ExternalResource 机制可以声明 GPU 需求，SlotManager 可以扩展为 GPU 亲和调度器，让推理算子被调度到已加载模型权重的 GPU 节点上。

当"推理=函数、状态=记忆、调度=资源分配"时——Flink 给出了这些问题在数据工程领域最成熟的答案。它不是最优的推理引擎，但它是从数据工程视角审视 AI 推理系统的最佳参照系之一。

---

## 本章要点回顾

1. Flink 的流处理、状态管理、异步 IO 三大能力与 AI 推理场景的结构性需求同构——这是 Flink 适配 AI 推理的根本原因。
2. AsyncDataStream + mailbox 模型允许单线程维持数百并发 LLM 请求而不阻塞，是 LLM API 集成的核心模式。
3. State Backend 的分层存储模型天然适配 Agent Memory 的冷热分层需求：KeyedState 存短期对话，VectorDB 存长期知识。
4. GPU 亲和调度可以在 ResourceProfile + ExternalResource + RequirementMatcher 上逐步扩展，不需要架构大改。
5. Flink AI Model 模块（flink-model-openai / flink-model-triton）以 AsyncPredictFunction 为基类，验证了 Async IO + LLM 的工程可行性。
6. Flink 与 Ray Serve、Triton、Kafka Streams 各有定位：Flink 提供流式编排和状态管理，Triton 提供 GPU 推理优化，两者互补而非竞争。

## 源码导航

- **AsyncFunction**：`org.apache.flink.streaming.api.functions.async.AsyncFunction` — 异步 IO 函数接口
- **AsyncDataStream**：`org.apache.flink.streaming.api.datastream.AsyncDataStream` — 异步 IO 工具类
- **ResultFuture**：`org.apache.flink.streaming.api.functions.async.ResultFuture` — 异步结果回调
- **AsyncPredictFunction**：`org.apache.flink.table.functions.AsyncPredictFunction` — 异步推理函数基类
- **AbstractOpenAIModelFunction**：`org.apache.flink.model.openai.AbstractOpenAIModelFunction` — OpenAI 集成基类
- **OpenAIChatModelFunction**：`org.apache.flink.model.openai.OpenAIChatModelFunction` — OpenAI Chat 推理实现
- **AbstractTritonModelFunction**：`org.apache.flink.model.triton.AbstractTritonModelFunction` — Triton 集成基类
- **TritonCircuitBreaker**：`org.apache.flink.model.triton.TritonCircuitBreaker` — Triton 熔断器
- **GPUDriver**：`org.apache.flink.externalresource.gpu.GPUDriver` — GPU 资源发现驱动
- **GPUInfo**：`org.apache.flink.externalresource.gpu.GPUInfo` — GPU 资源信息
- **ResourceProfile**：`org.apache.flink.runtime.clusterframework.types.ResourceProfile` — 资源画像（含 ExternalResource）
- **DefaultRequirementMatcher**：`org.apache.flink.runtime.slots.DefaultRequirementMatcher` — 资源需求匹配器
