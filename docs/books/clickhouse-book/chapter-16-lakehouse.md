# Chapter 16: Lakehouse 集成 — Iceberg / DeltaLake / Paimon 原生支持全链路

## 16.1 ClickHouse Lakehouse 架构

```
SQL 查询
  │
  ├── Parser → AST
  ├── Analyzer → QueryTree (TableNode → StorageObjectStorage)
  ├── Planner → QueryPlan
  │     └── ReadFromStorage
  │           └── StorageObjectStorage
  │                 ├── DataLake: Iceberg / DeltaLake / Paimon
  │                 │     ├── 元数据解析（Snapshot / Manifest / Partition）
  │                 │     ├── 分区裁剪
  │                 │     └── 文件列表生成
  │                 │
  │                 └── ObjectStorage: S3 / Azure / HDFS
  │                       ├── 列出数据文件
  │                       ├── 读取 Parquet / ORC / Avro
  │                       └── 可选: 本地 FileCache
  │
  └── Pipeline → 执行
```

### 统一接口设计

所有 Lakehouse 格式共享同一个 `IDataLake` 接口：

```cpp
// src/Storages/ObjectStorage/DataLakes/IDataLake.h
class IDataLake
{
    // 获取数据文件列表（带分区裁剪）
    virtual DataFiles getDataFiles(
        const ActionsDAG * filter,
        ContextPtr context) const = 0;

    // 获取表 schema
    virtual NamesAndTypesList getTableSchema() const = 0;

    // 检查是否支持写入
    virtual bool supportsDataWriting() const = 0;

    // 获取快照信息
    virtual std::optional<Snapshot> getSnapshot() const = 0;
};
```

## 16.2 Apache Iceberg — 最成熟的 Lakehouse 支持

`src/Storages/ObjectStorage/DataLakes/Iceberg/` — 30+ 个头文件，读写删全支持。

### 元数据层次

```
Iceberg Table
  ├── metadata/
  │     ├── v1.metadata.json     ← 表元数据（schema, partition-spec, sort-order）
  │     ├── snap-xxx.avro        ← Manifest List（快照）
  │     └── manifest-xxx.avro    ← Manifest File（数据文件列表）
  │
  └── data/
        ├── part-00000.parquet   ← 数据文件
        └── part-00001.parquet
```

**读取层次**：

```
1. metadata.json → 当前 Snapshot ID
2. snap-xxx.avro → Manifest File 列表
3. manifest-xxx.avro → DataFile 列表（带统计信息）
4. DataFile → 实际的 Parquet/ORC/Avro 文件
```

### 核心类

| 类 | 文件 | 作用 |
|----|------|------|
| `IcebergMetadata` | `IcebergMetadata.h` | 解析 metadata.json |
| `Snapshot` | `Snapshot.h` | 快照表示 |
| `ManifestFile` | `ManifestFile.h` | Manifest 文件解析 |
| `ManifestFileIterator` | `ManifestFileIterator.h` | 遍历 Manifest 中的 DataFile |
| `ManifestFilesPruning` | `ManifestFilesPruning.h` | 分区/列统计裁剪 |
| `IcebergIterator` | `IcebergIterator.h` | 统一的数据文件迭代器 |
| `DataFileStatistics` | `DataFileStatistics.h` | DataFile 级别的统计信息 |
| `IcebergMetadataFilesCache` | `IcebergMetadataFilesCache.h` | 元数据缓存 |

### 读取流程

```
1. IcebergMetadata → 获取当前 Snapshot
   ├── 从 metadata.json 解析
   ├── 支持 snapshot-id 指定历史快照
   └── 支持 time-travel: AS OF TIMESTAMP

2. Snapshot → Manifest List → Manifest Files
   ├── 读取 snap-xxx.avro
   ├── 每个 Manifest File 包含一组 DataFile 的统计信息
   └── Manifest 级别有分区字段的 min/max（用于快速裁剪）

3. ManifestFilesPruning → 使用分区 + 列统计裁剪不满足条件的 DataFile
   ├── Level 1: 分区裁剪（利用分区字段的 min/max）
   ├── Level 2: 列统计裁剪（利用 DataFile 的 NaN/Null 计数、min/max）
   └── 裁剪后剩余的 DataFile → 需要实际读取

4. IcebergIterator → 遍历剩余 DataFile
   └── 对每个 DataFile 创建 Parquet/ORC/Avro 读取任务

5. 对每个 DataFile → 读取 Parquet/ORC/Avro
   └── 通过 ObjectStorage 读取

6. 可选: PositionDelete / EqualityDelete → 应用删除向量
```

### ManifestFilesPruning — 裁剪算法

```
输入: WHERE date = '2024-01-01' AND user_id = 300

Level 1: 分区裁剪
  Manifest 1: partition(date) min=2023-12, max=2024-01 → 可能包含
  Manifest 2: partition(date) min=2024-02, max=2024-03 → 排除

Level 2: 列统计裁剪
  DataFile A: user_id min=100, max=200 → 排除 (300 > max)
  DataFile B: user_id min=50, max=500 → 可能包含 → 需要读取
  DataFile C: user_id min=250, max=400 → 可能包含 → 需要读取

结果: 只读取 DataFile B 和 C
```

### 写入流程

`IcebergWrites.h` + `MultipleFileWriter.h` + `MetadataGenerator.h`：

```
1. 创建新的 DataFile (Parquet)
   → 使用 ParquetBlockOutputFormat 写入
   → 写入到 ObjectStorage

2. 生成新的 Manifest File
   → 包含新 DataFile 的统计信息
   → 写入到 ObjectStorage

3. 生成新的 Snapshot
   → 引用新的 Manifest File
   → 保留旧 Manifest（快照隔离）

4. 原子更新 metadata.json
   → 使用 S3 If-Match 条件写入
   → 或通过 Iceberg Catalog 的原子操作
```

### 删除支持

| 类型 | 文件 | 作用 |
|------|------|------|
| Position Delete | `PositionDeleteObject.h` | 按行号删除 |
| Equality Delete | `EqualityDeleteObject.h` | 按条件删除 |
| Position Delete Transform | `PositionDeleteTransform.h` | 删除向量应用 |

```
Position Delete:
  DELETE FROM t WHERE _pos IN (42, 105, 200)
  → 创建一个删除向量: [42, 105, 200]
  → 查询时过滤这些行号

Equality Delete:
  DELETE FROM t WHERE user_id = 42
  → 创建一个等值删除文件
  → 查询时过滤满足条件的行

读取时应用删除:
  1. 读取 DataFile 的 Parquet 数据
  2. 加载对应的 Delete 文件
  3. 过滤被标记删除的行
  4. 返回剩余行
```

### Compaction

`Compaction.h` — 合并小文件为大文件（Iceberg 表维护的核心操作）：

```
场景: 频繁小批量写入产生大量小文件
  → 读取性能差（需要打开大量文件）

Compaction 流程:
  1. 扫描小 DataFile
  2. 合并为大的 DataFile
  3. 生成新的 Manifest
  4. 原子提交新 Snapshot
```

### 过期快照清理

`ExpireSnapshotsTypes.h` — 清理旧的 Snapshot 和对应的 DataFile：

```
场景: 历史快照占用存储空间
  → 需要定期清理

清理流程:
  1. 确定保留窗口（如最近 7 天）
  2. 标记过期快照
  3. 找出仅被过期快照引用的 DataFile
  4. 删除这些 DataFile
  5. 删除过期 Manifest File
  6. 更新 metadata.json
```

### Stateless 模式

`StatelessMetadataFileGetter.h` — 无需本地状态即可从 S3 获取 Iceberg 元数据：

```
传统: 启动时加载所有元数据到内存
  → 适合元数据量小的场景
  → 启动慢

Stateless: 按需从 S3 获取元数据文件
  → 适合大规模表
  → 适配存算分离架构
  → 无状态计算节点可以直接查询 Iceberg 表

优势:
  - 无需本地状态
  - 启动快
  - 支持动态扩缩容
```

### 元数据缓存

```
IcebergMetadataFilesCache:
  Key: {metadata_file_path, snapshot_id}
  Value: 解析后的 Manifest / DataFile 列表

  缓存策略:
  - LRU 淘汰
  - TTL 过期（默认 30 秒）
  - 支持 force_refresh

  设置:
    iceberg_metadata_cache_max_size = 100MB
    iceberg_metadata_cache_ttl = 30s
```

## 16.3 Delta Lake

`src/Storages/ObjectStorage/DataLakes/DeltaLake/` — 通过 delta-kernel-rust FFI 实现。

### 架构

```
ClickHouse (C++)
  │
  ├── KernelHelper.h / KernelPointerWrapper.h  → Rust delta-kernel FFI
  │     │
  │     └── delta-kernel-rust (Rust)
  │           ├── 读取 Delta Lake Log
  │           ├── 解析 JSON/Parquet checkpoint
  │           └── 返回数据文件列表 + 统计信息
  │
  └── C++ 层
        ├── DeltaLakeTableStateSnapshot.h → 快照表示
        ├── PartitionPruner.h → 分区裁剪
        ├── DeltaLakeSink.h → 写入
        └── ReadFromTableChangesStep.h → CDC 读取
```

**为什么用 Rust Kernel？** Delta Lake 的协议复杂（事务日志、CDF、Z-Ordering），delta-kernel-rust 是官方维护的轻量级库，避免在 C++ 中重新实现协议。

### FFI 交互模式

```
C++ 调用 Rust:
  1. KernelHelper::createSnapshot(path)
     → 调用 Rust delta_kernel::Snapshot::new()
     → 返回 opaque pointer

  2. KernelHelper::getFiles(snapshot, predicate)
     → 调用 Rust 遍历 Log + Checkpoint
     → 返回 DataFile 列表（通过 C ABI 回调）

  3. KernelHelper::getSchema(snapshot)
     → 调用 Rust 获取表 Schema
     → 转换为 ClickHouse 的 NamesAndTypesList

内存管理:
  → Rust 侧分配的内存通过 KernelPointerWrapper 管理
  → RAII 包装，析构时调用 Rust 的 free 函数
  → 避免跨语言内存泄漏
```

### 写入支持

`DeltaLakeSink.h` + `DeltaLakePartitionedSink.h` + `WriteTransaction.h`：

```
1. 写入 Parquet 文件到 ObjectStorage
   → 使用 ClickHouse 的 ParquetBlockOutputFormat
   → 按 partition 分桶写入

2. 通过 delta-kernel 生成事务日志
   → 记录新增的文件、统计信息
   → 生成 commit info

3. 原子提交事务
   → 使用 delta-kernel 的 commit API
   → 保证 ACID 属性
```

### CDC 支持

`ReadFromTableChangesStep.h` — 读取 Delta Lake 的 Change Data Feed：

```
场景: 增量读取 Delta Lake 的数据变更
  → 用于实时数据同步

读取方式:
  SELECT * FROM delta_table TABLE CHANGES FROM VERSION 5

  → 读取从 version 5 开始的所有变更
  → 包括 INSERT、UPDATE、DELETE 操作
  → 每行附带 _change_type (insert/update/delete) 和 _commit_version
```

## 16.4 Apache Paimon

`src/Storages/ObjectStorage/DataLakes/Paimon/` — 基础读支持：

| 类 | 作用 |
|----|------|
| `PaimonClient.h` | Paimon Catalog/Table 客户端 |
| `PaimonMetadata.h` | 元数据解析 |
| `PaimonTableSchema.h` | Schema 解析 |
| `PartitionPruner.h` | 分区裁剪 |
| `BinaryRow.h` | Paimon 的二进制行格式 |

当前状态：只读，写支持待开发。

### Paimon 元数据层次

```
Paimon Table
  ├── schema/
  │     └── schema-0, schema-1, ...   ← Schema 版本
  ├── snapshot/
  │     └── snapshot-1, snapshot-2, ... ← 快照
  ├── manifest/
  │     ├── manifest-list-1            ← Manifest List
  │     └── manifest-file-1            ← Manifest File
  └── data/
        ├── bucket-0/
        │     └── data-0.parquet
        └── bucket-1/
              └── data-0.parquet
```

## 16.5 Hive

`src/Storages/Hive/` — ClickHouse 也支持 Hive Metastore 中的表：

```
支持格式: Parquet, ORC, TextFile
支持分区: 静态分区 + 动态分区
元数据: 从 Hive Metastore 获取

Hive Metastore 连接:
  1. 通过 Thrift 协议连接 Hive Metastore
  2. 获取表定义（schema + partition spec）
  3. 获取分区列表
  4. 生成数据文件路径
  5. 通过 ObjectStorage 读取数据
```

## 16.6 Parquet 读取优化

`src/Processors/Formats/Impl/ParquetBlockInputFormat.h` — Parquet 是 Lakehouse 的主要数据格式。

### Parquet 文件结构

```
Parquet File:
  ├── Magic: PAR1
  ├── Row Group 1
  │     ├── Column Chunk (col_a)
  │     │     ├── Data Page (压缩的数据)
  │     │     ├── Dictionary Page (可选)
  │     │     └── ...
  │     ├── Column Chunk (col_b)
  │     └── ...
  ├── Row Group 2
  │     └── ...
  ├── Footer (元数据)
  │     ├── Schema
  │     ├── Row Group 统计信息
  │     │     ├── 行数
  │     │     ├── 每列的 min/max/null_count
  │     │     └── 每列的编码/压缩方式
  │     └── Key-Value Metadata
  └── Footer Length + Magic
```

### 列裁剪

```
查询: SELECT col_a, col_b FROM t WHERE col_c = 1

Parquet 读取优化:
  1. 只读取 col_a, col_b, col_c 的 Column Chunk
  2. 不读取 col_d, col_e, ... 的数据
  3. 通过 Footer 中的偏移量直接 seek 到目标 Column Chunk
```

### Row Group 裁剪

```
查询: WHERE col_a > 100

Row Group 级别裁剪:
  Row Group 1: col_a max = 50 → 排除（所有行 < 100）
  Row Group 2: col_a max = 200 → 可能包含 → 读取
  Row Group 3: col_a max = 80 → 排除
  Row Group 4: col_a min = 150 → 可能包含 → 读取

结果: 只读取 Row Group 2 和 4
```

### Page 级别过滤

```
Page 级索引 (Parquet 的 Page Index / Column Index):
  每个 Data Page 记录 min/max/null_count
  → 可以跳过不满足条件的 Page
  → 粒度比 Row Group 更细

场景: 一个 Row Group 有 100 万行，10 个 Page
  WHERE col_a = 42
  → Page 3: col_a min=40, max=45 → 可能包含
  → 其他 Page: col_a max < 40 或 min > 45 → 排除
  → 只读取 Page 3（10 万行），而非整个 Row Group（100 万行）
```

## 16.7 统一的 ObjectStorage 访问层

所有 Lakehouse 格式共享同一个 `StorageObjectStorage` 基础设施：

```
StorageObjectStorage
  ├── DataLake 接口
  │     ├── Iceberg (C++ 原生实现)
  │     ├── DeltaLake (Rust Kernel FFI)
  │     └── Paimon (C++ 原生实现)
  │
  ├── ObjectStorage 后端
  │     └── S3 / Azure / HDFS
  │
  └── 分布式执行
        └── StorageObjectStorageCluster → 跨节点并行扫描
```

### StorageObjectStorageCluster

`src/Storages/ObjectStorage/StorageObjectStorageCluster.h` — 分布式 Lakehouse 查询：

```
Coordinator:
  1. 从 DataLake 元数据获取文件列表
  2. 将文件列表分片
     → 按 Parquet Row Group 边界切分
     → 保证每个分片大小均衡
  3. 分发给多个 Worker 节点

Workers:
  1. 各自读取分配到的文件
  2. 执行过滤、投影、聚合
  3. 返回部分结果

Coordinator:
  1. 合并结果
  2. 如果有 GROUP BY → 重新聚合
  3. 如果有 ORDER BY → 排序
```

### 创建 Lakehouse 表的语法

```sql
-- Iceberg
CREATE TABLE iceberg_table ENGINE = Iceberg(
    's3://bucket/path/to/table',
    aws_access_key_id = '...',
    aws_secret_access_key = '...'
);

-- Delta Lake
CREATE TABLE delta_table ENGINE = DeltaLake(
    's3://bucket/path/to/table',
    aws_access_key_id = '...',
    aws_secret_access_key = '...'
);

-- Paimon
CREATE TABLE paimon_table ENGINE = Paimon(
    's3://bucket/path/to/table',
    aws_access_key_id = '...',
    aws_secret_access_key = '...'
);

-- 使用 Iceberg Catalog
CREATE TABLE iceberg_catalog_table ENGINE = Iceberg(
    catalog_url = 'https://glue.amazonaws.com/...',
    database_name = 'my_db',
    table_name = 'my_table'
);
```

## 16.8 本章小结

```
Lakehouse 支持成熟度:
  Iceberg    → 读写删全支持 (C++ 原生, 30+ 头文件)
  Delta Lake → 读写支持 + CDC (Rust Kernel FFI)
  Paimon     → 只读 (早期)
  Hive       → 读取支持

核心架构:
  StorageObjectStorage → DataLake 层 → ObjectStorage 层
  所有格式共享同一套 ObjectStorage 基础设施

Iceberg 裁剪层次:
  Snapshot → Manifest List → Manifest → DataFile
  分区裁剪 → 列统计裁剪 → Row Group 裁剪 → Page 裁剪

Parquet 读取优化:
  列裁剪 → 只读取需要的列
  Row Group 裁剪 → 利用 Footer 统计信息
  Page 级裁剪 → 利用 Page Index

分布式执行:
  StorageObjectStorageCluster → 文件分片 → Worker 并行扫描
```

**关键文件地图**：
```
src/Storages/ObjectStorage/DataLakes/IDataLake.h             → DataLake 接口
src/Storages/ObjectStorage/DataLakes/Iceberg/                → Iceberg 实现
src/Storages/ObjectStorage/DataLakes/Iceberg/ManifestFilesPruning.h → 裁剪算法
src/Storages/ObjectStorage/DataLakes/Iceberg/IcebergWrites.h → Iceberg 写入
src/Storages/ObjectStorage/DataLakes/DeltaLake/              → DeltaLake 实现
src/Storages/ObjectStorage/DataLakes/Paimon/                 → Paimon 实现
src/Storages/ObjectStorage/StorageObjectStorageCluster.h     → 分布式查询
src/Processors/Formats/Impl/ParquetBlockInputFormat.h        → Parquet 读取
```
