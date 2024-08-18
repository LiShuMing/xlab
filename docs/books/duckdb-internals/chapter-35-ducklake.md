# 第35章：DuckLake —— SQL 作为 Lakehouse Format

> Lakehouse 的元数据管理一直是痛点——Iceberg 用 JSON/Avro 文件维护清单，Delta Lake 用 JSON 事务日志，Hudi 用时间线文件。DuckDB 团队提出了一个激进的洞察：与其用文件管理元数据，不如用一个 SQL 数据库管理元数据。

## 35.1 Lakehouse 的元数据困局

### 三大 Lakehouse 格式的元数据复杂度

| 格式 | 元数据存储 | 元数据格式 | 一致性保证 |
|------|-----------|-----------|-----------|
| Iceberg | 清单文件 + 快照文件 + 元数据 JSON | JSON + Avro | 文件级乐观并发 |
| Delta Lake | 事务日志 JSON 文件 | JSON | 文件级乐观并发 |
| Hudi | 时间线文件 | Avro/JSON | 文件级乐观并发 |

共同问题：
1. **元数据碎片化**：一个表可能有成千上万个元数据文件，维护它们的一致性是分布式系统问题
2. **读取开销**：读一个表需要先读取多层元数据文件（快照 → 清单 → 数据文件），延迟高
3. **并发控制复杂**：文件级的乐观并发控制需要处理冲突、重试、合并——这不是数据库用户想关心的事
4. **小文件问题**：频繁写入产生大量小文件，元数据膨胀

## 35.2 DuckLake 的核心洞察：用 SQL 数据库管理元数据

### 架构：两层设计

```
┌─────────────────────────────────────────────┐
│              DuckLake 实例                   │
├─────────────────────────────────────────────┤
│  元数据层（SQL 数据库）                       │
│  ├── DuckDB / PostgreSQL / SQLite           │
│  ├── ACID 事务保证                           │
│  ├── 快照、Schema 演进、分区信息             │
│  └── 多客户端并发访问                        │
├─────────────────────────────────────────────┤
│  数据层（Parquet 文件）                      │
│  ├── 本地磁盘 / 对象存储（S3, GCS, ...）     │
│  ├── 开放格式，无供应商锁定                   │
│  └── 统计信息用于过滤下推                     │
└─────────────────────────────────────────────┘
```

**关键设计决策**：元数据用 SQL 数据库（DuckDB、PostgreSQL 或 SQLite），数据用 Parquet 文件。元数据层天然提供 ACID 事务——不需要在文件系统上重新实现并发控制。

### 与 Iceberg/Delta Lake 的本质差异

```
Iceberg/Delta Lake:
  元数据 = 文件（JSON/Avro）
  → 并发控制需要自己实现（乐观锁 + 重试）
  → 读元数据 = 多层文件读取
  → 小文件问题是架构性的

DuckLake:
  元数据 = SQL 数据库表
  → 并发控制由数据库引擎提供
  → 读元数据 = SQL 查询
  → 无小文件问题（数据库内部管理存储）
```

## 35.3 关键特性（DuckLake 0.1 → 1.0 的演进，2025.05 → 2026.04）

### 版本时间线

```
2025.05  DuckLake 0.1 — 初始发布（SQL as a Lakehouse Format）
2025.07  DuckLake 0.2 — 改进与修复
2025.09  DuckLake 0.3 — Iceberg 互操作性 + Geometry 类型支持
2025.10  Frozen DuckLakes — 多用户 Serverless 数据访问
2026.04  Data Inlining — 解锁流式写入
2026.04  DuckLake 1.0 — 生产就绪版本，保证向后兼容
```

### Data Inlining：解锁流式写入

传统 Lakehouse 格式要求每次写入产生完整的 Parquet 文件——这不适合流式写入（高频率小批量）。DuckLake 的 Data Inlining 允许将小批量数据直接嵌入元数据层：

```
传统模式: 每次写入 → 生成 Parquet 文件 → 注册到元数据
Data Inlining: 小批量 → 数据直接存入元数据库 → 积累到阈值后转为 Parquet
```

这解决了流式场景下的"小文件问题"——高频写入的数据先存在元数据库中，积累到一定量后批量转为 Parquet。

### Frozen DuckLakes：多用户 Serverless 数据访问

Frozen DuckLake 是一个只读快照——多个用户可以同时查询同一个 Frozen DuckLake，无需计算资源分配：

```
生产 DuckLake（读写）
  → Freeze → Frozen DuckLake 1（只读，用户 A 访问）
  → Freeze → Frozen DuckLake 2（只读，用户 B 访问）
```

这为 Serverless 场景提供了成本效益——只读访问不需要计算实例。

### Clustering：自动聚簇优化查询性能

DuckLake 支持按指定列自动聚簇数据——物理数据布局按聚簇键排序，提升 Zone Map 裁剪效果：

```sql
ALTER TABLE my_table CLUSTER BY (user_id, event_date);
```

### Bucket Partitioning：与 Iceberg 生态互通

Bucket Partitioning 允许按哈希桶分区数据——与 Iceberg 的 Bucket Transform 兼容，方便跨格式数据交换。

### Geometry 与 Variant 类型：半结构化数据的原生支持

- **Geometry**：空间数据类型，与 PostGIS 兼容
- **Variant**：半结构化类型（类似 JSON），内部使用 Shredded 存储优化

### Iceberg 互操作性

DuckLake 0.3 引入了 Iceberg 互操作性——DuckLake 可以读取 Iceberg 表的元数据，实现跨格式查询。

### Agent Sandbox Isolation：AI Agent 的安全数据访问隔离

为 AI Agent 提供沙箱隔离的计算环境——Agent 只能访问授权的数据集，沙箱内的修改不影响主数据。这是 AI Agent 在生产环境中安全使用数据的架构基础。

## 35.4 与 Apache Iceberg/Delta Lake 的对比

### 元数据管理的本质差异

| 维度 | Iceberg | Delta Lake | DuckLake |
|------|---------|-----------|----------|
| 元数据存储 | 文件（JSON + Avro） | 文件（JSON） | SQL 数据库 |
| 并发控制 | 乐观锁（文件级） | 乐观锁（文件级） | 数据库 ACID |
| 读取延迟 | 多层文件读取 | 线性日志读取 | SQL 查询 |
| 元数据规模 | O(文件数) | O(提交数) | O(行数，数据库管理) |
| 小文件问题 | 有（需 compaction） | 有（需 OPTIMIZE） | 无 |
| 事务隔离 | 快照隔离 | 快照隔离 | 数据库级隔离 |
| 跨表事务 | 不支持 | 不支持 | 支持（SQL 数据库原生） |

### 读写路径的延迟差异

```
Iceberg 读路径:
  元数据 JSON → 快照 → 清单列表 → 清单 Avro → 数据文件列表 → Parquet 文件
  延迟：多层文件读取，数十到数百毫秒

DuckLake 读路径:
  SQL 查询元数据库 → 获取数据文件列表 → Parquet 文件
  延迟：一次 SQL 查询，毫秒级
```

### DuckLake 的工程哲学

> "借用 Iceberg 和 Delta Lake 的最佳想法，但加上低延迟和 Agent 沙箱隔离"

DuckLake 不试图替代 Iceberg/Delta Lake——它借鉴了它们的开放格式（Parquet）、分区、快照等核心概念，但用 SQL 数据库替代了文件级元数据管理。这是对"数据库是管理结构化数据的最佳工具"这一第一性原理的回归。

## 35.5 DuckLake 源码剖析：作为 DuckDB Extension 的实现方式

DuckLake 作为 DuckDB Extension 实现，核心是通过 `ATTACH` 语句挂载：

```sql
-- 使用 DuckDB 作为元数据库
ATTACH 'ducklake:metadata.ducklake' AS my_ducklake (DATA_PATH 'data/');

-- 使用 PostgreSQL 作为元数据库
ATTACH 'ducklake:postgres:dbname=ducklake_catalog host=your_postgres_host' AS my_ducklake (DATA_PATH 'data/');

-- 使用 SQLite 作为元数据库
ATTACH 'ducklake:sqlite:metadata.sqlite' AS my_ducklake (DATA_PATH 'data/');
```

这种设计使得 DuckLake 利用 DuckDB 现有的 `ATTACH` 机制——不需要新的连接器或协议。元数据库可以是 DuckDB（本地/嵌入式）、PostgreSQL（生产/多用户）或 SQLite（轻量级）。

MIT 许可证确保了 DuckLake 的开放性——规范和扩展都可在任何项目中自由使用。

## 本章小结

DuckLake 的核心洞察是一个"元回归"：**用数据库管理元数据，而不是用文件管理元数据**。这不是技术倒退——而是对第一性原理的回归。数据库（无论是 DuckDB、PostgreSQL 还是 SQLite）已经解决了并发控制、事务隔离、查询优化等问题——重新在文件系统上实现这些是重复劳动。

DuckLake 的风险在于：元数据库成为单点。Iceberg 的文件级元数据可以放在 S3 上，天然分布式；DuckLake 的元数据库需要维护。但 DuckLake 的回答是：PostgreSQL 已经是久经考验的生产系统，它的可用性远超任何自研的文件级并发控制。

对 DuckDB 用户而言，DuckLake 还有一个独特价值："多玩家 DuckDB"——多个 DuckDB 实例可以读写同一个 DuckLake，这是原生 DuckDB 不支持的。
