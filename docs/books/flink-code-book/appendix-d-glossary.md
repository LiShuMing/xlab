# 附录 D · 术语对照表

## 核心架构术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **JobManager** | 作业管理器 | Flink 集群的主进程，包含 Dispatcher、RM、JobMaster | 第 1 章 |
| **TaskManager** | 任务管理器 | 运行实际 Task 的工作进程 | 第 1 章 |
| **JobMaster** | 作业主控 | 每个 Job 的核心调度/容错组件 | 第 1 章 |
| **Dispatcher** | 调度分发器 | 接收任务提交、启动 JobMaster 的入口 | 第 1 章 |
| **ResourceManager** | 资源管理器 | 管理 TaskManager 和 Slot 分发 | 第 1 章 |
| **Slot** | 插槽 | Flink 的资源分片单位（一块内存） | 第 1,7 章 |
| **SlotSharingGroup** | Slot 共享组 | 允许不同算子共用 Slot 的机制 | 第 7 章 |
| **WorkerResourceSpec** | 工作节点资源规格 | 描述 TM 所需的 CPU、内存等资源规格 | 第 7 章 |

## 图结构术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **StreamGraph** | 流图 | 用户层 API 拓扑（最接近源码） | 第 5 章 |
| **JobGraph** | 作业图 | 优化后的执行图（算子链合并后） | 第 5 章 |
| **ExecutionGraph** | 执行图 | 物理执行图（并行度展开后） | 第 5 章 |
| **JobVertex** | 作业顶点 | JobGraph 中的节点 | 第 5 章 |
| **ExecutionVertex** | 执行顶点 | ExecutionGraph 中的节点 | 第 5 章 |
| **IntermediateResult** | 中间结果 | 一个 JobVertex 的产出 | 第 5 章 |
| **IntermediateResultPartition** | 中间结果分区 | 中间结果的一个并行分片 | 第 5 章 |
| **Pipeline** | 流水线 | 从 Source 到 Sink 的一条完整数据处理管线 | 第 5 章 |
| **Boundedness** | 有界性 | 描述数据流是否有界（BOUNDED / UNBOUNDED） | 第 2 章 |

## 内存与缓冲术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **MemorySegment** | 内存段 | Flink 自定义的 32KB 定长二进制缓冲区 | 第 2,4 章 |
| **NetworkBufferPool** | 网络缓冲池 | 所有 Slot 共享的全局 Buffer 池 | 第 4 章 |
| **LocalBufferPool** | 本地缓冲池 | 每个 Task 的 Buffer 配额 | 第 4 章 |
| **ManagedMemory** | 管理内存 | Flink 对批/State 管理的推外内存 | 第 4 章 |
| **Tiered Storage** | 层级存储 | 热数据在内存、温数据在本地 SSD、冷数据在远端的分层存储策略 | 第 13 章 |

## 网络与 Shuffle 术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **RecordWriter** | 记录写出器 | 算子产出到网络栈的写网关 | 第 10,16 章 |
| **ResultPartition** | 结果分区 | 生产端的数据输出分区 | 第 16 章 |
| **ResultSubpartition** | 结果子分区 | 一个消费者对应一个子分区 | 第 16 章 |
| **InputGate** | 输入门 | 消费端的所有输入通道入口 | 第 16 章 |
| **InputChannel** | 输入通道 | 对单个上游 Subpartition 的消费通道 | 第 16 章 |
| **Credit-based Flow Control** | 信用流控 | 下游给上游"能接受 N 个 Buffer"的信用 | 第 11 章 |
| **Backpressure** | 反压 | 下游慢时上游自动降速的机制 | 第 11 章 |
| **Hybrid Shuffle** | 混合 Shuffle | 内存 + 磁盘的统一收发模式 | 第 17 章 |

## 调度术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **PipelinedRegion** | 流水线区域 | 调度时按边类型切分的独立调度单元 | 第 6 章 |
| **OperatorChain** | 算子链 | 多个算子串在同一个线程中跑 | 第 9 章 |
| **OperatorID** | 算子标识 | 算子在运行时的全局唯一标识，用于状态恢复匹配 | 第 14 章 |

## 执行模型术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **StreamTask** | 流任务 | TaskManager 上运行的基本执行单元 | 第 10 章 |
| **MailboxProcessor** | 邮箱处理器 | Task 线程的用户态合作调度器 | 第 10 章 |
| **AsyncFunction** | 异步函数 | 支持异步 I/O 操作的算子函数，避免阻塞主线程 | 第 9 章 |
| **MiniBatch** | 小批次 | 将流数据按微批攒条后再处理，减少状态访问频率 | 第 20 章 |
| **LocalGlobalAgg** | 本地全局聚合 | 两阶段聚合策略：本地预聚合消除数据倾斜，全局聚合保证正确性 | 第 20 章 |

## 时间与水印术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **Watermark** | 水位线 | 表示"所有事件时间 <= t 的数据都到了" | 第 8 章 |
| **CheckpointBarrier** | 检查点屏障 | 在 DAG 上流动的快照标记 | 第 12 章 |

## 容错与状态术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **Checkpoint** | 检查点 | 全局一致性快照（故障恢复用） | 第 12 章 |
| **Savepoint** | 保存点 | 用户手动触发的永久快照（升级用） | 第 14 章 |
| **Aligned Checkpoint** | 对齐检查点 | 等待所有通道 Barrier 到齐再拍 | 第 12 章 |
| **Unaligned Checkpoint** | 非对齐检查点 | 不等待、附带在途数据进行快照 | 第 12 章 |
| **CheckpointCoordinator** | 检查点协调器 | 全局协调 Checkpoint 周期的组件 | 第 12 章 |
| **StateBackend** | 状态后端 | 可插拔的算子状态存储层 | 第 13 章 |
| **KeyedStateBackend** | 键控状态后端 | KeyBy 之后的状态管理 | 第 13 章 |
| **KeyGroup** | 键组 | Key 空间的哈希分片单位 | 第 13 章 |
| **TypeSerializer** | 类型序列化器 | Flink 自定义的二进制序列化协议 | 第 2 章 |
| **TypeSerializerSnapshot** | 类型序列化器快照 | 序列化器的版本元数据，用于状态恢复时兼容性校验 | 第 2 章 |

## Source / Sink 术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **SplitEnumerator** | 分片枚举器 | FLIP-27 Source 中负责发现和分配数据分片的组件 | 第 23 章 |
| **SourceReader** | 源读取器 | FLIP-27 Source 中实际读取数据并输出记录的组件 | 第 23 章 |
| **Committer** | 提交器 | FLIP-143 Sink 中负责两阶段提交的组件 | 第 23 章 |

## Table / SQL 术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **TableEnvironment** | 表环境 | Table/SQL API 的入口上下文，管理 Catalog、模块和执行配置 | 第 18 章 |
| **Catalog** | 目录（元数据中心） | 管理数据库、表、函数等元数据的统一注册中心 | 第 18 章 |
| **DataStream** | 数据流 | DataStream API 的核心抽象，表示一个并行数据流 | 第 2 章 |
| **DynamicTableSource** | 动态表源 | Flink SQL 连接器的通用 SPI，支持扫描与查找两种模式 | 第 18 章 |
| **MaterializedTable** | 物化表 | 持续维护的增量物化视图 | 第 22 章 |
| **SQL Gateway** | SQL 网关 | 多租户 SQL 流服务端入口 | 第 22 章 |
| **Calcite** | Calcite | Apache 的 SQL 解析/优化框架 | 第 19 章 |
| **ChangelogMode** | 变更日志模式 | INSERT/UPSERT/RETRACT 语义标记 | 第 19 章 |
| **CodeGen** | 代码生成 | 动态字节码生成（Janino） | 第 20 章 |
| **BinaryRowData** | 二进制行数据 | Flink SQL 的行式内部表示 | 第 21 章 |
| **ColumnarRowData** | 列式行数据 | Flink SQL 的列式内部表示 | 第 21 章 |
| **RowData** | 行数据接口 | Flink SQL 的 Row 统一接口 | 第 21 章 |
| **NormalizedKey** | 归一化键 | 排序时将关键字段归一化为定长前缀，加速比较 | 第 21 章 |
| **ExecNode** | 执行节点 | SQL 逻辑执行计划中的物理算子节点 | 第 19 章 |

## 部署与资源术语

| 英文 | 中文 | 说明 | 首次出现章节 |
|------|------|------|------------|
| **ExternalResource** | 外部资源 | GPU/FPGA 等非标准资源管理 | 第 25 章 |
| **ActiveResourceManager** | 主动资源管理器 | 按需申请容器的动态 RM | 第 25 章 |
| **Vors** | ForSt | Flink 新一代 LSM-based State Backend | 第 13 章 |
