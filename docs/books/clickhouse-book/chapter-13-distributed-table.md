# Chapter 13: DistributedTable 与协调器节点模型

## 13.1 Distributed 存储引擎

`src/Storages/StorageDistributed.h` — ClickHouse 的分布式查询不是 MPP，而是 Scatter-Gather：

```
                    ┌── Shard 1 (本地查询)
Client → Coordinator ├── Shard 2 (本地查询)
                    └── Shard 3 (本地查询)
                          │
                    聚合结果 ← 各分片返回
```

### 表创建

```sql
CREATE TABLE dist_table ON CLUSTER cluster
ENGINE = Distributed(cluster, database, local_table, [sharding_key])
```

**关键参数**：
- `cluster`：集群配置（在 `config.xml` 中定义）
- `database`、`local_table`：各分片上的本地表名
- `sharding_key`：分片键（决定写入时数据分配到哪个分片）

### StorageDistributed 类结构

`src/Storages/StorageDistributed.h:45-258` — 核心成员：

```cpp
class StorageDistributed final : public IStorage, WithContext
{
    String remote_database;              // 远程数据库名
    String remote_table;                 // 远程表名
    const String cluster_name;           // 集群名
    bool has_sharding_key;               // 是否有分片键
    ASTPtr sharding_key;                 // 分片键 AST
    ExpressionActionsPtr sharding_key_expr; // 分片键表达式
    String sharding_key_column_name;     // 分片键列名
    bool sharding_key_is_deterministic;  // 分片键是否确定性
    SimpleIncrement file_names_increment; // 文件名全局递增序号
    ActionBlocker async_insert_blocker;  // 异步写入控制
    StoragePolicyPtr storage_policy;     // 本地缓冲存储策略
    VolumePtr data_volume;              // 本地缓冲卷
};
```

### 核心接口

```cpp
// 读路径 — 分布式查询执行
void read(QueryPlan & query_plan, ...) override;

// 写路径 — 分布式写入
SinkToStoragePtr write(const ASTPtr & query, ...) override;

// 查询处理阶段 — 决定各分片执行到哪个阶段
QueryProcessingStage::Enum getQueryProcessingStage(...) override;

// 分片裁剪 — 根据查询条件跳过不相关分片
ClusterPtr getOptimizedCluster(...) const;
ClusterPtr skipUnusedShards(...) const;
```

## 13.2 查询执行流程

### QueryProcessingStage — 分片执行阶段

`src/Core/QueryProcessingStage.h` — ClickHouse 的分布式查询分 4 个阶段：

```
阶段 1: Complete                → 分片完成全部计算，Coordinator 只合并结果
阶段 2: WithMergeableStateAfterAggregationAndLimit
                                → 分片完成聚合+Limit，Coordinator 合并聚合状态
阶段 3: WithMergeableStateAfterAggregation
                                → 分片完成聚合，Coordinator 合并聚合状态
阶段 4: WithMergeableState      → 分片完成部分计算，Coordinator 做最终聚合

更优的阶段 → 更少的数据传输 → 更快的查询
```

**阶段选择逻辑** (`StorageDistributed.h:193-208`)：

```cpp
std::optional<QueryProcessingStage::Enum> getOptimizedQueryProcessingStage(
    const SelectQueryInfo & query_info, const Settings & settings) const
{
    // 简单查询（无 GROUP BY / DISTINCT）→ Complete
    // GROUP BY sharding_key → WithMergeableStateAfterAggregation
    // 否则 → WithMergeableState（默认）
}
```

**示例**：

```sql
-- 阶段: Complete（分片完成全部计算）
SELECT count() FROM dist_table WHERE date = '2024-01-01'
→ 各分片: SELECT count() FROM local_table WHERE date = '2024-01-01'
→ Coordinator: sum(all_shard_counts)

-- 阶段: WithMergeableState（分片完成部分聚合）
SELECT user_id, count() FROM dist_table GROUP BY user_id
→ 各分片: SELECT user_id, count() FROM local_table GROUP BY user_id
→ Coordinator: 重新聚合 (MergeAggregated)

-- 阶段: WithMergeableStateAfterAggregation（当 GROUP BY = sharding_key）
-- 如果 sharding_key = user_id
SELECT user_id, count() FROM dist_table GROUP BY user_id
→ 各分片: SELECT user_id, count() FROM local_table GROUP BY user_id
→ Coordinator: 直接拼接（无需重新聚合，因为数据不跨分片）
```

### SelectStreamFactory — 查询分发

`src/Interpreters/ClusterProxy/SelectStreamFactory.h:49-72` — 构建各分片的查询管道：

```cpp
class SelectStreamFactory
{
    struct Shard
    {
        ASTPtr query;                        // 重写后的 SQL
        QueryTreeNodePtr query_tree;          // Analyzer v2 的 QueryTree
        std::shared_ptr<QueryPlan> query_plan; // 或预构建的 QueryPlan
        StorageID main_table;                // 远程表标识
        SharedHeader header;                  // 结果列结构
        Cluster::ShardInfo shard_info;        // 分片连接信息
        bool lazy = false;                    // 延迟连接（本地副本延迟大时）
        AdditionalShardFilterGenerator shard_filter_generator; // 分片级过滤
    };
};
```

**查询重写** (`ClusterProxy/SelectStreamFactory.h:39-44`)：

```cpp
ASTPtr rewriteSelectQuery(ContextPtr context, const ASTPtr & query,
    const std::string & remote_database, const std::string & remote_table)
{
    // 将 Distributed 表名替换为本地表名
    // dist_table → local_table
    // 保留 WHERE / GROUP BY / HAVING 等子句
}
```

### 分片裁剪

`StorageDistributed.h:175-189` — `skipUnusedShards()` 根据查询条件跳过不相关分片：

```
场景: sharding_key = user_id
查询: SELECT * FROM dist_table WHERE user_id = 42

1. 计算 user_id = 42 的分片号
   hash(42) % num_shards = 2
2. 只将查询发送到 Shard 2
3. 跳过 Shard 1 和 Shard 3

设置:
  optimize_skip_unused_shards = 1     — 启用分片裁剪
  force_optimize_skip_unused_shards = 1 — 强制裁剪（无法裁剪时报错）
```

## 13.3 写入路径

### DistributedSink — 写入目标

`src/Storages/Distributed/DistributedSink.h:39-80` — 两种写入模式：

```cpp
class DistributedSink : public SinkToStorage
{
    void consume(Chunk & chunk) override
    {
        if (insert_sync)
            writeSync(block);   // 同步写入
        else
            writeAsync(block);  // 异步写入
    }

    // 分片选择：按 sharding_key 计算分片号
    IColumn::Selector createSelector(const Block & source_block) const;

    // 分块：将一个 Block 按分片拆分为多个子 Block
    Blocks splitBlock(const Block & block);
};
```

### 同步写入 (`distributed_foreground_insert = 1`)

```
Client → Coordinator (DistributedSink)
  │
  ├── splitBlock() → 按 sharding_key 分片
  │
  ├── Shard 1 → 直连写入 Shard 1 的本地表
  ├── Shard 2 → 直连写入 Shard 2 的本地表
  └── Shard 3 → 直连写入 Shard 3 的本地表

优点: 实时写入，延迟低
缺点: 目标分片不可用时报错
```

### 异步写入（默认）

```
Client → Coordinator (DistributedSink)
  │
  ├── splitBlock() → 按 sharding_key 分片
  │
  ├── Shard 1 的 Block → 写入本地文件 data/shard1/
  ├── Shard 2 的 Block → 写入本地文件 data/shard2/
  └── Shard 3 的 Block → 写入本地文件 data/shard3/
        │
        └── DistributedAsyncInsertDirectoryQueue
              → 后台线程监控目录
              → 异步发送到目标分片
              → 失败重试
```

**DistributedAsyncInsertDirectoryQueue** (`src/Storages/Distributed/DistributedAsyncInsertDirectoryQueue.h`)：

```
data/shard1/
  ├── batch_0001.bin   ← 压缩的 Native 格式数据
  ├── batch_0002.bin
  └── ...

后台线程:
  1. 监控目录中的新文件
  2. 读取 .bin 文件
  3. 通过 Native Protocol 发送到目标分片
  4. 发送成功 → 删除本地文件
  5. 发送失败 → 保留文件，稍后重试
```

**异步写入的优势**：
- 目标分片不可用时不影响客户端
- 批量发送减少网络开销
- 文件保证写入不丢失

**异步写入的风险**：
- 数据延迟（`distributed_directory_monitor_sleep_time_ms` 控制检查间隔）
- 本地磁盘空间占用
- Coordinator 宕机可能丢失未发送的数据

## 13.4 集群配置

```xml
<clickhouse>
    <remote_servers>
        <my_cluster>
            <shard>
                <internal_replication>true</internal_replication>
                <replica>
                    <host>shard1-rep1</host>
                    <port>9000</port>
                    <user>default</user>
                    <password>...</password>
                </replica>
                <replica>
                    <host>shard1-rep2</host>
                    <port>9000</port>
                </replica>
            </shard>
            <shard>
                <replica>
                    <host>shard2-rep1</host>
                    <port>9000</port>
                </replica>
            </shard>
        </my_cluster>
    </remote_servers>
</clickhouse>
```

**`internal_replication`**：
- `true`：INSERT 只写入一个副本，副本间通过 ReplicatedMergeTree 同步
- `false`：INSERT 写入所有副本（旧模式，不推荐）

## 13.5 跨分片 JOIN

Distributed 查询的一个重要限制：只有简单查询可以下推到分片。跨分片 JOIN 的处理：

```
SELECT * FROM dist_a JOIN dist_b ON dist_a.id = dist_b.id

→ 两种策略：
  1. 将 dist_b 的数据拉到 Coordinator，在 Coordinator 上做 JOIN
     (默认行为，当 dist_b 较小时可行)
  2. 将 dist_a 的查询发送到 dist_b 所在的分片，本地 JOIN
     (prefer_localhost_replica=1 时可能发生)

注意: 无论哪种策略，都不做 Shuffle Join！
→ 这是 ClickHouse 与 MPP 数据库的核心差异
```

### 分布式子查询

```sql
SELECT * FROM dist_a WHERE id IN (SELECT id FROM dist_b)

→ 两种执行模式：
  1. IN = GLOBAL IN: 将子查询结果广播到所有分片
  2. IN (非 GLOBAL): 每个分片独立执行子查询（可能结果不同）
```

**`GLOBAL IN`** 是 ClickHouse 独有的语法——它保证子查询只在 Coordinator 执行一次，结果广播到所有分片。这是解决分布式子查询语义不一致的实用方案。

> **侧边栏 · 与 StarRocks MPP 对比**：StarRocks 使用 Shuffle Join——将 JOIN 两表按 KEY 哈希重分布到所有 BE 节点，每个节点只处理一部分数据。ClickHouse 的 Scatter-Gather 模型更简单但不适合大表 JOIN——所有数据都汇聚到 Coordinator，Coordinator 成为瓶颈。这是 ClickHouse 在分布式 JOIN 场景下的主要劣势，也是 Parallel Replicas 和 SharedMergeTree 想要解决的。

> **侧边栏 · 与 MaxCompute 对比**：MaxCompute 使用 Stage-based 执行模型——每个 Stage 是一次 Map/Reduce/Shuffle 操作，Stage 之间通过磁盘交换数据。ClickHouse 的 Distributed 模型更像是一次性的 Scatter-Gather——没有中间 Shuffle，所有结果直接返回 Coordinator。这简化了执行模型但限制了复杂查询的扩展性。

## 13.6 Distributed 引擎的特殊行为

### 虚拟列

```cpp
// StorageDistributed.h:223
static VirtualColumnsDescription createVirtuals();
// 添加 _shard_num 虚拟列，标识数据来自哪个分片
```

### 延迟副本处理

```cpp
// SelectStreamFactory.h:69
bool lazy = false;  // 延迟连接
// 当本地副本延迟过大时，Coordinator 不立即连接本地副本
// 而是先连接远程副本，如果远程副本也慢再回退到本地
// 这避免了慢副本拖累整个查询
```

### 分片权重

```xml
<shard>
    <weight>2</weight>   ← 该分片权重为 2
    <replica>...</replica>
</shard>
<shard>
    <weight>1</weight>   ← 该分片权重为 1
    <replica>...</replica>
</shard>
```

写入时，sharding_key 按权重比例分配数据（2:1），而非均匀分配。

## 13.7 本章小结

```
Distributed 查询模型:
  Coordinator (Scatter) → N 个 Shard (独立执行) → Coordinator (Gather)

查询阶段:
  Complete → WithMergeableStateAfterAggregationAndLimit
           → WithMergeableStateAfterAggregation → WithMergeableState

写入模式:
  同步: 直连写入目标分片 (distributed_foreground_insert=1)
  异步: 本地缓冲 → 后台线程发送 (默认)

关键限制:
  ├── 跨分片 JOIN 需要 Coordinator 汇聚（无 Shuffle）
  ├── 聚合需要两阶段（分片局部 + 全局合并）
  ├── 数据倾斜取决于 sharding_key
  └── 异步写入有延迟和丢失风险
```

**关键文件地图**：
```
src/Storages/StorageDistributed.h                  → Distributed 引擎定义
src/Storages/StorageDistributed.cpp                → Distributed 引擎实现
src/Storages/Distributed/DistributedSink.h         → 写入 Sink
src/Storages/Distributed/DistributedAsyncInsertDirectoryQueue.h → 异步写入队列
src/Interpreters/ClusterProxy/SelectStreamFactory.h → 查询分发工厂
src/Interpreters/Cluster.h                         → 集群定义
```
