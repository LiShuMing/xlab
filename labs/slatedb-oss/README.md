# slatedb-oss：SlateDB + OpenDAL 阿里云 OSS 存算分离 E2E 验证

通过 **路线一（进程内直连，无 `s3s` 网关）** 将 [SlateDB](https://slatedb.io/) 直接接入阿里云 OSS：

```text
SlateDB (0.18.1)
  └─▶ object_store_opendal (0.60.5)   # PutMode::Create <-> if_not_exists(true)
        └─▶ opendal::services::Oss (0.59.5)   # x-oss-forbid-overwrite: true
              └─▶ Aliyun OSS (未开启版本控制的 Bucket，如 xlab-slatedb-dev)
```

## 前置条件

1. **Rust 工具链**：Rust 1.91+（`cargo`、`clippy`、`rustfmt`）。
2. **阿里云 OSS Bucket 硬约束**：
   - **版本控制（Versioning）必须保持“未开通”**（一旦开启过，哪怕后续暂停，`x-oss-forbid-overwrite: true` 都会被 OSS 静默忽略，导致 Writer Fencing 失效）。
   - 存储类型 `Standard`，ACL `private`，未开启 WORM 合规保留策略。
3. **环境变量**（自动优先读取进程环境变量，未设置时回退读取 `$HOME/.env`；凭证仅存于本机环境，不写入仓库）：
   - `SLATEDB_OSS_ACCESS_KEY_ID`（回退 `DB_RADAR_OSS_ACCESS_KEY_ID`）
   - `SLATEDB_OSS_ACCESS_KEY_SECRET`（回退 `DB_RADAR_OSS_ACCESS_KEY_SECRET`）
   - `SLATEDB_OSS_ENDPOINT`（回退 `DB_RADAR_OSS_ENDPOINT`，如 `oss-cn-beijing.aliyuncs.com`）
   - `SLATEDB_OSS_BUCKET`（默认 `xlab-slatedb-dev`，不会静默落到开启版本控制的旧桶）

## 运行与验证

```sh
# 1. 离线测试（使用 InMemory ObjectStore 跑通全部 6 阶段）
cargo fmt -- --check
cargo clippy --all-targets -- -D warnings
cargo test

# 2. 本地内存后端 CLI 演练（零网络）
cargo run -- --backend memory

# 3. 真实阿里云 OSS E2E 验证（默认跑完自动清理所有临时对象，零残留）
cargo run -- e2e --backend oss --bucket xlab-slatedb-dev

# 4. 真实阿里云 OSS 性能/缓存/独立 Compactor+GC 基准（输出 JSON 供 labs/lab-viewer 聚合）
cargo run -- bench --backend oss --bucket xlab-slatedb-dev --json-out .local/slatedb-oss-bench.json

# 5. 同桶 DuckDB + Parquet 横向对比（独立 compare/ 前缀，自动清理）
python3 compare/duckdb_oss_compare.py --bucket xlab-slatedb-dev --json-out .local/duckdb-oss-compare.json

# 6. 启动薄单写者 HTTP KV 服务（供 Python/TypeScript/Go 业务复用，启动期自动做 CAS 自检）
cargo run -- serve --backend oss --bucket xlab-slatedb-dev --prefix kv-service/demo --bind 127.0.0.1:8088

# 如需保留 OSS 上的 manifest/、wal/、compacted/ 文件做人工观测：
cargo run -- e2e --backend oss --bucket xlab-slatedb-dev --prefix e2e/inspect-1 --keep-data
```

## 6 阶段 E2E 验收覆盖

| 阶段 | 验证目标 | 关键断言 |
| --- | --- | --- |
| 1 | `ObjectStore` 层 `PutMode::Create` 原子 CAS | 首次写入成功，同名重复写严格返回 `AlreadyExists`，原对象内容未被篡改（提前拦截开了 Versioning 的桶） |
| 2 | SlateDB 基础 KV CRUD + 批量 + 扫描 + 刷盘 | `put`/`get`/`delete`/`WriteBatch`/`scan`/`seek` + WAL 与 MemTable L0 SST 刷盘 |
| 3 | 冷重启恢复与 OSS 对象布局 | 确认 `manifest/` 与 `compacted/` 目录已落盘，冷重启后键值与删除墓碑完整恢复 |
| 4 | 无状态 `DbReader`（单写多读存算分离） | `DbReader(FollowLatest)` 独立读取最新已提交状态 |
| 5 | **Writer Fencing（防脑裂）** | Writer B 接管后，旧 Writer A 再次写入刷盘必须返回 `ErrorKind::Closed(CloseReason::Fenced)`，且不污染新数据 |
| 6 | Detached Checkpoint 与历史快照隔离 | 创建 Checkpoint 后修改主库，绑定 Checkpoint 的 Reader 仍读旧值，Latest Reader 读新值 |

## 架构与迁移思考（从 Lab 到可复用/生产组件）

当这个 E2E 验证跑通后，如果计划将其迁移为独立项目或现有系统的存算分离存储层（如迁往 `vela`、`lyra` 或独立微服务），可以按三层渐进迁移：

1. **存储适配层独立为纯库 crate（`oss-object-store` / 复用 `src/config.rs` + `src/store.rs`）**
   - 保持上层只依赖 `Arc<dyn object_store::ObjectStore>`，业务代码与 SlateDB 完全不感知 OSS vs S3 vs 本地内存。
   - **启动自检（Fail-Fast Guard）**：在生产服务初始化时保留 Stage 1 的轻量 CAS 探针（或启动期检查 `GetBucketVersioning`），防止运维误开版本控制导致静默脑裂。
   - 接入 OpenDAL 的 `RetryLayer` / `LoggingLayer` / `MetricsLayer`（注意：对 `if_not_exists` 的不确定超时重试要遵循 SlateDB 自身的 `RetryingObjectStore` 语义，避免双重重试掩盖 `AlreadyExists`）。
2. **本地缓存与内网拓扑（决定真实生产延迟与 OSS 账单）**
   - 计算节点部署在与 Bucket 同地域的 ECS/ACK 上，Endpoint 切换为内网域名（`oss-cn-beijing-internal.aliyuncs.com`），去掉公网 RTT 与下行流量费。
   - 启用 SlateDB 内置的 `foyer` 混合缓存（内存 + 本地临时 NVMe 盘）缓存热门 SST Block 与 Filter，将读请求挡在本地；按业务延迟容忍度调大 `flush_interval`（Group Commit）降低 `PUT` 请求数。
   - 将 Compactor 与 Garbage Collector 拆分为独立无状态任务/Pod（参考 `slatedb` 的 `CompactorBuilder` / `GarbageCollectorBuilder`），避免后台合并抖动影响在线写入 P99。
3. **跨语言与演进路径**
   - **纯 Rust 业务**：直接内嵌 `slatedb + object_store_opendal + opendal(oss)`（本 lab 架构，零额外进程）。
   - **Python / Go / Java 业务**：两种选择：
     - **服务化封装（推荐）**：用本 lab 的 Rust 底座外包一层 gRPC/HTTP KV 服务（天然保留单 Writer + 本地 `foyer` 缓存，多客户端共享同一个热缓存和 Group Commit 批次，OSS API 成本远低于每个客户端直连）。
     - **单进程多语言绑定**：将 `OpendalStore` 编进自定义 UniFFI/PyO3 扩展，或在多进程隔离场景下搭配未开版本控制桶的 `s3s + opendal(oss)` Sidecar。
   - **仓库归属建议**：本目录保留在 `xlab/labs/slatedb-oss/` 作为可复现的机制实验与回归探针；一旦演进为正式数据库子系统，按仓库路由迁入 `vela/storage/`（存储引擎主线）或业务仓库的独立 storage crate，并同步更新 `PROJECTS.md`。

## 实测记录

- **验收环境**：macOS (arm64) / Rust 1.100.1 / `slatedb 0.18.1` / `object_store_opendal 0.60.5` / `opendal 0.59.5` / `object_store 0.14.2`。
- **离线验证**：`cargo test`（6/6 通过，含 `InMemory` 6 阶段 E2E、`bench`、Axum HTTP KV `serve`）、`cargo clippy --all-targets -- -D warnings`、`cargo fmt -- --check`、`ruff check compare/duckdb_oss_compare.py` 全部通过。
- **阿里云 OSS 6 阶段 E2E（`xlab-slatedb-dev` @ `oss-cn-beijing.aliyuncs.com`，公网直连）**：6 阶段全部通过（总计 42 个对象、12,293 字节：`manifest/` 19、`compactions/` 11、`wal/` 9、`compacted/` 3），Stage 5 成功触发 `ErrorKind::Closed(CloseReason::Fenced)` 拦截僵尸写者，自动清理 42/42 对象。
- **阿里云 OSS Bench（`xlab-slatedb-dev`，公网直连，自动清理 51/51 对象）**：
  - **Group Commit（24 次 `WriteHandle::await_durable()`，8 并发，256B value）**：合并为 **3 次 OSS PUT（7,210 B）**；`flush=50ms` `107.8 ops/s`（P50 `62.1ms`），`200ms` `50.1 ops/s`（P50 `174.3ms`），`500ms` `16.9 ops/s`（P50 `507.1ms`）。
  - **Foyer 缓存 vs 无缓存点查（12 次读 L0 SST）**：无缓存第 2 轮 `1136.3ms`（P50 `93.0ms`，24 次 OSS GET / `40,860 B`）；开启 `FoyerCache` 后第 2 轮降至 **`2.2ms`**（P50 `0.13ms`，**0 次 OSS GET**）。
  - **独立 Compactor + GC**：`l0_flushes=3`，`compactor_ok=true`，`gc_ok=true`（`3613.7ms`）。
- **同桶 DuckDB + ZSTD Parquet 对照（10,000 行，自动清理 1/1 对象）**：批量写 `263.85ms`，点查 P50 `47.96ms`，全量 `GROUP BY` 聚合扫描 `51.68ms`。
- **TypeScript 报告聚合**：已用 `labs/lab-viewer` 将两份真实 JSON 报告聚合输出为 Markdown 与离线 HTML 对比面板。
- **阿里云 OSS 基准实测（`bench`，24 次并发持久化写 `await_durable`、`c=8`、`256B` value，结束清理 52/52 对象）**：
  - **Group Commit (`flush_interval`)**：`50ms` 下 24 次并发写合并为 `3` 次 OSS PUT（`p50=64.45ms`、`p99=80.0ms`、`117.79 ops/s`）；`200ms` 为 `4` 次 PUT（`p50=323.98ms`）；`500ms` 为 `3` 次 PUT（`p50=506.35ms`）。
  - **Foyer 缓存 vs 无缓存（12 次点查）**：无缓存第 2 轮耗时 `986.38ms`（`p50=81.96ms`、`24` 次 OSS GET、`40,860 B`）；开启 `FoyerCache` 后第 1 轮 `94.00ms`（`4` 次 GET、`3,405 B`），第 2 轮降至 **`0.40ms`（`p50=0.03ms`、`0` 次 OSS GET）**。
  - **独立 Compactor + GC**：3 次 L0 刷盘后独立启动并优雅停止 `CompactorBuilder` 与 `GarbageCollectorBuilder`，均返回 `ok`（总耗时 `3646.43ms`）。
- **同桶 DuckDB + Parquet 实测（`xlab-slatedb-dev`，`10,000` 行 ZSTD Parquet，结束清理 1/1 对象）**：批量写入 `263.85ms`，点查 `p50=47.96ms`（`mean=62.21ms`），全量 `GROUP BY` 聚合扫描 `51.68ms`。
