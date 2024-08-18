# Chapter 9: ReplicatedMergeTree — ZooKeeper/Keeper 协调下的分布式一致性

## 9.1 为什么需要 ReplicatedMergeTree？

MergeTree 是单节点的——没有副本、没有容错。ReplicatedMergeTree 在 MergeTree 基础上添加了：
- **多副本**：同一份数据存储在多个节点
- **一致性**：通过 ZooKeeper/ClickHouse Keeper 保证副本间数据一致
- **高可用**：任一副本宕机，其他副本继续服务

## 9.2 ZooKeeper 中的元数据结构

ReplicatedMergeTree 在 ZooKeeper 中维护以下节点：

```
/zk_path/{database}/{table}/
  ├── metadata/                          ← 表元数据
  │     ├── columns                      ← 列定义
  │     └── metadata                     ← 表引擎参数
  │
  ├── log/                               ← 全局操作日志（所有副本共享）
  │     ├── entry-0000000001             ← INSERT 操作
  │     ├── entry-0000000002             ← MERGE 操作
  │     └── entry-0000000003             ← MUTATION 操作
  │
  ├── replicas/                          ← 副本注册
  │     ├── {replica_1}/
  │     │     ├── host                   ← 节点地址
  │     │     ├── is_active              ← 心跳标记（临时节点）
  │     │     ├── pointer                ← 日志消费指针
  │     │     ├── queue/                 ← 该副本的待执行任务
  │     │     │     ├── queue-0000001    ← 从 log 中拉取的待执行条目
  │     │     │     └── queue-0000002
  │     │     ├── parts/                 ← 该副本持有的 Parts
  │     │     │     ├── all_1_1_0        ← Part 注册（值 = checksum）
  │     │     │     └── all_2_2_0
  │     │     └── log/                   ← 该副本已处理的日志
  │     │
  │     └── {replica_2}/
  │           └── ...
  │
  ├── blocks/                            ← 写入去重
  │     └── {hash_of_block_id}           ← 幂等性保证
  │
  ├── deduplication_hashes/              ← 异步 INSERT 去重
  │     └── {partition}_{hash}
  │
  ├── mutations/                         ← Mutation 操作
  │     └── 0000000001.txt
  │
  ├── temp/                              ← 临时节点（Part 传输锁）
  │
  └── pinned_part_uuids/                 ← Part UUID 固定（防止误删）
```

## 9.3 LogEntry — 操作日志条目

`src/Storages/MergeTree/ReplicatedMergeTreeLogEntry.h:24-120` — 每个日志条目定义了一个操作：

```cpp
struct ReplicatedMergeTreeLogEntryData
{
    enum Type
    {
        EMPTY,                // 空条目
        GET_PART,             // 从其他副本获取 Part
        ATTACH_PART,          // 附加 Part（可能来自本地 /detached 目录）
        MERGE_PARTS,          // 合并多个 Part
        DROP_RANGE,           // 删除指定分区范围内的 Part
        CLEAR_COLUMN,         // 清除指定列（已废弃）
        CLEAR_INDEX,          // 清除指定索引（已废弃）
        REPLACE_RANGE,        // 替换指定范围的 Part（REPLACE PARTITION）
        MUTATE_PART,          // 对 Part 应用 Mutation
        ALTER_METADATA,       // 更新元数据（ALTER TABLE）
        SYNC_PINNED_PART_UUIDS, // 同步 Part UUID（确保内存状态一致）
        CLONE_PART_FROM_SHARD,  // 从其他分片克隆 Part
        DROP_PART,            // 删除指定 Part
    };

    String znode_name;           // ZooKeeper 节点名
    String log_entry_id;         // 日志条目 ID
    Type type = EMPTY;
    String source_replica;       // 来源副本
    String new_part_name;        // 结果 Part 名
    Strings source_parts;        // 源 Part 列表
    bool deduplicate = false;    // Merge 时是否去重
    MergeType merge_type = MergeType::Regular; // Merge 类型
    int alter_version = -1;      // ALTER 版本号
};
```

## 9.4 ReplicatedMergeTreeQueue — 副本操作队列

`src/Storages/MergeTree/ReplicatedMergeTreeQueue.h:38-100` — 每个副本维护自己的操作队列：

```cpp
class ReplicatedMergeTreeQueue
{
    // 关键状态
    ActiveDataPartSet current_parts;  // 当前应该持有的 Parts（虚拟视图）
    Queue queue;                      // 待执行的操作列表

    // 核心方法
    void pullLogsToQueue(ZooKeeperPtr & zookeeper, ContextPtr context);
    // → 从全局 log 拉取尚未执行的操作到本地 queue

    LogEntryPtr selectEntryToProcess();
    // → 从 queue 中选择下一个要执行的操作
    // → 不是简单的 FIFO！会考虑：
    //    - 操作间的依赖关系
    //    - 是否有冲突（同时操作同一个 Part）
    //    - 优先级（GET_PART 优先于 MERGE）

    void processEntry(LogEntryPtr & entry);
    // → 执行选中的操作
    // → 成功后从 queue 中移除
    // → 失败后重试

    // 去重
    std::unordered_set<String> deduplication_block_ids;
    // → INSERT 的 block_id 去重集合
};
```

### 操作选择策略

`selectEntryToProcess()` 不是简单的 FIFO，而是智能选择：

1. **GET_PART 优先**：获取缺失的 Part 比合并更紧急
2. **无冲突**：不会同时执行操作同一个 Part 的两个操作
3. **ATTACH_PART 优先于 MERGE_PARTS**：如果本地已有合并结果，不需要重新合并

## 9.5 INSERT 流程（分布式）

```
Client → Replica 1:
  │
  ├── 1. 去重检查
  │     ├── 计算 block_id 的哈希
  │     ├── 检查 /blocks/{hash} 是否存在
  │     └── 存在 → 跳过（幂等保证）
  │
  ├── 2. 写入本地 Part
  │     └── 与普通 MergeTree 相同的写入流程
  │
  ├── 3. 注册到 ZooKeeper
  │     ├── 在 /log/ 创建新 entry (GET_PART, new_part_name)
  │     ├── 在 /blocks/ 创建去重标记
  │     └── 在 /replicas/me/parts/ 注册 Part
  │
  └── 4. 等待 Quorum（可选）
        → 如果设置了 insert_quorum，等待 N 个副本确认
```

### 去重机制

```
INSERT INTO t VALUES (...) — block_id = hash(data)

1. 检查 /blocks/{block_id_hash}
   ├── 存在 → 这批数据已写入，跳过（返回成功）
   └── 不存在 → 继续写入

2. 写入后在 /blocks/ 中注册
   → 保证 INSERT 的幂等性
   → 客户端重试不会产生重复数据

3. 过期清理
   → /blocks/ 中的条目在 replicated_deduplication_window 后清理
   → 默认保留最近 1000 个 block_id
```

### Quorum 写入

```sql
INSERT INTO t SETTINGS insert_quorum = 2, insert_quorum_timeout = 60000
```

```
1. Leader 写入本地 Part
2. 创建 /log/ entry
3. 等待至少 2 个副本确认拥有该 Part
4. 超时未达到 Quorum → 回滚

这保证了即使 Leader 宕机，数据也不会丢失
```

## 9.6 MERGE 流程（分布式）

```
Leader Replica:
  │
  ├── 1. 选择要合并的 Parts
  │     └── MergeSelector（与普通 MergeTree 相同）
  │
  ├── 2. 分配 Merge 任务
  │     ├── 在 /log/ 创建 MERGE_PARTS entry
  │     └── 或通过 DistributedMergePredicate 协调
  │
  ├── 3. 执行本地 Merge
  │     └── 与普通 MergeTree 相同的 MergeTask
  │
  └── 4. 注册新 Part
        ├── 在 /replicas/me/parts/ 注册
        └── 旧 Part 标记为过期

Follower Replica:
  │
  ├── 1. 从 log 拉取 MERGE_PARTS entry 到 queue
  │
  ├── 2. 选择执行方式:
  │     ├── 自行执行 Merge（从源 Parts 重新合并）
  │     │     → 适用于本地已有源 Parts 的情况
  │     │
  │     └── 从 Leader 拉取合并后的 Part
  │           → 适用于本地缺少源 Parts 的情况
  │           → 通过 DataPartsExchange 拉取
  │
  └── 3. 注册新 Part，标记旧 Part 过期
```

### DataPartsExchange — Part 传输

`src/Storages/MergeTree/DataPartsExchange.h` — 副本间的 Part 传输协议：

```
Follower → Leader: HTTP GET /replicas/me/parts/{part_name}
Leader → Follower: Part 的压缩数据流

使用 Interserver HTTP 端口（默认 9009）
支持校验和验证
支持断点续传
```

## 9.7 Mutation 流程

```
ALTER TABLE t UPDATE col = expr WHERE condition;

1. 在 /mutations/ 创建 mutation entry
   → 包含 mutation 命令和条件

2. 在 /log/ 创建 MUTATE_PART entry
   → 每个 Part 一个 entry

3. 各副本从 queue 中拉取 MUTATE_PART
   → 执行与普通 Merge 相同，但只修改满足条件的行

4. 完成后在 /replicas/me/parts/ 注册新 Part
```

## 9.8 副本同步与恢复

### 启动恢复

```
1. 从 ZooKeeper 读取 /replicas/me/parts/ → 本地应该持有的 Parts
2. 对比本地实际 Parts：
   ├── 缺失 → 从其他副本拉取 (GET_PART)
   └── 多余 → 标记为 /detached（可能正在被清理）
3. 从 /log/ 拉取未处理的 entries → 放入 queue
4. 执行 queue 中的操作，追上进度
5. 标记 /replicas/me/is_active → 开始服务查询
```

### 延迟监控

```sql
SELECT
    replica_name,
    absolute_delay,      -- 绝对延迟（秒）
    queue_size,          -- 待执行操作数
    inserts_in_queue,    -- 待执行 INSERT 数
    merges_in_queue,     -- 待执行 MERGE 数
    mutations_in_queue   -- 待执行 MUTATION 数
FROM system.replicas
WHERE table = 't';
```

## 9.9 ClickHouse Keeper

`src/Coordination/` — ClickHouse 自研的 ZooKeeper 替代品：

### 为什么不用 ZooKeeper？

1. Java 依赖重，部署复杂
2. GC 停顿影响延迟（ZooKeeper 对 GC 停顿极其敏感）
3. 内存占用高（JVM 堆 + 堆外内存）
4. 运维成本高（需要独立的 ZooKeeper 集群）

### Keeper 优势

- **C++ 实现**：无 GC，延迟更稳定
- **共享二进制**：与 ClickHouse Server 在同一个二进制中
- **RAFT 协议**：与 ZooKeeper 的 ZAB 类似，保证线性一致性
- **热快照**：不阻塞读写的情况下创建快照
- **兼容协议**：支持 ZooKeeper 客户端协议（ClickHouse 无需修改即可切换）

```cpp
// src/Coordination/KeeperStorage.h
class KeeperStorage : public IKeeper
{
    // RAFT State Machine
    // 支持所有 ZooKeeper 操作：create, remove, exists, get, set, get_children, multi
    // 额外支持：watch, remove_recursive (高效递归删除)
};
```

### Keeper 配置

```xml
<clickhouse>
    <keeper_server>
        <tcp_port>9181</tcp_port>
        <server_id>1</server_id>
        <log_storage_path>/var/lib/clickhouse/coordination/log</log_storage_path>
        <snapshot_storage_path>/var/lib/clickhouse/coordination/snapshots</snapshot_storage_path>
        <raft_configuration>
            <server>
                <id>1</id>
                <hostname>keeper1</hostname>
                <port>9234</port>
            </server>
        </raft_configuration>
    </keeper_server>
</clickhouse>
```

## 9.10 常见问题与调优

### 副本延迟

```
原因:
  1. Part 数量过多 → Merge 跟不上
  2. 网络带宽不足 → Part 传输慢
  3. ZooKeeper 延迟 → 日志拉取慢
  4. 大 Part 的 Mutation → 重写大量数据

调优:
  → 增加后台线程数: background_pool_size, merge_tree_max_rows_to_merge_at_once
  → 减少小 INSERT 批次: 使用异步 INSERT
  → 优化 ZooKeeper: 使用 ClickHouse Keeper
```

### ZooKeeper 压力

```
原因:
  1. 每个 Part 注册一个 ZK 节点
  2. 每个 INSERT 创建 log entry + block entry
  3. Part 数量过多时 ZK 节点数爆炸

调优:
  → 减少 Part 数量: 增大 INSERT 批次大小
  → 使用 async_insert: 批量合并小 INSERT
  → 使用 parts_to_throw_insert: 限制活跃 Part 数
  → 使用 ClickHouse Keeper: 更低的延迟和内存占用
```

## 9.11 本章小结

```
ReplicatedMergeTree
  ├── ZooKeeper/Keeper 存储元数据和操作日志
  ├── LogEntry 定义了 12 种操作类型
  ├── ReplicatedMergeTreeQueue 智能选择操作顺序
  ├── Leader 副本负责 Merge 决策
  ├── 所有副本可以接受 INSERT
  ├── 操作通过 log + queue 传播
  ├── Part 通过 DataPartsExchange HTTP 拉取
  ├── 去重通过 /blocks/ 幂等保证
  └── Quorum 写入保证数据不丢失

ClickHouse Keeper:
  C++ 实现 + RAFT 协议 + 热快照 + 协议兼容
```

**关键文件地图**：
```
src/Storages/StorageReplicatedMergeTree.h           → ReplicatedMergeTree 定义
src/Storages/MergeTree/ReplicatedMergeTreeLogEntry.h → 日志条目定义
src/Storages/MergeTree/ReplicatedMergeTreeQueue.h    → 操作队列
src/Storages/MergeTree/DataPartsExchange.h           → Part 传输协议
src/Storages/MergeTree/MergeFromLogEntryTask.h       → 从日志执行 Merge
src/Storages/MergeTree/MutateFromLogEntryTask.h      → 从日志执行 Mutation
src/Coordination/                                    → ClickHouse Keeper 实现
```
