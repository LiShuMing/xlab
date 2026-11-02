# Apache Iceberg 深度解析：格式演进、生态博弈与技术洞察（2023–2026）

> 作者背景：StarRocks 核心开发者，日常与 C++/向量化执行/分布式系统打交道。本文从一线工程师视角梳理 Iceberg 近年演进，重点关注那些对引擎实现和架构选型有实质影响的技术决策。

---

## Executive Summary

Apache Iceberg 在过去三年完成了一次关键的范式跃迁：从一个"解决 Hive 大表管理问题"的表格式，演变成了开放数据湖架构的**事实标准元数据层**。这一转变的核心驱动力有三：

1. **Spec v3 的落地**（v1.8.0–v1.10.0，2025 年）：Deletion Vectors、Row Lineage、Variant 类型、原生加密等能力，将 Iceberg 推向了与传统数仓功能等价的区间。
2. **REST Catalog 生态的爆发**：Snowflake 捐献 Apache Polaris、Databricks 开源 Unity Catalog、AWS S3 Tables 原生支持，Credential Vending 机制成为多引擎安全访问的标配。
3. **商业格局重塑**：2024 年 6 月 Databricks 以逾 10 亿美元收购 Iceberg 原班人马 Tabular，直接将 Iceberg 核心贡献者纳入麾下，随之而来的是对社区走向的话语权争夺。

对于 StarRocks 这样的 OLAP 引擎而言，Iceberg 既是最重要的 External Table 数据源，也是理解对手（Trino/Spark 生态）技术优先级的参照系。理解 Iceberg 的演进方向，本质上是在理解整个 Lakehouse 生态的重力场。

---

## 一、Format Spec 演进：v1 → v2 → v3 核心差异

### Spec v1：快照隔离的奠基

Spec v1 解决的核心问题是：**如何在不可变对象存储上实现 ACID 语义**。其核心设计思想是三层元数据结构：

```
Table Metadata JSON
  └── Manifest List (Avro)
        └── Manifest File (Avro) × N
              └── Data File (Parquet/ORC/Avro) × M
```

每次写入产生新的 Snapshot，旧快照的所有指针链仍然可达，天然实现 Time Travel。Schema Evolution 通过字段 ID（而非字段名）追踪字段映射，彻底解决了 Hive 时代"改列名即破坏下游"的痛点。**Hidden Partitioning**（隐式分区）是另一个关键设计——用户定义 `PARTITIONED BY (months(event_time))`，引擎自动推断分区剪裁，查询中无需写 `WHERE partition_col = '2024-01'`。

### Spec v2：行级删除的引入（2020–2022）

v2 的核心新增是 **Row-level Deletes**，支持两种实现模式：

**Position Delete File**：以 `(file_path, row_position)` 二元组标记删除位置，存储为独立的 Avro 文件。精确高效，但读取时需要额外 Join——引擎必须先读 Data File，再对照 Position Delete File 过滤已删除行。对于高并发小批量删除场景，Position Delete File 会快速堆积，导致读放大（Read Amplification）显著上升。

**Equality Delete File**：通过指定列值（如 `id = 5`）标记删除，类似于 CDC 中的 before-image。写入代价极低，但读取时有全表扫描风险——引擎必须将所有 Equality Delete 的条件 Join 到 Data File 上，且无法利用 Column Statistics 剪裁（因为 delete 条件可能覆盖多个 data file）。Trino、StarRocks 等引擎对 Equality Delete 的向量化支持普遍落后于 Position Delete，这是 v2 表在 MOR 场景下的现实痛点。

v2 还引入了 **Sequence Number** 机制，为每次 Commit 分配单调递增的序列号，解决了 Delete File 与 Data File 之间的时序语义问题——只有序列号 ≤ delete file 序列号的 data file 才需要应用该 delete。

### Spec v3：2025 年的全面升级

Spec v3 的核心变更集中在四个方向（参考 [v3 Spec](https://iceberg.apache.org/spec/)，v1.8.0 起逐步落地）：

#### 1. Deletion Vector（DV）：彻底重塑行级删除

这是 v3 最重要的单点变化，思路直接借鉴自 Delta Lake 的 Deletion Vectors 设计。DV 以 **Roaring Bitmap** 的二进制形式存储每个 Data File 中被删除行的位置集合，存储在 [Puffin 文件](https://iceberg.apache.org/puffin-spec/)（`.stat` 文件）中，并通过 `content_offset + content_size_in_bytes` 直接定位到对应 Data File 的 DV blob。

关键设计约束：**一个 Data File 在任意 Snapshot 中至多对应一个 DV**。当新的删除到来时，Writer 必须将新删除与已有 DV 合并（或与现有 Position Delete File 合并），而不是新增一个 DV 文件。这从根本上避免了 v2 时代 Position Delete File 堆积的问题。

与 v2 Position Delete 的工程权衡对比：

| 维度 | v2 Position Delete | v3 Deletion Vector |
|------|-------------------|-------------------|
| 写入模式 | 每次删除产生新文件 | 合并进单一 Bitmap |
| 读取开销 | 需 Join 多个 delete file | 直接 Bitmap AND 操作 |
| 文件数增长 | 线性增长 | 恒定（每 data file 1 个 DV） |
| Compaction 压力 | 高 | 低 |
| 引擎实现复杂度 | 中 | 高（需处理 64-bit Roaring Bitmap 分层结构） |

目前（截至 2025 年底）Spark on EMR 7.12、Flink、Starburst Galaxy 已原生支持 DV；Trino 尚不支持；StarRocks、ClickHouse、BigQuery 等仍停留在 v1/v2。

#### 2. Row Lineage：行级血缘追踪

v3 强制要求所有新写入的 Data File 携带两个隐式字段：

- `_row_id`：全局唯一 long 类型行标识符，通过继承机制（inheritance）在 Commit 成功后由 `next-row-id` 表属性分配（写 Manifest 时 Commit 序列号尚未确定，因此用继承而非提前写入，避免 OCC 重试时重写 data file）。
- `_last_updated_sequence_number`：记录该行最后被修改时的 Snapshot 序列号。

这两个字段天然支持**增量处理（Incremental Processing）**——下游系统可以通过过滤 `_last_updated_sequence_number > last_watermark` 来精确捞取变更行，无需扫描整个表做快照 diff。这对物化视图增量刷新、CDC 管道、审计追踪场景意义重大。需要注意的是，Row Lineage 不追踪通过 Equality Delete 更新的行（因为 Equality Delete 语义上引擎不读取旧行即可执行删除）。

#### 3. 新数据类型：Variant、Geospatial、Nanosecond Timestamp

**Variant 类型**：半结构化数据的原生支持，编码规范复用 Apache Parquet 项目的 Variant 标准，本质上是比 JSON-string 更强的类型系统——支持 date、timestamp、decimal 等原生类型的嵌套，避免了将 JSON 塞进 VARCHAR 列的 schema 腐化问题。Variant Shredding（将频繁访问的子路径提取为独立列，利用 Column Statistics 剪裁）尚在开发中，是 v3 生态成熟的关键里程碑。

**Geospatial 类型**（`geometry`/`geography`）：与 Parquet 社区协同定义，为位置分析场景（物流、零售地理围栏等）提供原生存储语义，是目前 Starburst Galaxy 少数支持的引擎之一。

**Nanosecond Timestamps**（`timestamp_ns`/`timestamptz_ns`）：从 microsecond 精度升级至 nanosecond，对高频交易、IoT 传感器等对时间精度敏感的场景至关重要。

#### 4. 原生表加密

v1.10.0（2025 年 9 月）合并了 Spec 层的加密支持（[#12162](https://github.com/apache/iceberg/pull/12162)、[#12927](https://github.com/apache/iceberg/pull/12927)），在 REST Catalog Spec 中新增 encryption keys API（[#12987](https://github.com/apache/iceberg/pull/12987)）。加密密钥由 Catalog 管理和分发，引擎无需直接持有云存储密钥，与 Credential Vending 机制形成互补的安全体系。

---

## 二、元数据层深度解析

### Manifest 三层结构的工程意义

Iceberg 的三层元数据结构（Manifest List → Manifest File → Data File）并非过度设计，而是在"元数据读取开销"与"精确剪裁能力"之间的工程平衡：

**Manifest List**：Snapshot 的入口，记录该快照涉及的所有 Manifest File 路径及其聚合统计（added/deleted/existing 文件数、row count）。引擎打开一个 Snapshot 只需读这一个文件，开销是常数级的。

**Manifest File**（Avro 格式）：每条记录对应一个 Data File，包含该文件的分区信息和**列级统计信息**（`lower_bounds`、`upper_bounds`、`null_value_counts`）。这是 **File Skipping**（文件剪裁）的核心载体——引擎在 Scan Planning 阶段扫描 Manifest 中的 min/max 统计，即可跳过不可能包含目标数据的 Data File，整个过程无需打开 Parquet 文件头。对于宽表（数百列）或大规模表（数百 TB），这个层级的剪裁效果远超 Hive Partition Pruning 能提供的粒度。

**Manifest Caching**：在高并发读场景（如 StarRocks 的 External Table 查询），Manifest 文件频繁被反复读取。引擎侧的 Manifest 缓存（基于 Snapshot ID + Manifest Path 作为缓存 key）是生产环境必要的优化。StarRocks 的 Iceberg Catalog 实现了 Manifest Cache，在热点表查询场景下显著降低了 S3 List/GET 请求数。

### Snapshot 隔离模型与 WAP 模式

Iceberg 的 Snapshot 支持四种操作语义：
- **Append**：仅新增 Data File，不覆盖已有数据。
- **Overwrite**：替换特定分区的数据（动态分区覆盖）。
- **Replace**：Compaction 场景专用，用新文件替换旧文件但不改变逻辑数据。
- **Delete**：通过 Delete File 标记行级删除。

**Branch / Tag**（Snapshot Reference）：v1.1.0 开始引入，概念上类比 Git 分支模型，但差异显著：Git 的 branch 是轻量指针，可以 merge/rebase；Iceberg 的 Branch 是 Snapshot 链的命名引用，"merge"本质上是选取某个 Branch 上的 Snapshot 链写入主分支。

**WAP（Write-Audit-Publish）模式**是 Branch 的经典工程实践：数据先写入一个 `audit` Branch，经过数据质量校验后再通过 `cherrypick_snapshot` 或 `fast_forward` 操作将其发布到 `main` Branch，实现生产数据的"先审后发"。Netflix 等公司的大规模数据管道中大量使用这一模式，避免坏数据直接污染生产表。

---

## 三、并发控制与事务模型

### Optimistic Concurrency Control（OCC）

Iceberg 的并发写入基于**乐观并发控制**：所有 Writer 各自读取当前 Snapshot，在本地构建新的 Metadata（新 Manifest、新 Snapshot），最后通过 Catalog 原子性地将 Table Metadata 指针从旧版本 CAS（Compare-And-Swap）到新版本。

不同 Catalog 后端的原子性保证机制：
- **S3（HadoopCatalog）**：S3 Conditional PUT（`if-none-match`）或 DynamoDB 原子 Put——注意 S3 标准 API 不原生支持 CAS，HadoopCatalog 在 S3 上的并发安全性依赖 DynamoDB Lock 或 S3 版本控制，生产环境不推荐用于高并发写场景。
- **Hive Metastore**：HMS 的乐观锁通过数据库事务 + 版本号 CAS 实现，在高并发下容易成为瓶颈。
- **REST Catalog**：标准化的 HTTP CAS 操作，由 Catalog 服务端保证原子性，是目前最推荐的生产方案。
- **Nessie**：基于 Git-like 分支的多写场景，通过 Nessie 服务端的 OCC 保证。

**Commit Conflict 重试策略**：当两个 Writer 同时提交时，后者会收到冲突响应，触发 `RetryableCommit` 机制——重新读取最新 Snapshot，重放本次写操作（如 `DataOperations.newAppend()`），再次尝试提交。Iceberg 的冲突检测粒度是分区级别：两个 Writer 写不相交分区时可并发成功；写相同分区时后者需重试。这意味着对于高并发流式写入同一分区的场景（如按 hour 分区的实时数据），需要特别设计 Writer 分桶策略来降低冲突率。

### Catalog 类型技术选型

| Catalog | 原子性保证 | 多分支 | Credential Vending | 适用场景 |
|---------|-----------|-------|-------------------|---------|
| Hive Metastore | DB事务 | ✗ | ✗ | 存量迁移 |
| REST Catalog | 服务端CAS | 实现相关 | ✓（Polaris/UC） | 生产推荐 |
| AWS Glue | DynamoDB | ✗ | ✓（Lake Formation） | AWS原生 |
| Nessie | Git-style OCC | ✓ | ✗ | 实验/审计 |
| JDBC | DB事务 | ✗ | ✗ | 小规模自建 |

---

## 四、Row-level Deletes 三种实现的工程权衡

### Copy-on-Write（COW）vs Merge-on-Read（MOR）

这是引擎实现 DML 时最核心的架构选择：

**COW 模式**：DELETE/UPDATE 时重写整个受影响的 Data File，生成新文件并在 Manifest 中替换旧文件。**写放大（Write Amplification）极高**——一条记录的修改可能触发整个 Parquet 文件（通常 128MB–1GB）的重写。但读取时无额外开销，任何引擎读到的都是干净的 Data File，无需处理 Delete File。对于低频批量更新、读多写少场景，COW 是正确选择。

**MOR 模式**：DELETE/UPDATE 时只追加 Delete File（v2 的 Position/Equality Delete 或 v3 的 DV），Data File 原地不动。**写开销极低**，适合高频实时更新。但读取时引擎必须 Merge Data File 与 Delete File，产生读放大。随着 Delete File 积累，读性能持续下降，这是 Compaction（`rewrite_data_files`）存在的根本原因。

### Position Delete vs Equality Delete vs Deletion Vector

从工程实践角度，三种行级删除实现的选型建议：

**Position Delete**（v2）：精确删除，读取时开销可控（需 Sort-Merge Join data file 与 delete file，可向量化）。适合 CDC Upsert 场景。但高频小批量删除会导致大量小 delete file，触发 `rewrite_position_delete_files` 的 Compaction 需求。

**Equality Delete**（v2）：写入极简（只记录 `id = 5`），但读取代价高昂——每个 Data File 都需要与 Equality Delete 的条件做 Anti-Join，且该 Join 无法被 Partition Pruning 优化。生产环境应尽量避免大量 Equality Delete 堆积，需要及时 Compaction 将其转换为 COW 的干净文件。

**Deletion Vector**（v3）：兼顾写入效率（Bitmap append 开销低）与读取效率（SIMD 友好的 Roaring Bitmap AND 操作），是目前三种方案中工程权衡最优的选择。唯一代价是引擎实现复杂度较高（需要处理 Puffin 文件的读写，64-bit Roaring Bitmap 的分层结构），以及目前生态支持度尚不完整。

---

## 五、表维护机制

### Compaction：`rewrite_data_files` 与 `rewrite_manifests`

Compaction 是 Iceberg MOR 模式的核心运维负担，本质上是用计算换存储整洁度。

**`rewrite_data_files`** 支持两种策略：
- **Bin-packing**：将多个小文件合并为目标大小（默认 512MB）的文件，解决 small files 问题，是最常见的 Compaction 场景。
- **Sorting**：按指定 Sort Order（`ORDER BY (date, user_id)` 等）重组文件，提升后续查询的 Data Skipping 效率。高阶变种是 **Z-Order**（多列 locality preserving sort），在 `(x, y)` 二维查询场景下将相关数据物理聚合，减少 file scan 数。Z-Order 在 Spark 的 `rewrite_data_files` procedure 中已有实现（通过 `strategy='sort', sort_order='zorder(col1, col2)'`）。更进一步的 **Hilbert Curve** 排序（比 Z-Order 具有更好的空间局部性）也在社区讨论中。

Compaction 的并发安全性由 Iceberg 的 OCC 机制保证：Compaction Job 在 Commit 阶段执行 Replace 操作，如果此期间有新的 Write 发生在同一文件集合上，Commit 会失败并重试或放弃（取决于实现）。实践中建议 Compaction 与 Write 使用不同的分区时间窗口（如只 Compact `date < today - 1`），避免冲突。

**`rewrite_manifests`**：当 Manifest 文件过多或包含大量已删除文件条目时，Manifest 本身的读取开销会上升。`rewrite_manifests` 将多个 Manifest 合并、剔除已过期条目，降低 Scan Planning 的 List 开销。

Flink 1.10.0 合并了 Flink Table Maintenance API 中的 `RewriteDataFiles` 支持（[#11497](https://github.com/apache/iceberg/pull/11497)），使得 Flink 作业可以在流式写入的同时触发 Compaction，降低运维复杂度。

### Snapshot 过期与 Orphan Files 清理

**`expire_snapshots`**：Iceberg 通过引用计数而非直接删除来管理 Snapshot 生命周期。`expire_snapshots` 会标记不再被任何 Branch/Tag 引用的 Snapshot 为过期，并删除其独占的文件（其他 Snapshot 仍在引用的文件不会被删除）。在流式写入场景下，如果 Checkpoint 间隔内产生大量 Snapshot，建议合理设置 `min-snapshots-to-keep` 和 `max-snapshot-age-ms`，防止元数据膨胀。

**Orphan Files**：由于 Writer Failure（写了 Data File 但 Commit 未成功）、Compaction 中间状态等原因，对象存储中可能存在不被任何 Snapshot 引用的"孤儿文件"。`delete_orphan_files` 通过对比 Snapshot 链路中所有引用文件集合与存储中实际文件的差集来识别孤儿文件。**安全边界**：由于新写入的文件在被 Commit 前也是"孤儿"状态，`delete_orphan_files` 必须设置 `older_than` 参数（通常 > 1 小时）来避免误删正在写入中的文件。

### Puffin 文件与 Table Statistics

[**Puffin Spec**](https://iceberg.apache.org/puffin-spec/) 是 Iceberg 定义的统计信息专用文件格式，本质上是一个 Blob 容器，支持多种 Blob 类型。目前已在 Spec 中正式化的 Blob 类型：

- **`apache-datasketches-theta-v1`**：基于 Apache DataSketches 库的 Theta Sketch，用于近似估算列的 NDV（Number of Distinct Values）。NDV 对查询优化器的 Join 重排序（Join Reordering）至关重要——CBO 需要知道 `user_id` 列有 1 亿个不同值 vs `country_code` 只有 200 个，才能做出正确的 Join 顺序决策。
- **`deletion-vector-v1`**（v3 新增）：即上文的 Roaring Bitmap DV。

Puffin 文件与 Snapshot 绑定（通过 `snapshot-id` 和 `sequence-number` 关联），保证统计信息的时序一致性。Trino 通过 `compute_table_stats` 生成 Puffin 统计；Spark 通过 `compute_table_statistics` procedure 支持；AWS Glue Data Catalog 在 2024 年 7 月支持了为 Iceberg 表生成列级统计（存储为 Puffin 文件，供 Amazon Redshift Spectrum 的 CBO 使用）。

对于 StarRocks 而言，读取 Puffin 中的 NDV 估计并馈入 CBO 是一个高价值的优化方向——外表查询的 Join 顺序决策目前很大程度上依赖 Data File 的 row count，NDV 信息的引入将显著提升估计准确性。

---

## 六、多引擎集成深度对比

### Spark 集成

Spark 是 Iceberg 功能支持最完整的引擎，这本质上反映了 Iceberg 原始设计目标（Netflix 的 Spark 大表管理）。关键集成点：

- **SparkCatalog / SparkSessionCatalog**：前者作为独立 Catalog 注册（`spark.sql.catalog.my_catalog = org.apache.iceberg.spark.SparkCatalog`），后者替换 Spark 默认 Session Catalog 实现无缝迁移。
- **DataSource V2 API**：Iceberg 深度集成 Spark DSv2，支持 ScanBuilder（谓词下推、列裁剪）、SupportsReportStatistics（统计信息上报）等接口，是 File Skipping 工作的 API 基础。
- **Structured Streaming Exactly-Once**：Flink Sink 的 2PC 对应 Spark Structured Streaming 的 `checkpoint` 机制——Spark 在每个 Checkpoint 时 Commit 一批 Iceberg 数据，保证 Checkpoint 与 Commit 对齐，即使作业重启也不重复提交。
- **Spark 4.0 集成**（v1.10.0，[#12494](https://github.com/apache/iceberg/pull/12494)）：随 Spark 4.0 正式支持，是最新版本的重要里程碑。

### Flink 集成

Flink Iceberg Sink 的 **Two-Phase Commit（2PC）** 是其 Exactly-Once 语义的基石：
1. Pre-commit（Checkpoint 触发）：Writer 将缓冲数据 Flush 到对象存储，记录待提交的文件列表。
2. Commit（Checkpoint 完成）：Committer 将文件列表提交为新 Iceberg Snapshot。

如果 Committer 在第 2 步前崩溃，恢复后从 Checkpoint 重做第 2 步（幂等提交）；如果第 1 步未完成，恢复后重放第 1、2 步（Exactly-Once 数据）。

**Incremental Scan**：Flink 读取 Iceberg 时可以指定 `start-snapshot-id` 和 `end-snapshot-id`，仅读取该 Snapshot 区间内新增的 Data File，这是 Change Data Capture 下游消费的基础。v1.10.0 新增了 `StreamingStartingStrategy.INCREMENTAL_FROM_LATEST_SNAPSHOT_EXCLUSIVE`（[#12899](https://github.com/apache/iceberg/pull/12899)），满足"从当前快照之后开始消费"的流式场景。

### Trino / StarRocks / DuckDB 集成对比

| 引擎 | Spec 支持 | DV支持 | Equality Delete向量化 | Metadata Tables | 说明 |
|------|---------|--------|---------------------|----------------|------|
| Trino | v1/v2 | ✗（规划中） | ✓ | ✓ | Iceberg 原始合作伙伴 |
| StarRocks | v1/v2 | ✗（roadmap） | 部分支持 | ✓ | External Catalog 方案成熟 |
| DuckDB | v1/v2 | ✗ | 有限 | ✓ | 适合单机分析场景 |
| Spark | v1/v2/v3 | ✓ | ✓ | ✓ | 功能最完整 |
| Starburst Galaxy | v1/v2/v3 | ✓ | ✓ | ✓ | 目前 v3 支持最全面的商用引擎 |

StarRocks 作为 OLAP 引擎，其 Iceberg 集成的核心价值在于 External Catalog（`CREATE EXTERNAL CATALOG` 直接对接 Hive/REST/Glue Catalog）和向量化 Parquet 读取。当前对 Equality Delete 的处理存在性能短板（需要 Anti-Join），这也是 v3 DV 对 StarRocks 而言升级优先级较高的原因——DV 的 Roaring Bitmap AND 操作更友好于向量化执行模型。

### PyIceberg

[PyIceberg](https://py.iceberg.apache.org/) 是纯 Python 实现的 Iceberg 客户端（非 Java 桥接），与 PyArrow、pandas、DuckDB 无缝互操作。目前写入能力仍有限制，完整 DML（DELETE/UPDATE/MERGE）支持尚在开发中，但 Python 生态的读取和 Schema/Partition Evolution 操作已趋于成熟，是数据科学家和 ML 工程师访问 Iceberg 表的主流路径。

---

## 七、REST Catalog 生态与云原生集成

### REST Catalog Spec：解耦引擎与 Catalog 实现

[REST Catalog Spec](https://iceberg.apache.org/rest-catalog-spec/)（`open-api/rest-catalog-open-api.yaml`）是 Iceberg 生态过去两年最重要的基础设施演进。其核心价值：**将 Catalog 操作标准化为 HTTP REST API**，使任何引擎只需实现一个 REST 客户端，即可对接所有遵循该规范的 Catalog 实现。

关键安全机制：**Credential Vending（凭证代理）**。传统方式下，每个查询引擎需要直接持有 S3 IAM 凭证；Credential Vending 模式下，Catalog 服务（Polaris、Unity Catalog）在接收到查询请求后，根据 RBAC 权限动态生成**短期、Table 范围内的临时凭证**（AWS STS Token），颁发给引擎，引擎凭此访问对应 S3 路径，凭证过期后自动失效。这是零信任安全架构在 Lakehouse 场景的具体实现。

```sql
-- StarRocks 连接 Polaris（启用 Credential Vending）
CREATE EXTERNAL CATALOG polaris_catalog
PROPERTIES (
  "iceberg.catalog.type" = "rest",
  "iceberg.catalog.uri" = "http://polaris:8181/api/catalog",
  "iceberg.catalog.security" = "oauth2",
  "iceberg.catalog.oauth2.credential" = "client_id:secret",
  "iceberg.catalog.vended-credentials-enabled" = "true"
);
```

### 主流 REST Catalog 实现对比

**Apache Polaris**（Snowflake 捐献，2024 年 8 月 Apache 孵化）：100% 开源的 Iceberg REST Catalog 参考实现，RBAC 模型类似 Snowflake 权限体系，支持 Credential Vending、多租户、Internal/External Catalog 双模式。Snowflake Open Catalog 是其托管版本。StarRocks、Apache Doris、Trino、Spark 等均已验证与 Polaris 的集成（参考 [StarRocks x Polaris 集成实践](https://polaris.apache.org/blog/2025/10/21/starrocks-and-apache-polaris-integration-building-a-unified-high-performance-data-lakehouse/)）。

**Unity Catalog**（Databricks，2024 年 6 月开源）：多模态治理，统一管理 Tables、Files、ML Models、Functions，权限模型比 Polaris 更复杂。托管在 LF AI & Data Foundation 而非 Apache，Databricks 在社区中影响力更直接。Iceberg REST API 兼容，GA 支持 Iceberg 外部表的读写。

**Apache Gravitino**（Datastrato，Apache 孵化）：定位于跨数据源的统一元数据层，支持 Iceberg、Hive、JDBC 等多种 Catalog 抽象，目标是成为统一的 Catalog Proxy。

**Nessie**（Dremio）：Git-style 分支语义，最适合需要数据版本控制、实验性 ETL 的场景。Dremio 在 Polaris 捐献后已声明逐步将 Nessie 重心转向 Polaris，Nessie 更多定位为 Git-like catalog 场景的专用选项。

---

## 八、竞品对比：Delta Lake v3 / Apache Hudi / DuckLake

### Delta Lake vs Iceberg：分歧在哪

Delta Lake 与 Iceberg 在核心理念上有两处根本分歧：

1. **元数据存储方式**：Delta 使用 `_delta_log/` 目录下的 JSON/Parquet transaction log（类似 WAL）；Iceberg 使用 Manifest List + Manifest File 两层 Avro 结构。Delta 的 log 格式对 Spark 更友好（直接 Schema-on-Read），但在 Manifest-level Statistics 的细粒度上弱于 Iceberg（Iceberg 每个 Manifest Entry 携带列级 min/max，Delta 需要 Data Skipping Index 才能达到类似效果）。

2. **引擎中立性**：Iceberg 从设计之初就追求引擎无关（Netflix 用于 Trino/Presto），Delta Lake 早期深度绑定 Spark 生态，虽然通过 `delta-standalone` 和 Delta Kernel 做了解耦，但生态重心仍在 Databricks/Spark。

**Delta Lake v3 与 Iceberg v3 的对齐**：两者在关键特性上高度趋同——Delta 也引入了 Deletion Vectors（早于 Iceberg v3）；Databricks 推动 Delta 与 Iceberg 在 DV 语义上互兼容，是 Iceberg v3 DV 设计参考 Delta DV 的直接原因。这种"趋同"是 Tabular 团队进入 Databricks 后的主动推动，也是 Databricks 整合叙事的技术支撑。

### Apache Hudi：流式 Upsert 的专家

Hudi 的 COW/MOR 双模式、CDC Timeline 设计在流式实时写入场景（如 Flink CDC）具有独特优势，但引擎兼容性和社区规模与 Iceberg 差距持续扩大。从 2024–2025 年各大云厂商的 Managed Service 来看，Iceberg 的覆盖广度（S3 Tables、BigLake、Polaris）已完全压制 Hudi。Hudi 的生存空间越来越集中在 Flink 实时写入 + 低延迟 CDC 场景。

### DuckLake：对 Iceberg 元数据层的"批判性重构"

2025 年 DuckDB Labs 推出的 [DuckLake](https://ducklake.select/) 对 Iceberg 的元数据设计提出了尖锐批评：**为什么要把元数据存在 Object Storage 的文件里，而不是存在数据库里？**

DuckLake 将所有元数据（Snapshot、Manifest、Schema 等）存入关系型数据库（DuckDB、PostgreSQL、BigQuery 等），数据文件仍是 Parquet on S3。其核心优势：
- **多表事务**：直接借助关系型数据库的事务保证，无需 OCC 协调。
- **元数据访问速度快**：数据库 SQL 查询 vs Iceberg 的多次 S3 GET。
- **运维简单**：无 Manifest 文件积累，无 Orphan Files，无 Compaction for metadata。

然而 DuckLake 的批评有一个重要前提假设：**Catalog 总是可用且可信任**。Iceberg 的文件系统元数据恰恰是在"Catalog 挂掉或者 Catalog 不存在（裸 S3 场景）"时仍可通过扫描文件恢复表状态的保障——这对于数据归档、跨组织数据共享等场景至关重要。此外，DuckLake 当前的引擎生态几乎只有 DuckDB/MotherDuck，而 Iceberg 已有 20+ 主流引擎支持。

社区的回应也很直接：有人向 Iceberg 项目提交了 Issue #13196（"Move metadata into the catalog, like DuckLake"），被关闭——Iceberg 不打算走 DuckLake 的路，但 REST Catalog Spec 的演进（将更多元数据操作下推到 Catalog 服务）实际上在服务端实现上已经部分吸收了 DuckLake 的思想。

---

## 九、社区治理与商业化博弈

### Tabular 收购：核心贡献者的迁移

2024 年 6 月 4 日，Databricks 宣布以逾 10 亿美元收购 Tabular——这家由 Iceberg 原作者 Ryan Blue、Daniel Weeks、Jason Reid 创立的公司。时机极为微妙：收购公告恰好在 Snowflake Summit 期间发布，而 Snowflake 当天也宣布将 Polaris Catalog 开源捐献给 Apache。

这次收购的影响是多层次的：

**对 Iceberg 社区独立性的影响**：Tabular 团队（包括 Ryan Blue 等核心 Committer）加入 Databricks 后，仍在 Apache Iceberg 社区活跃贡献，尤其是推动 Spec v3（包括 DV 与 Delta DV 的对齐）。但 Databricks 同时是 Delta Lake 的主导者，其动机难免被质疑——是真正推进 Iceberg 生态，还是通过影响 Spec 方向来最大化自家 Delta/Iceberg 双格式商业价值？目前来看，Spec v3 的关键特性（DV、Row Lineage）在技术上是有价值的，但决策过程的社区透明度需要持续关注。

**Apple、Netflix、AWS 的话语权**：Apple 在 Iceberg 社区长期有稳定贡献（Apple 内部大规模使用 Iceberg），Netflix 是 Iceberg 的发源地，AWS 在 S3 Tables、Glue、EMR 上的投入使其具有强烈的 Iceberg 生态动机。这三家与 Databricks/Snowflake 形成了相互制衡的格局，短期内 Iceberg 社区不大可能被单一商业实体完全主导。

### "支持 Iceberg"已成基础设施选项

从产品竞争角度，一个结构性趋势已经清晰：**"支持 Iceberg"不再是差异化能力，而是数据平台的入场券**。

- **AWS S3 Tables**（2024 年末）：S3 原生支持 Iceberg 表，存储层内置 Compaction、Snapshot 管理，Iceberg 被嵌入对象存储本身。
- **Google BigLake**：将 BigQuery 元数据能力延伸至 Iceberg 表，支持 BigQuery ML 直接读 Iceberg。
- **Snowflake Open Catalog（Polaris 托管版）**：Snowflake 通过捐献 Polaris 并托管其商业版本，将 Iceberg 纳入自己的数据共享生态。
- **Databricks Unity Catalog**：开源后支持 Iceberg REST API，将 Iceberg 作为 Delta 的互操作出口。

这场竞争的本质是：**谁的 Catalog 成为 Iceberg 元数据的权威来源，谁就在多引擎 Lakehouse 架构中占据治理中心地位**。Polaris vs Unity Catalog vs Lakekeeper vs Gravitino 的竞争，本质上是 Catalog 控制权的博弈。

---

## 十、总结与展望

从技术演进轨迹来看，Iceberg 的下一步重心将集中在：

1. **Spec v3 生态落地**：DV、Row Lineage 在主流引擎（Trino、StarRocks、ClickHouse）的实现完善，是 2026 年最值得关注的进展。Variant Shredding 的标准化将决定半结构化数据场景的实用性。

2. **REST Catalog Spec 深化**：加密密钥管理、Catalog 级别的 Multi-table Transactions（借鉴 Nessie 的 Branch 语义或 DuckLake 的 DB 事务），是 Catalog 层向"Lakehouse 数据库"演进的关键路径。

3. **多引擎 v3 支持收敛**：目前 v3 支持存在显著引擎差异，市场会优先向支持度完整的引擎（Spark、Starburst Galaxy）倾斜，倒逼其他引擎加速跟进。

4. **与 DuckLake 的长期竞争**：DuckLake 代表了"元数据回归数据库"的设计哲学，在中小规模、工程简洁性优先的场景具有真实竞争力。Iceberg 需要通过 REST Catalog 的进一步能力提升（更快的元数据操作、原生多表事务）来回应这一挑战，而不是简单否定 DuckLake 的批评。

对于 StarRocks 这类 OLAP 引擎，核心行动项清晰：**优先实现 Deletion Vector 的向量化读取**（SIMD Roaring Bitmap 过滤），跟进 REST Catalog 的 Credential Vending 支持，并持续优化 Manifest Cache 以降低高并发 External Table 查询的元数据开销。这是在 Lakehouse 生态中保持竞争力的技术基础。

---

*参考资料：[Apache Iceberg Spec](https://iceberg.apache.org/spec/) | [GitHub Releases](https://github.com/apache/iceberg/releases) | [Puffin Spec](https://iceberg.apache.org/puffin-spec/) | [REST Catalog Spec](https://iceberg.apache.org/rest-catalog-spec/) | AWS Blog: [Iceberg V3 DV & Row Lineage](https://aws.amazon.com/blogs/big-data/accelerate-data-lake-operations-with-apache-iceberg-v3-deletion-vectors-and-row-lineage/) | Databricks Blog: [Iceberg v3 Ecosystem Unification](https://www.databricks.com/blog/apache-icebergtm-v3-moving-ecosystem-towards-unification) | [Databricks x Tabular Announcement](https://www.databricks.com/company/newsroom/press-releases/databricks-agrees-acquire-tabular-company-founded-original-creators)*
