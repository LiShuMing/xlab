# 附录 C · FLIP 索引

FLIP = Flink Improvement Proposal。每个 FLIP 记录了 Flink 核心改动的设计讨论和决策过程。以下是与本书各章对应的关键 FLIP，每条附有一句话概要。

## 架构与运行时

| FLIP | 标题 | 简要说明 | 对应章节 |
|------|------|---------|---------|
| FLIP-1 | TaskManager Memory Model | 重新设计 TM 内存模型，将堆内/堆外/网络缓冲统一划分 | 第 4 章 |
| FLIP-49 | Unified Memory Configuration | 统一内存配置项，用 process/framwork/task/network 四大块替代旧模型 | 第 4 章 |
| FLIP-53 | Fine Grained Resource Management | 允许每个算子独立声明 CPU/GPU/内存等细粒度资源需求 | 第 6,7 章 |
| FLIP-56 | Dynamic Slot Allocation | 支持按需动态分配与释放 Slot，避免资源浪费 | 第 6,7 章 |
| FLIP-84 | Adaptive Scheduler | 根据可用资源自动调整并行度的调度器 | 第 6 章 |
| FLIP-116 | Unified Memory Configuration for JobManager | 将 JM 内存配置也纳入统一模型 | 第 4 章 |
| FLIP-119 | Pipelined Region Scheduler | 按 Pipelined Region 粒度调度，避免流水线死锁 | 第 6 章 |
| FLIP-164 | Job Terminated State | 引入 FINISHED/CANCELED/FAILED 等终止态，统一 Job 生命周期语义 | 第 6 章 |
| FLIP-168 | Adaptive Batch Scheduler | 批作业自适应并行度调度器，运行时推断最优并行度 | 第 6 章 |
| FLIP-222 | Adaptive Scheduler | 增强版自适应调度器，支持流批统一的自适应并行度推断 | 第 6 章 |
| FLIP-226 | Dynamic Slot Allocation for Adaptive Scheduler | 为自适应调度器提供动态 Slot 分配能力 | 第 6,7 章 |
| FLIP-6 | Reactive Mode | 让 Flink 在 Reactive 模式下自动跟随可用 TM 数调整并行度 | 第 6,7 章 |

## Checkpoint & State

| FLIP | 标题 | 简要说明 | 对应章节 |
|------|------|---------|---------|
| FLIP-76 | Unaligned Checkpoints | 跳过 Barrier 对齐，将缓冲区数据一起快照以降低延迟 | 第 12 章 |
| FLIP-147 | Sort-Merge Based Blocking Shuffle | 批作业的排序归并阻塞 Shuffle 实现 | 第 17 章 |
| FLIP-148 | Introduce Sort-Based Blocking Shuffle | 引入基于排序的阻塞 Shuffle 替代原有 Hash Shuffle | 第 17 章 |
| FLIP-151 | Incremental Checkpoint | 只保存与上次 Checkpoint 差异的状态数据，减少 I/O | 第 12,13 章 |
| FLIP-158 | Changelog State Backend | 将状态变更持续写入日志，实现亚秒级故障恢复 | 第 15 章 |
| FLIP-190 | Checkpoint File Merging | 将大量小文件合并为少量大文件，缓解文件系统压力 | 第 13 章 |
| FLIP-325 | Buffer Debloating / Back Pressure Monitor | 根据反压自动调整网络 Buffer 大小，并改进反压监控指标 | 第 11 章 |
| FLIP-477 | StateBackend V2 (ForSt) | 引入基于 LSM 的新一代状态后端 ForSt | 第 13 章 |

## Stream 处理

| FLIP | 标题 | 简要说明 | 对应章节 |
|------|------|---------|---------|
| FLIP-27 | Refactor Source Interface | 将 Source 拆分为 SplitEnumerator + SourceReader 的新接口 | 第 23 章 |
| FLIP-126 | Watermark Alignment | 让多个 Source 的 Watermark 推进保持一致，避免数据倾斜 | 第 8 章 |
| FLIP-143 | Unified Sink API (v2) | 统一批/流 Sink 为 Writer + Committer + GlobalCommitter 三段式 | 第 23 章 |
| FLIP-186 | Mailbox-based Operator Model | 用邮箱模型替代同步锁，实现 Task 线程的协作式调度 | 第 9,10 章 |
| FLIP-191 | Extend Unified Sink API | 在 v2 基础上扩展支持多 Table/SQL 场景的 Sink 语义 | 第 23 章 |
| FLIP-231 | Event-time Temporal Join | 支持基于事件时间的时态关联，替代 Processing Time 版本 | 第 18 章 |

## Table / SQL

| FLIP | 标题 | 简要说明 | 对应章节 |
|------|------|---------|---------|
| FLIP-32 | Restructure flink-table | 将 flink-table 拆分为多个子模块以便社区贡献 | 第 18 章 |
| FLIP-95 | New Table Source and Sink Interfaces | 引入 DynamicTableSource/Sink 替代旧版 TableSource 接口 | 第 18,23 章 |
| FLIP-122 | New Data Structures (RowData) | 用二进制 RowData 替代 Row 对象，降低序列化开销 | 第 21 章 |
| FLIP-136 | DataStream and Table API Interop | 改进 DataStream 与 Table API 之间的互操作能力 | 第 18 章 |
| FLIP-152 | Hybrid Shuffle Mode | 内存 + 磁盘混合 Shuffle，兼顾流式低延迟与批式高吞吐 | 第 17 章 |
| FLIP-162 | Batch Execution Mode | 为 Table/SQL 引入批执行模式，关闭 Checkpoint 与 Watermark | 第 18 章 |
| FLIP-163 | Sort-Based Blocking Shuffle | 批模式下基于排序的阻塞 Shuffle，减少小文件并支持压缩 | 第 17 章 |
| FLIP-188 | Introduce SQL Gateway | 提供多租户 SQL 网关服务，支持远程提交与执行 SQL | 第 22 章 |
| FLIP-200 | Materialized Table | 引入物化表概念，支持增量维护的物化视图 | 第 22 章 |
| FLIP-235 | JDBC Driver for SQL Gateway | 为 SQL Gateway 提供 JDBC 驱动，兼容 BI 工具直连 | 第 22 章 |

## 部署与生态

| FLIP | 标题 | 简要说明 | 对应章节 |
|------|------|---------|---------|
| FLIP-111 | Standalone Kubernetes Support | 在独立模式下支持 Kubernetes 部署 Flink 集群 | 第 25 章 |
| FLIP-138 | Native Kubernetes Support | 原生 Kubernetes 集成，JM 直接调 K8s API 申请/释放 Pod | 第 25 章 |
| FLIP-210 | GPU as Managed Resource | 将 GPU 作为 Flink 可管理资源，自动发现与分配 GPU 设备 | 第 25 章 |

## FLIP 与本书各章的对应关系

下表展示本书各章涉及的主要 FLIP，便于按阅读顺序查阅：

| 章节 | 涉及 FLIP |
|------|----------|
| 第 4 章（内存模型） | FLIP-1, FLIP-49, FLIP-116 |
| 第 5 章（图结构） | — |
| 第 6 章（调度） | FLIP-6, FLIP-84, FLIP-119, FLIP-164, FLIP-168, FLIP-222 |
| 第 7 章（资源） | FLIP-53, FLIP-56, FLIP-226 |
| 第 8 章（时间与水位） | FLIP-126 |
| 第 9 章（算子模型） | FLIP-186 |
| 第 10 章（Task 执行） | FLIP-186 |
| 第 11 章（网络与反压） | FLIP-325 |
| 第 12 章（检查点） | FLIP-76, FLIP-151 |
| 第 13 章（状态后端） | FLIP-151, FLIP-190, FLIP-477 |
| 第 15 章（Changelog） | FLIP-158 |
| 第 17 章（Shuffle） | FLIP-147, FLIP-148, FLIP-152, FLIP-163 |
| 第 18 章（Table API） | FLIP-32, FLIP-95, FLIP-136, FLIP-162, FLIP-231 |
| 第 19 章（SQL 优化） | — |
| 第 21 章（数据结构） | FLIP-122 |
| 第 22 章（SQL Gateway） | FLIP-188, FLIP-200, FLIP-235 |
| 第 23 章（连接器） | FLIP-27, FLIP-95, FLIP-143, FLIP-191 |
| 第 25 章（部署） | FLIP-111, FLIP-138, FLIP-210 |

## FLIP 编号速查

按编号升序排列，方便从源码注释中的 `FLIP-XX` 标签快速定位：

| 编号 | 分类 | 关键词 |
|------|------|--------|
| FLIP-1 | 运行时 | TM 内存模型 |
| FLIP-6 | 运行时 | Reactive Mode |
| FLIP-27 | Stream | Source 接口重构 |
| FLIP-32 | Table | flink-table 模块拆分 |
| FLIP-49 | 运行时 | 统一内存配置 |
| FLIP-53 | 运行时 | 细粒度资源管理 |
| FLIP-56 | 运行时 | 动态 Slot 分配 |
| FLIP-76 | State | 非对齐检查点 |
| FLIP-84 | 运行时 | 自适应调度器 |
| FLIP-95 | Table | 新 Table Source/Sink 接口 |
| FLIP-111 | 部署 | Standalone K8s |
| FLIP-116 | 运行时 | JM 统一内存 |
| FLIP-119 | 运行时 | 流水线区域调度 |
| FLIP-122 | Table | RowData 数据结构 |
| FLIP-126 | Stream | Watermark 对齐 |
| FLIP-136 | Table | DataStream/Table 互操作 |
| FLIP-138 | 部署 | Native K8s |
| FLIP-143 | Stream | 统一 Sink API v2 |
| FLIP-147 | Shuffle | 排序归并阻塞 Shuffle |
| FLIP-148 | Shuffle | 排序阻塞 Shuffle |
| FLIP-151 | State | 增量检查点 |
| FLIP-152 | Table | 混合 Shuffle |
| FLIP-158 | State | Changelog 状态后端 |
| FLIP-162 | Table | 批执行模式 |
| FLIP-163 | Shuffle | 排序阻塞 Shuffle |
| FLIP-164 | 运行时 | Job 终止态 |
| FLIP-168 | 运行时 | 自适应批调度器 |
| FLIP-186 | Stream | 邮箱算子模型 |
| FLIP-188 | Table | SQL Gateway |
| FLIP-190 | State | 检查点文件合并 |
| FLIP-191 | Stream | Sink API 扩展 |
| FLIP-200 | Table | 物化表 |
| FLIP-210 | 部署 | GPU 资源管理 |
| FLIP-222 | 运行时 | 增强自适应调度器 |
| FLIP-226 | 运行时 | 自适应调度动态 Slot |
| FLIP-231 | Stream | 事件时间时态关联 |
| FLIP-235 | Table | SQL Gateway JDBC |
| FLIP-325 | State | Buffer Debloating |
| FLIP-477 | State | StateBackend V2 (ForSt) |

## 相关 FLIP 的源码定位

FLIP 的讨论可以在 Flink Wiki 找到，对应的 `FLIP-XX` 标签通常在对应源码的文件头部注释里出现。例：

```java
// flink-core/.../source/SourceReader.java
/**
 * FLIP-27 核心接口
 */
```

定位步骤：

1. 确定目标 FLIP 编号（如 FLIP-27）
2. 在 Wiki 查阅设计文档，确定涉及的模块和核心类
3. 在源码中搜索 `FLIP-27` 注释标签，定位具体实现文件
4. 对照本章内容阅读源码，理解设计意图与实现细节
