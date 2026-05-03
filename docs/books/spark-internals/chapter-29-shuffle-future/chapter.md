# 第 29 章：Shuffle 的下一个十年 — 存算分离与硬件革命

## 设计动机

Spark 的 Shuffle 架构本质上是一个三阶段的旅程。每一阶段都解决了一组 "Shuffle 出了什么问题" 但引入了新的瓶颈：

```
第一代 (Spark 1.x-2.x, 2014-2019): Shuffle File
  - 直接写本地磁盘 → Reducer 通过网络拉取
  - 瓶颈: Executor shuffle 磁盘空间绑定计算节点
          磁盘 I/O 邻接影响(J) → Executor 多作业共享同一块磁盘
          节点故障 → Shuffle 数据丢光 → 全量重算

第二代 (Spark 3.x+, 2019-2025): External Shuffle Service + Push-based
  - ESS 解耦 Shuffle 服务与 Executor 生命周期
  - Push-based merge → Reducer 读少量合并文件
  - 瓶颈: ESS 仍与 NM 绑定 → 数据不独立于计算节点
          push 过程没有成熟的容错语义
          单一 ESS 吞吐仍受限于单机磁盘 + 网络 BDP

第三代 (2025-): 存算分离 Shuffle
  - Shuffle 数据不再绑定到计算节点上
  - 专门的 Shuffle 集群 (Celeborn, Uniffle) 作为持久化服务
  - 硬件加速: NVMe pools, RDMA, CXL shared memory, SmartNIC/FPGA
```

从第一性原理看，Shuffle 的本质是什么？是**生产者-消费者的数据暂存问题**。Map 端把数据按 partition 分类 → 临时存放某处 → Reduce 端来取。传统架构中"某处" = "Map 所在的节点的本地磁盘"——这只是因为"最初没有其他地方可放"。存算分离的 Shuffle 纠正了这个历史设计——把 Shuffle 数据从计算节点分离到一个**专用的、可靠的、具备服务质量保证的 Shuffle 存储层**。

## 核心原理

### 29.1 Celeborn — 存算分离的 Shuffle 服务

Apache Celeborn（原 Remote Shuffle Service）用一批专门的 Shuffle Server 组成的集群替代了分散在计算节点上的本地 Shuffle 存储：

```
Celeborn 架构:
  Client (Map Task):
    └── CelebornShuffleWriter
          ├── 将分区数据 push 到 ShuffleServer
          ├── 按 partition 组织 + 本地排序 (可选)
          └── 一条 partition 的多波 push  → ShuffleServer 端合并

  ShuffleServer 集群 (独立部署):
    ├── partitionData 持久化到 NVMe SSD 池
    ├── 复制: 同一 partition 写 2-3 副本 (跨 ShuffleServer)
    ├── Commit: task 完成后 → ShuffleServer 置该 partition 为"已完成"
    └── 生命周期: 由 AppShuffleManager 决定何时清理 (业务完成或过期)

  Client (Reduce Task):
    └── CelebornShuffleReader
          ├── 向 LifecycleManager 查询: "partition 5 的数据在哪些 ShuffleServer 上"
          ├── 从主副本 ShuffleServer 读取数据
          ├── 如果主副本不可用 → 从备份副本读
          └── 如果所有副本不可用 → Stage 重试 (全量重算 Mapper)
```

与 ESS 对比：

| 维度 | ESS (External Shuffle Service) | Celeborn |
|------|-------------------------------|----------|
| 存储位置 | 计算节点本地磁盘 | 专用 ShuffleServer 集群 |
| 容错 | Executor 重启数据还在，Node 故障数据消失 | 多副本 → Node 故障数据仍可读 |
| 容量弹性 | 跟计算节点 1:1 绑定 | 独立扩展 (可加更多 ShuffleServer 或扩容磁盘) |
| 与计算节点争抢 | 是 (共享磁盘带宽 + 网络) | 无 (完全隔离) |
| 运维复杂度 | 低 (与 NM/YARN 内置) | 中 (需管理 ShuffleServer 集群) |
| 适用场景 | 中小规模 (<100 节点) | 大规模 (>500 节点), mixed workloads |

Celeborn 的 LifycycleManager 负责协调整个 shuffle 生命周期——相当于 Spark Driver 与 ShuffleServer 集群之间的"元数据代理"。它跟踪每个 shuffle、每个 partition 的生命周期和位置。

### 29.2 Uniffle — 纯粹的远程 Shuffle 存储

Apache Uniffle 是 Celeborn 的同生态竞争项目，设计哲学更"纯"：

```
Uniffle 的关键设计差异:
  1. 无本地排序: Mapper push 的数据是"无序的" → ShuffleServer 端不做排序
     → 依赖 client 端的读取器在 reduce 时做排序
     → 降低 ShuffleServer 的 CPU 开销 → 高吞吐 (>10GB/s per server)

  2. 多级存储: ShuffleServer 内部
     MEMORY → LOCALFILE (NVMe SSD) → HDFS (remote, 可选)
     → 允许超大 shuffle (>10TB per partition)的场景

  3. 混合部署: ShuffleServer 可以在独立节点上，也可以 collocate 在
     计算节点上 (共享节点但由 ShuffleServer 管理磁盘分配)

  4. ShuffleServer 的链式复制:
     Primary → Secondary → Tertiary (链式而非星型 → 减少主副本的网络扇出)
```

Uniffle 和 Celeborn 都遵循相同的核心抽象："分布式 key-value 存储，其中 key = (shuffleId, partitionId)，value = 序列化后的 shuffle 数据块"。这不是本文的 file write + index file——而是对分布式存储的 API 调用。

### 29.3 CXL — 共享内存的 Shuffle 消除

CXL（Compute Express Link）3.0+ 提供了一个激进的可能性：**如果所有机器共享同一块物理内存，Shuffle 就不再需要"写磁盘"了**。

```
传统 Shuffle (磁盘介质):
  Mapper → sort/write local disk → network fetch → Reducer disk/memory
  物理操作: 磁盘写入(N次随机+顺序) + 网络传输 + 磁盘读出(N次)
  延时: 每个 partition 的端到端延时 ~10ms-1000ms (取决于大小和网络)

CXL Shared Memory Shuffle:
  Mapper → CXL write to shared memory region → Reducer CXL read from shared region
  物理操作: 总线读写 (load/store)
  延时: CXL.mem ≈ 100-300ns (local NUMA ~100ns, cross-socket ~200ns)
  
  对 128MB 的 partition:
    传统:  128MB / 2GB/s(网络) ≈ 64ms + 128MB / 3GB/s(磁盘) ≈ 43ms ≈ 107ms
    CXL:   128MB / 50GB/s(CXL 带宽) ≈ 2.6ms
  
  → 加速比: ~40×
```

CXL 真正改变的不是 Shuffle 的速度——是 **Shuffle 不再存在** 了。当所有 CPU 都能以 ~100-300ns 的延迟访问"其他 CPU 产生的数据"时，Spark 的物理计划中不需要 `ShuffleExchange` 节点——Map 端直接按 Reduce 端的 key 写入共享内存区，Reduce 端直接读取。

这个愿景在 2026 年尚在早期——CXL 3.0 硬件刚出现，CXL 内存共享的协议在操作系统的 NUMA 抽象之上仍有支持性问题。但在 2030 年代，它可能会让"Shuffle"这个概念成为分布式计算的历史脚注。

### 29.4 SmartNIC / FPGA Shuffle — 网络设备做 Shuffle

另一种激进的方向：把 Shuffle 操作从 CPU 卸载到网络设备上：

```
传统 Shuffle:
  CPU 做: sort, partition, serialize, checksum, compress, sendto
  NIC 做: 只负责 packet 发送

SmartNIC Shuffle:
  CPU 做: 只负责 write row to buffer
  SmartNIC 做: partition, sort(optional), serialize, compress, checksum, sendto
  NIC RDMA write 到目标机器内存

→ CPU 释放出 30-50% 的 Shuffle 成本
→ SmartNIC 上的 ARM cores 或 FPGA 处理 partition/sort → PCIe streaming
→ Reduce 端数据已在内存 → 直接读取, 0 次磁盘 I/O
```

FPGA 在这个方向上的优势是 **可重编程的流水线**——`partition → sort → compress` 是一组在 FPGA 门阵列上可以完全流水化的操作，不需要 CPU 的指令 fetch-decode-execute。一个 FPGA 加速器可以以线速（100GbE = 12.5GB/s）处理 shuffle，同时只有 ~1μs 的延迟。

SmartNIC Shuffle 的一个特殊优势是 **in-band replication**——SmartNIC 在发送 partition 数据时同时复制到 second 目标（副 本），不需要额外的 CPU 指令。这在 FPGA 上实现只需要"复制一份流到第二 FIFO"。

### 29.5 从 Stage-level Speculation 到 Block-level Recovery

现有的 Shuffle 容错是"Stage 级别"的——任何一个 map task 失败 → 整个 stage 重来（重新 shuffle 所有 partition）。存算分离的 Shuffle 打开了一个更细粒度的容错模式：

```
Block-level Recovery:
  Map Task-5 写了 15 个 partition 的 shuffle 数据 → ShuffleServer-A (3 replicas)
  Map Task-5 在写 partition 12 时 crash
  
  现有行为: Stage 重试 → 15 个 partition 全部重算 → 浪费: 14 个 partition 的 CPU + I/O

  Block-level 行为:
    1. ShuffleServer 检测 partition 12 的 commit 未完成
    2. 向 Driver 报告: "partition 5-12 incomplete"
    3. Driver 只调度一个 task 重算 Map Task-5 的 partition 12
       (通过合理的 shuffle dependency 设计, 可以只重算一个 partition)
    → 仅丢失 < 1/15 = 6.7% 的工作量
```

这个"细粒度恢复"的前提是 ShuffleServer 知道"哪些 partition 的写入已可靠完成"——这不是传统本地磁盘 Shuffle 可以做到的，因为它们没有独立于 Map Task 的 commit 记录。

### 29.6 Shuffle 与 Query Execution 的深度融合 — 在计划层消除不必要的 Shuffle

终极的 Shuffle 优化是**让 Shuffle 不发生**：

```
CBO + Shuffle Elimination 的场景:
  1. Partition-Key Align:
     表 A 按 customer_id 分 100 个 partition, 按 hash(customer_id) 分布
     表 B 按 customer_id 分 100 个 partition, 按 hash(customer_id) 分布
     → A JOIN B ON customer_id → 不需 Shuffle (两个表都已按 join key 分区)
  
  2. Bucket Join 消除:
     同 bucket 列 + 同 bucket 数 → HashJoin 不需要 Exchange
  
  3. Aggregation After Shuffle 消除:
     Shuffle(Expr, [dept]) + Aggregate([dept], [SUM(amount)])
     → Shuffle 已按 dept 分组 → Aggregate 可以是 partial-merging → 不需要再 Shuffle
  
  4. Dynamic Shuffle Elimination (基于 AQE 的运行时决策):
     如果 Shuffle Write 的实际数据量 < 阈值 → skip Shuffle → do broadcast
     如果 Shuffle Read 的数据量 < 阈值 → merge partition → 减少下阶段的并发度
```

这些优化的实现是在 Catalyst 的 Physical Plan 阶段完成的——通过 Strategy + CBO + AQE 的交互。但随着 Spark 4.0/4.1 的 Physical Plan 优化器的成熟度提高，"消除不必要的 Shuffle" 可能成为主流优化——类似现在的列裁剪和谓词下推。

## 关键代码片段

### 示例：Celeborn ShuffleWriter 的工作流程

```
CelebornShuffleWriter.write(records):
  for each record:
    partitionId = partitioner.getPartition(record.key)
    partitionWriters(partitionId).write(record)
    // 每个 partitionWriter 维护一个本地 buffer
  
  for each partition:
    commit each push:
      → ShuffleClient.pushData(
          shuffleId, partitionId, data, ...
          targetShuffleServer: ShuffleServer-3 (基于 hash 选择)
        )
    
    ShuffleClient.mapperEnd(shuffleId, mapId, numMappers)
      → 通知 ShuffleServer: "这个 map 的 push 结束了"
      → ShuffleServer 记录: shuffle_<id>_map_<mapId>.done

Reduce 端:
  CelebornShuffleReader.read(partitionId):
    → 询问 LifecycleManager: "shuffle_<id>_partition_<pid> 的数据在哪?"
    → LifecycleManager 返回: [ShuffleServer-3 (primary), ShuffleServer-7 (backup)]
    → 打开 ShuffleServer-3 的数据流 → 顺序读取该 partition 的所有 pushed chunks
```

### 示例：Uniffle 的 ShuffleServer 写入路径

```
内存模式 (最优, <256MB per partition):
  Client.pushData → ShuffleServer.memoryBuffer(partition) → append data
  → Client.finish → ShuffleServer flush memoryBuffer → disk (异步)
  → Reduce 读取时: 如果数据全在内存 → 直接从 memoryBuffer 读取 (0 磁盘 I/O)

磁盘模式 (大量 shuffle, >256MB per partition):
  Client.pushData → ShuffleServer.hybridStore:
    1. 先写内存 buffer → 存满 → flush disk file
    2. 继续接收 → 追加到 disk file
    3. 对 disk file 建 sparse index (每 64KB 一块, 记录 offset)
    → Reduce 读取时: index → seek → read 对应的块范围
```

## 硬件视角

**NVMe Pool 的 I/O 容量**：

一个 ShuffleServer 配 4 块 NVMe SSD（每块 3GB/s 读 + 2GB/s 写），总吞吐 = 12GB/s 读 + 8GB/s 写。在一个 50-node 的 Celeborn 集群中，这意味着 600GB/s 的读取带宽——足以服务于数千个并发的 Reduce Task。这个容量评估需要考虑到 ShuffleServer 的"流量模式"：在两个连续的时间窗口内，第一批 Task（Mapper）全部在写入（write bandwith-limited），第二批 Task（Reducer）全部在读取（read bandwidth-limited）——所以 读和写不是同时发生的，共享同一套 NVMe，各自占用全部带宽。

**RDMA 的一边写一边传**：

传统 ShuffleWrite 是 "写完整个文件 → Reducer 开始拉"。RDMA 允许 Mapper CPU "RDMA write" 直接写入 Reducer 的内存——不需要中间的磁盘或文件系统。但 RDMA write 不能超过目标内存的 BDP，否则需要 end-to-end 流控——这是尚未在 Spark 中标准化的部分。Uniffle 对 RDMA 的支持仍在实验阶段。

## AI 时代反思

Shuffle 是 Spark 性能优化的最后一个"非直觉"的环节——用户可以感知"Join 慢了"但很难定位到"Join 慢了是因为 Shuffle 磁盘在 batch-33 和 batch-34 之间被另一个作业的 MapReduce 占满"。这是 LLM Agent 的"关联分析"发挥优势的场景：

```
Agent: "Spark History Server 显示 batch-33 的 Shuffle Read 耗时 45 秒，
        batch-34 的 Shuffle Read 耗时 340 秒。
        同时段内 YARN 显示 user=etl_system 的 3 个 MapReduce 作业在 node-17 上运行，
        而 batch-34 的 Shuffle 数据全在 node-17 的 ESS 上。
        → 根因: node-17 的磁盘带宽被 MapReduce 作业占用，
              Shuffle Read 的 effective bandwidth 从 800MB/s 降到 50MB/s。
        → 建议: 对 node-17 启用 Shuffle IO 优先级限速或迁移 Shuffle 数据到 Celeborn。"
```

这种跨系统（Spark History Server + YARN RM + OS metrics）的关联分析需要搭配多个 API，但目前做得最好的仍然是人类 SRE 而不是 AI Agent。原因是各系统的数据格式不统一 + 时间对齐困难 + 因果推导链太长。

随着 Celeborn / Uniffle 将 Shuffle 存储层标准化为"带有标准 metrics 的 gRPC 服务"，Agent 收集和关联 Shuffle 数据的能力会大幅提升——因为不再是"分散在每个节点本地磁盘上的文件"而是"一个查询就能获取所有 Shuffle 状态的集中式 ShuffleServer"。

## 源码导航

注：Celeborn 和 Uniffle 是独立的 Apache 项目，以下是它们的集成点及 Spark 内部的 Shuffle 切入点。

| 文件/项目 | 关键内容 | 行号参考 |
|-----------|---------|---------|
| Apache Celeborn: `client-spark/shaded/.../CelebornShuffleWriter.scala` | CelebornShuffleWriter，Mapper 端 push 逻辑 | |
| Apache Celeborn: `server/.../PartitionDataWriter.scala` | ShuffleServer 端 partition 写入 | |
| Apache Celeborn: `client-spark/shaded/.../CelebornShuffleReader.scala` | CelebornShuffleReader，Reducer 端读取 | |
| Apache Celeborn: `server/.../LifecycleManager.scala` | Celeborn LifecycleManager，Shuffle 生命周期协调 | |
| Apache Uniffle: `client-spark/.../ShuffleWriteClientImpl.scala` | Uniffle Client，多级存储写入 | |
| Apache Uniffle: `server/.../ShuffleServer.scala` | Uniffle ShuffleServer，内存-磁盘-HDFS 三级存储 | |
| Apache Uniffle: `storage/.../LocalStorageManager.scala` | Uniffle 本地磁盘存储管理，hybrid store | |
| `common/network-shuffle/src/main/java/.../shuffle/ExternalShuffleBlockResolver.java` | ESS 的实现参考，与 Celeborn/Uniffle 的架构对比 | |
| `core/src/main/scala/org/apache/spark/shuffle/ShuffleManager.scala` | Spark ShuffleManager 接口，Celeborn/Uniffle 的挂载点 | ~31 (trait ShuffleManager) |
| `core/src/main/scala/org/apache/spark/shuffle/sort/SortShuffleManager.scala` | 传统 SortShuffleManager，与 remote shuffle manager 的对比 | |
| `sql/core/src/main/scala/.../execution/exchange/ShuffleExchangeExec.scala` | Spark Exchange 算子，Shuffle 的 Physical Plan 表示 | |
