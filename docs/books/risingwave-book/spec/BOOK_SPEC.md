# 《RisingWave 内核实现原理深度解析》全书 Spec

> **定位**：从源码出发，以第一性原理思维逐层拆解 RisingWave 流数据库内核实现。面向有分布式查询引擎经验（Spark/StarRocks/MaxCompute）的工程师。
> **源码路径**：`/Users/lism/work/risingwave`
> **输出目录**：`/Users/lism/work/risingwave-book/chapters/`
> **生成顺序**：从第二部分开始（Frontend→Stream→Storage→Meta），第一部分（总览）最后写，因为总览需要汇总后续所有章节的知识点。

---

## 第一部分：总体架构与设计哲学

### 第 1 章 · 流数据库的第一性原理
- 1.1 从"查询-响应"到"持续计算"的范式转换
- 1.2 增量计算 vs 全量重算：What, When, How
- 1.3 Stream-Table Duality 在工程实现中的映射
- 1.4 RisingWave 的架构全景图（Ingest → Process → Serve → Store）
- 1.5 与 Spark Streaming / Flink / ksqlDB 的核心差异

### 第 2 章 · 项目工程结构导览
- 2.1 Workspace 组织：`src/` 下各 crate 的职责边界
- 2.2 构建系统与 risedev 开发者工具链
- 2.3 Protobuf 定义与组件间契约（`proto/` 目录）
- 2.4 启动流程：从 `cmd_all` 看六大组件（frontend / compute / meta / compactor / connector）

---

## 第二部分：SQL 编译链路——从文本到流计算图

### 第 3 章 · SQL 解析器（sqlparser）
- 3.1 Fork 自 Apache DataFusion 的 sqlparser-rs
- 3.2 PostgreSQL 语法兼容策略：Parser 层面扩展点
- 3.3 DDL 特有语法：CREATE MATERIALIZED VIEW / SOURCE / SINK / INDEX
- 3.4 AST 节点全景与关键代码路径
- 核心源码：`src/sqlparser/`

### 第 4 章 · Binder——语义分析
- 4.1 Catalog 体系：Schema → Table → Column 的抽象树
- 4.2 名字解析（Name Resolution）与类型推导
- 4.3 `BoundStatement`——语义分析后的中间表示
- 4.4 Bind Source / Bind MV / Bind Sink 的差异化逻辑
- 核心源码：`src/frontend/src/binder/`

### 第 5 章 · Planner——逻辑计划生成
- 5.1 从 BoundStatement 到 LogicalPlan
- 5.2 `PlanNode` 树与 `PlanRoot` 的统一抽象
- 5.3 关键算子逻辑计划：TableScan / Project / Filter / Join / Agg / TopN
- 核心源码：`src/frontend/src/planner/`

### 第 6 章 · Optimizer——查询优化器
- 6.1 优化器架构：Rule-based（Heuristic）→ Cost-based（Cascades）
- 6.2 核心优化规则：Predicate Pushdown / Column Pruning / Join Reorder
- 6.3 流式特有优化：Watermark Propagation / State Cleanup Strategy
- 6.4 `PlanRef` 的内部克隆模式与不可变计划树
- 核心源码：`src/frontend/src/optimizer/`

### 第 7 章 · 物理计划到 Fragment Graph
- 7.1 物理算子与并行度决策（Distribution Key / Vnode Bitmap）
- 7.2 Fragmenter：如何切分出 Fragment（Exchange 作为边界）
- 7.3 StreamJob → TableFragments → Actor 的拓扑生成
- 7.4 DDL Handler：`handler/` 下每种语句的处理全流程
- 核心源码：`src/frontend/src/handler/`, `src/meta/src/stream/`

---

## 第三部分：流计算引擎——数据流动的心脏

### 第 8 章 · 核心抽象：Message / Barrier / Executor
- 8.1 消息模型：`Message = Chunk | Barrier | Watermark`
- 8.2 `Barrier` 的本质：全局时钟 + 控制指令载体
- 8.3 `Mutation` 的类型体系：Stop / Update / Add / Pause / Resume...
- 8.4 `Execute` trait 与 `Executor` 的双层封装
- 8.5 `MessageBatch` 与 Actor 内/Actor 间的消息格式转换
- 核心源码：`src/stream/src/executor/mod.rs`

### 第 9 章 · Actor 模型——流计算的调度单元
- 9.1 Actor 是什么：由一个或多个 Executor 组成的拓扑执行体
- 9.2 `ActorContext`：Actor 的运行时上下文
- 9.3 `LocalBarrierManager`：Actor 内的屏障协调器
- 9.4 Actor 生命周期：创建→运行→暂停→恢复→销毁
- 9.5 对比：Actor 模型 vs Flink Task/Subtask vs Spark Stage/Task
- 核心源码：`src/stream/src/executor/actor.rs`, `src/stream/src/task/`

### 第 10 章 · 数据流动：Exchange 与 Dispatch
- 10.1 `exchange::input` / `exchange::output`：Actor 间数据传输
- 10.2 `MergeExecutor`：多上游对齐与 Barrier Alignment 算法（`DynamicReceivers`）
- 10.3 `DispatchExecutor` 与 `DispatchBarrierBuffer`：上下游变更的两阶段应用
- 10.4 `BarrierRecvExecutor`：本地 Barrier 注入入口
- 10.5 传输语义：Exactly-Once 的实现机制
- 核心源码：`src/stream/src/executor/exchange/`, `src/stream/src/executor/merge.rs`, `src/stream/src/executor/dispatch.rs`

### 第 11 章 · 算子实现精析（上）——无状态算子
- 11.1 `SourceExecutor`：外部数据接入统一抽象，Split 分配与 Failover
- 11.2 `ChainExecutor`：快照读取 + 增量消费衔接
- 11.3 `FilterExecutor` / `ProjectExecutor`：行级变换
- 11.4 `UnionExecutor` / `ExpandExecutor`：多路合并与展开
- 11.5 `RowMergeExecutor`：多流合并去重
- 11.6 `WatermarkFilterExecutor` / `HopWindowExecutor`：窗口水位线过滤
- 核心源码：`src/stream/src/executor/source/`, `src/stream/src/executor/chain.rs`, etc.

### 第 12 章 · 算子实现精析（中）——连接算子
- 12.1 `HashJoinExecutor`：流式 Hash Join 状态管理
  - 12.1.1 Join 编码格式与 Degree 表
  - 12.1.2 Delta Join 算法的工程实现
- 12.2 `TemporalJoinExecutor`：基于版本的时间对齐
- 12.3 `AsOfJoinExecutor`：快照精确连接
- 12.4 `LookupJoinExecutor`：维表 Join 的 Lookup 模式
- 12.5 `NestedLoopTemporalJoinExecutor`：宽表展开
- 核心源码：`src/stream/src/executor/hash_join.rs`, `src/stream/src/executor/join/`

### 第 13 章 · 算子实现精析（下）——聚合与 TopN
- 13.1 `SimpleAggExecutor` / `HashAggExecutor`：流式聚合
- 13.2 `GlobalApproxPercentileExecutor` + `LocalApproxPercentileExecutor`：近似计算
- 13.3 `MaterializeExecutor`：物化视图的边界执行器与冲突检测
- 13.4 `TopNExecutor` / `GroupTopNExecutor` / `AppendOnlyTopNExecutor`：流式 Top-N
- 13.5 `OverWindowExecutor` / `EowcOverWindowExecutor`：窗口计算
- 13.6 `GapFillExecutor`：时间序列空洞补齐
- 核心源码：`src/stream/src/executor/aggregate/`, `src/stream/src/executor/top_n/`

### 第 14 章 · Backfill——历史数据与增量流的合流
- 14.1 为什么需要 Backfill：Snapshot + Stream 双流模式
- 14.2 `ArrangementBackfill`：基于 Sorted Index 的有序回填
- 14.3 `SnapshotBackfill` / `NoShuffleBackfill`：快照回填模式
- 14.4 `CdcBackfillExecutor`：CDC 全量+增量同步
- 14.5 Backfill 中的屏障协调与进度跟踪
- 核心源码：`src/stream/src/executor/backfill/`

### 第 15 章 · Source 与 Sink 深度剖析
- 15.1 `SourceExecutor` 内部状态机
- 15.2 Split 变更：`SourceChangeSplit` Mutation 的处理流程
- 15.3 `SinkExecutor`：输出管道的完整链路
- 15.4 `UpstreamSinkUnionExecutor`：Sink into Table 的逆向流
- 15.5 Sink Schema Change 与 `ConnectorPropsChange` Mutation
- 核心源码：`src/stream/src/executor/source/`, `src/stream/src/executor/sink.rs`

---

## 第四部分：存储引擎 Hummock——云原生 LSM

### 第 16 章 · Hummock 总体架构
- 16.1 三层存储模型：Shared Buffer → SSTable → Object Store
- 16.2 为什么不是 RocksDB：Kv Separation / Remote Compaction / Shared Storage
- 16.3 Key 编码体系：TableKey / FullKey / UserKey / Epoch
- 16.4 VNode 在存储层的分区映射
- 核心源码：`src/storage/src/hummock/mod.rs`, `src/storage/src/hummock_sdk/`

### 第 17 章 · 写入路径：MemTable 到 Shared Buffer
- 17.1 `MemTable`：内存写入缓冲区
- 17.2 `ImmutableMemtable` 的 Flush 触发条件与流程
- 17.3 `SharedBuffer` 的 Upload 机制
- 17.4 `WriteLimiter` 写入流控策略
- 核心源码：`src/storage/src/mem_table.rs`, `src/storage/src/hummock/shared_buffer/`

### 第 18 章 · SSTable 格式与读取路径
- 18.1 SSTable 的 Block 结构：Meta Block / Data Block / Bloom Filter
- 18.2 `SstableIterator`：有序扫描的核心迭代器
- 18.3 `BlockCache`：内存中 SST Block 的 LRU 缓存
- 18.4 读取路径：`get_from_sstable_info` → Bloom Filter → Block Fetch
- 18.5 `BlockStream`：异步 SST Block 预取
- 核心源码：`src/storage/src/hummock/sstable/`, `src/storage/src/hummock/block_cache.rs`

### 第 19 章 · Compaction 与版本管理
- 19.1 Hummock Version：SST 集合的 MVCC 视图
- 19.2 `LocalVersionManager`：计算节点本地版本维护
- 19.3 `HummockObserver`：版本变更订阅与同步
- 19.4 Compactor：Level-Based 的远程 Compaction 策略
- 19.5 Time Travel 查询与 Backup / Recovery
- 19.6 `RecentFilter`：减少 Compaction 读取放大
- 核心源码：`src/storage/src/hummock/local_version/`, `src/storage/src/compactor/`

---

## 第五部分：Meta Service——集群的大脑

### 第 20 章 · Catalog 与元数据管理
- 20.1 元数据持久化：SeaORM + PostgreSQL 的 Schema 设计
- 20.2 Controller 层：对 Catalog 操作的统一封装
- 20.3 `NotificationVersion`：Catalog 变更通知机制
- 20.4 Database / Schema / Table / Source / Sink / MV / Index 的统一与差异
- 核心源码：`src/meta/src/model/`, `src/meta/src/controller/`

### 第 21 章 · Barrier 全局协调
- 21.1 `GlobalBarrierManager`：系统唯一 Barrier 生成器
- 21.2 `BarrierScheduler`：屏障周期性注入与 Checkpoint 策略
- 21.3 Barrier Collect：从所有 Compute Node 收集 Barrier 响应
- 21.4 分布式 Checkpoint 的一致性保障
- 核心源码：`src/meta/src/barrier/`

### 第 22 章 · 流图管理与扩缩容
- 22.1 `StreamManager`：创建/修改/删除 Streaming Job 的全局入口
- 22.2 `stream_graph.rs`：Stream Node → Fragment → Actor 的生成管道
- 22.3 并行度变更：Rescheduling 的编排流程
- 22.4 `SourceManager` / `RefreshManager`：Source 发现与 MV 刷新
- 核心源码：`src/meta/src/stream/`

---

## 第六部分：高级主题与实践

### 第 23 章 · 一致性与容错
- 23.1 Exactly-Once 语义的端到端实现分析
- 23.2 `consistency_panic!`：防御性一致性检查机制
- 23.3 Failover 恢复：从 Checkpoint 重启 Actor
- 23.4 Insane Mode（`RW_UNSAFE_ENABLE_INSANE_MODE`）的设计意图
- 核心源码：`src/stream/src/lib.rs` (consistency 模块)

### 第 24 章 · 性能调优与资源管理
- 24.1 `StreamingConfig` 关键参数深度解读
- 24.2 Chunk Size / Barrier Interval / Throttle 的调优实践
- 24.3 Memory Manager：统一内存分配与流控（`common/src/memory/`）
- 24.4 监控指标体系：Metrics 埋点设计
- 核心源码：`src/common/src/config/`, `src/common/src/memory/`, `src/storage/src/monitor/`

### 第 25 章 · 扩展 RisingWave
- 25.1 添加新 SQL 语法的全链路（Parser → Binder → Planner → Handler）
- 25.2 添加新流式算子的规范流程
- 25.3 添加新 Connector（Source / Sink）的接口契约
- 25.4 添加新表达式/函数（`src/expr/impl/` 扩展指南）
- 25.5 UDF / UDAF 接入方式

### 第 26 章 · AI 时代的 RisingWave
- 26.1 Event Streaming for Agentic AI：流计算如何赋能 LLM Agent
- 26.2 Iceberg + DataFusion：开放格式下的混合工作负载
- 26.3 实时特征工程与在线推理的数据管道设计
- 26.4 Streaming Database vs 向量数据库的协同模式

---

## 附录

### 附录 A · 关键数据结构速查表
### 附录 B · 核心 trait 与接口索引
### 附录 C · 配置参数完整列表
### 附录 D · 源码阅读建议路线

---

## 生成约定

1. **每章一个文件**：`chapters/XX-章节名.md`（如 `chapters/08-核心抽象.md`）
2. **行级源码引用**：关键代码片段从源码中提取，标注文件路径和行号
3. **可独立阅读**：每章有完整的上下文，不依赖前后章节
4. **穿插"思考盒子"**：在关键设计决策处，插入第一性原理分析段落
5. **图表**：用 ASCII art 绘制核心流程图，复杂架构图说明去向
6. **代码语言**：所有代码块标注 `rust`
7. **目标深度**：每章 3000-8000 字中文，具体取决于源码复杂度
8. **生成顺序**：第二部分→第三部分→第四部分→第五部分→第六部分→第一部分→附录
