# SlateDB 架构剖析与阿里云 OSS 存算分离实证（v0.18.1）

> 源码锚定基线：`slatedb/slatedb` `main` (`871b7396`, `v0.18.1`, `object_store 0.14.2`, `foyer 0.22.6`)。
> 配套可复现实验：[labs/slatedb-oss/](../../../labs/slatedb-oss/README.md)。

## 1. 核心定位与设计哲学

SlateDB 是原生构建在对象存储（S3 / GCS / ABS / OSS）之上的嵌入式 LSM-Tree 存储引擎，采用**无外部协调服务（Zero-Coordination）的单写多读架构**：

- **WAL 与 SST 全量落对象存储**：不依赖本地持久化盘；计算节点完全无状态，本地磁盘/内存仅作可丢弃的读缓存（`foyer`）。
- **单写多读 + 异步角色拆分**：Writer（`Db`）、无状态只读客户端（`DbReader`）、压缩器（`CompactorBuilder`）和垃圾回收器（`GarbageCollectorBuilder`）可以合并在单进程，也可拆分为完全独立的无状态进程。
- **零外部元数据服务**：没有 ZooKeeper / etcd / Postgres Catalog；所有状态提交、Epoch 递增与 Writer Fencing 均通过对象存储的**原子条件创建（`PutMode::Create` / `put_if_not_exists`）**完成。

## 2. 源码锚定的五大核心机制

### 2.1 基于对象存储的事务性元数据（`slatedb-txn-obj`）

核心实现在 `slatedb-txn-obj/src/object_store.rs` 中的 `ObjectStoreSequencedStorageProtocol<T>`：

- **顺序编号不可变对象**：每个元数据版本以 20 位零填充十进制 ID 命名，例如 `manifest/00000000000000000001.manifest`、`compactions/00000000000000000001.compactions`（`path_for()`）。
- **乐观并发 CAS（`PutMode::Create`）**：每次更新必须写入 `current_id + 1` 并传递 `PutMode::Create`。若对象存储已存在同 ID 文件，底层返回 `object_store::Error::AlreadyExists`（或 `Precondition`），协议层将其转换为 `TransactionalObjectError::ObjectVersionExists`，由调用方刷新最新版本后重试。
- **不可变 CAS 的取舍**：相比在单一路径上做 `If-Match` 原地覆盖，顺序文件名 + `PutMode::Create` 只需对象存储支持“禁止覆盖创建”，语义最简单、支持保留历史版本供 Checkpoint 与时间点恢复，但代价是目录对象数会持续增长，需要后台 GC 清理过期版本。

### 2.2 Epoch 与双层 Writer Fencing（`slatedb/src/fence.rs`）

防止网络分区下的“僵尸写者（Zombie Writer）”覆盖新写者状态，依赖 `WriterFencer::fence()`（`slatedb/src/fence.rs`）的两阶段隔离：

1. **Manifest Epoch Fencing**：新 Writer 启动时调用 `FenceableManifest::init_writer()`，基于当前最新 Manifest 递增 `writer_epoch` 并通过 `PutMode::Create` 写入下一个 Manifest ID。一旦落盘成功，旧 Writer 后续任何试图推进 Manifest 的 `PutMode::Create` 都会因版本冲突或 Epoch 过旧而失败。
2. **WAL Fencing**：随后调用 `wal_writer_init.fence_and_init(&mut manifest)`，通过写入零字节哨兵 WAL 文件（`SlateDBError::EmptySSTable` 注释明确指出：`A WAL fence is a zero-byte object`）占住下一个 WAL 序号。僵尸写者在未察觉 Manifest 变化前试图刷下一个 WAL 段时，会直接撞上 `AlreadyExists`，从而立即进入 `ErrorKind::Closed(CloseReason::Fenced)`（见 `slatedb/src/error.rs`）。

### 2.3 写入路径、Group Commit 与刷盘（`slatedb/src/db.rs` & `config.rs`）

- 每次 `db.put` / `db.write(WriteBatch)` 先进入内存 MemTable 与 WAL 缓冲，**在 `v0.18.1` 中返回 `WriteHandle`（见 `slatedb/src/db.rs::WriteHandle`）**：调用方若不显式调用 `handle.await_durable().await?`，写入仅落入内存缓冲；显式等待 `await_durable()` 时，会等待包含该 `seqnum` 的 WAL Group Commit 对象完成远端 `PUT`。按 `Settings::flush_interval`（默认 `100ms`）合并为一个 WAL 对象批量 `PUT` 到对象存储。
- **延迟 vs OSS API 账单的直接权衡**：对象存储每次 `PUT` 有数十至上百毫秒 RTT 且按次计费。增大 `flush_interval` 可将并发写合并进更少的 WAL `PUT` 中，显著降低单次操作的 `PUT` 请求次数，代价是单请求持久化等待时间拉长。
- 当 MemTable 达到 `l0_sst_size_bytes`（默认 64 MiB）或显式调用 `flush_with_options(FlushOptions { flush_type: FlushType::MemTable })` 时，MemTable 编码为 L0 SST（ULID 命名）写入 `compacted/` 并推进 Manifest。

### 2.4 多级缓存架构（`slatedb/src/db_cache/`）

`DbCache` trait（`slatedb/src/db_cache/mod.rs`）统一缓存 SST Data Block、Index 与 Filter（如 Bloom Filter），内置三种实现：

- `FoyerCache`（`db_cache/foyer.rs`，默认启用）：基于 RisingWave 开源的 `foyer` 内存缓存，按 `CachedEntry::size()` 精确计重（custom weighter），并通过 `CacheLoader` 实现并发请求去重（single-flight），避免缓存击穿放大对象存储 `GET`。
- `FoyerHybridCache`（`db_cache/foyer_hybrid.rs`）：内存 + 本地临时 NVMe 盘两级混合缓存，计算节点重启后丢弃即可，专为存算分离读热点设计。
- `MokaCache`（`db_cache/moka.rs`）：可选轻量纯内存缓存实现。

### 2.5 无状态只读客户端与观测（`db_reader.rs` & `instrumented_object_store.rs`）

- `DbReader` 支持三种模式（`DbReaderMode`）：
  - `ManagedCheckpoint`（默认）：自动创建并定期续期 Checkpoint，防止后台 GC 删除正在读取的 SST；
  - `Checkpoint(Uuid)`：固定绑定到历史 Detached Checkpoint，用于强一致快照回放或离线分析；
  - `FollowLatest`：零对象存储写入，仅跟随最新 Manifest（适合只读只查或镜像场景）。
- `InstrumentedObjectStore`（`slatedb/src/instrumented_object_store.rs`）位于 `RetryingObjectStore` 之下，按 `(ObjectStoreComponent, ObjectStoreType)` 双维度统计每次重试级别的真实存储请求与耗时。

## 3. 阿里云 OSS 适配的协议实证与硬约束

在阿里云 OSS（`oss-cn-beijing.aliyuncs.com`）上的实测暴露出两条必须遵守的工程边界（完整复现见 [labs/slatedb-oss](../../../labs/slatedb-oss/README.md)）：

| 协议路径 / 桶配置 | `PutMode::Create` 实际行为 | 结论 |
| --- | --- | --- |
| `object_store` S3 驱动直连 OSS（发 `If-None-Match: *`） | OSS 返回 **`400 NotImplemented`**（`<Header>If-None-Match</Header>`） | **不可用**：首个 Manifest 即报错 |
| OpenDAL OSS 驱动 + **已开启/曾开启版本控制**的 Bucket | OSS 忽略 `x-oss-forbid-overwrite: true`，重复写返回 `200 OK` 生成新版本 | **高危禁用**：静默破坏 Writer Fencing |
| OpenDAL OSS 驱动 + **从未开启版本控制**的 Bucket | 首次 `200 OK`，重复写严格返回 **`409 FileAlreadyExists`** → `AlreadyExists` | **生产可行**：完整支撑 CAS 与 Fencing |

> **关键工程守卫**：由于阿里云 OSS 开启版本控制后无法退回“未开通”（只能 `Suspended`，仍使 `x-oss-forbid-overwrite` 失效），生产服务必须在打开 `Db` 前运行一次轻量 `PutMode::Create` 重复写探针（见 `labs/slatedb-oss/src/store.rs::ensure_cas_supported`），实现启动期 Fail-Fast。

### 3.1 `xlab-slatedb-dev`（北京公网直连）实测基准摘录

- **Group Commit（24 次 `await_durable()` 写入，8 并发，256B value）**：全部压缩为 **3 次 OSS PUT（7,210 B）**；`flush_interval=50ms` 吞吐 `107.8 ops/s`（P50 `62.1ms`），`200ms` 降至 `50.1 ops/s`（P50 `174.3ms`），`500ms` 降至 `16.9 ops/s`（P50 `507.1ms`）。
- **Foyer 缓存收益（12 次 L0 SST 点查）**：关闭缓存时第 2 轮耗时 `1136.3ms`（P50 `93.0ms`、24 次 OSS GET / `40,860 B`）；开启 `FoyerCache` 后第 2 轮耗时 **`2.2ms`**（P50 `0.13ms`、**0 次 OSS GET**），读延迟下降两个数量级以上。
- **同桶 DuckDB + ZSTD Parquet 对照（10,000 行）**：单次批量写 `263.85ms`，点查 P50 `47.96ms`，全量 `GROUP BY` 聚合 `51.68ms`。

### 3.1 阿里云 OSS（北京公网）实测量化数据

在 `xlab-slatedb-dev` 上使用 `CountingObjectStore` 实测（`256B` value，结束均自动清空）：

- **Group Commit（`WriteHandle::await_durable()`，`24` 次写入，`8` 并发）**：8 路并发将 24 次持久化写合并为 **3–4 次 OSS PUT**（8x 写请求合并）；`flush_interval=50ms` 时 `p50=64.45ms`、`117.79 ops/s`，`200ms` 时 `p50=323.98ms`，`500ms` 时 `p50=506.35ms`——说明同步持久化场景下 `flush_interval` 直接构成延迟下界，而并发度决定单次 PUT 的吞吐摊薄比例。
- **Foyer 缓存收益（12 次 SST 点查）**：
  - 关闭缓存（`round2_warm`）：总耗时 `986.38ms`，`p50=81.96ms`，产生 **`24` 次 OSS GET（`40,860 B`）**（每次点查触发 Index + Data Block 两次读）。
  - 开启 `FoyerCache`（`round1_cold` → `round2_warm`）：首轮 `94.00ms`（`4` 次 GET，`3,405 B`），预热后降至 **`0.40ms`（`p50=0.03ms`，`0` 次 OSS GET）**，读延迟下降超 2,400 倍且消除热键 OSS GET 费用。
- **同桶 DuckDB + ZSTD Parquet 对照（10,000 行）**：批量写 1 个 Parquet 对象仅 `263.85ms`，全量 `GROUP BY` 聚合扫描 `51.68ms`，但单点查询 `p50=47.96ms`——直观印证了行存 LSM KV（SlateDB + Foyer）与列存湖仓（DuckDB + Parquet）在点查 vs 扫描上的互补边界。

## 4. 阿里云 OSS 同桶实测与同类存算分离引擎对比

在同一个北京非版本控制桶 `xlab-slatedb-dev`（公网直连）上的实测对比：

| 引擎 / 模式 | 工作负载 | 实测耗时 / P50 | 远端 OSS 请求量 |
| --- | --- | --- | --- |
| SlateDB（`flush=50ms`，8 并发 `await_durable`） | 24 次 256B 持久化点写 | `222.6ms`（P50 `62.1ms`） | `3` 次 `PUT`（8× 合并） |
| SlateDB（禁用缓存，`round2_warm`） | 12 次 SST 点查 | `1136.3ms`（P50 `93.0ms`） | `24` 次 `GET`（`40,860 B`） |
| SlateDB（`FoyerCache`，`round2_warm`） | 12 次 SST 点查 | **`2.16ms`（P50 `0.13ms`）** | **`0` 次 `GET`**（提速 526×） |
| DuckDB + Parquet（ZSTD，同桶） | 10,000 行批量列写 | `263.85ms` | `1` 次 `PUT` |
| DuckDB + Parquet（同桶） | 5 次点查 / 全表 `GROUP BY` | 点查 P50 `47.96ms` / 聚合 `51.68ms` | Range Get 读列块 |

| 维度 | SlateDB（行存 LSM KV） | DuckDB + Parquet / DuckLake（列存湖仓） | Hummock / JuiceFS（外置元数据） |
| --- | --- | --- | --- |
| **元数据协调** | 无外部服务，纯对象存储 `PutMode::Create` | 外部 SQL Catalog（PG/SQLite/DuckDB） | 外部 Meta Store（etcd/PG/Redis） |
| **阿里云 OSS 版本控制桶** | **不兼容**（必须新建未开版本控制桶） | **兼容**（只写不可变 Parquet） | **兼容**（只写不可变对象） |
| **优势负载** | 低延迟点查、短范围扫描、高频增量更新、秒级 Clone | 批量列式写入、全表扫描与聚合分析 | 分布式大状态流计算 / POSIX 通用挂载 |
| **主要开销** | 写放大受 `flush_interval` 制约；无缓存时点查放大受 SST 索引/块读影响 | 单行点查/高频小事务成本高 | 多维护一套有状态元数据服务 |

## 5. 进一步改进与迁移方向

1. **云上内网部署**：将计算节点与 OSS Bucket 置于同一地域，使用 `*-internal.aliyuncs.com` 内网 Endpoint 消除公网 RTT 与下行流量费。
2. **写合并 + `FoyerHybridCache`**：在线业务配合本地临时 NVMe 开启混合缓存，结合可容忍延迟调优 `flush_interval` 压降 OSS `PUT` 费用。
3. **跨语言复用模式**：Python / TypeScript / Go 业务不建议各进程直连 OSS 争抢单写锁，推荐复用 `labs/slatedb-oss` 的薄 Rust HTTP/gRPC KV 服务形态，让单 Writer 独占热缓存与 Group Commit 批次。
