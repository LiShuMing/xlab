# GitHub 未读通知摘要 2026-10-13

> 截至 08:55（UTC+8 / fetch_start 2026-10-13T00:55:42Z）共 1888 条未读。无 @我 / review / assignment。**未**标记为已读。

## 各仓库未读数
ClickHouse 857 · DuckDB 309 · StarRocks 189 · Doris 165 · Spark 102 · DataFusion 91 · Velox 78 · Trino 65 · ClickBench 32

## ClickHouse（857）
- 发版：[v26.9.17.8-stable](https://github.com/ClickHouse/ClickHouse/releases/tag/v26.9.17.8-stable)、[v26.8.25.14-lts](https://github.com/ClickHouse/ClickHouse/releases/tag/v26.8.25.14-lts)、[v26.7.28.6-stable](https://github.com/ClickHouse/ClickHouse/releases/tag/v26.7.28.6-stable)、[v26.3.49.3-lts](https://github.com/ClickHouse/ClickHouse/releases/tag/v26.3.49.3-lts)
- 🔴 [#125399](https://github.com/ClickHouse/ClickHouse/issues/125399) 旧版 26.3 往新版写过的 Iceberg 表再 INSERT 会损坏 manifest list，表不可读
- 🔴 [#125323](https://github.com/ClickHouse/ClickHouse/issues/125323) 叠在分片 RIGHT/FULL hash join 上的 join 结果错误
- 🔴 [#106125](https://github.com/ClickHouse/ClickHouse/issues/106125) SummingMergeTree FINAL 在 read-in-order + 列裁剪时丢掉求和列为 0 的行
- 🔴 [#120199](https://github.com/ClickHouse/ClickHouse/issues/120199) / 修复 [#125494](https://github.com/ClickHouse/ClickHouse/pull/125494) NATS 直查在连接被替换时 segfault
- 🔴 [#125457](https://github.com/ClickHouse/ClickHouse/issues/125457) / 修复 [#125505](https://github.com/ClickHouse/ClickHouse/pull/125505) AvroConfluent 读 Avro map→`Map(DateTime, String)` SIGSEGV
- 🔴 [#116032](https://github.com/ClickHouse/ClickHouse/issues/116032) CapnProto import 跨注释丢失，深 schema 仍 SIGSEGV
- 🔴 [#125401](https://github.com/ClickHouse/ClickHouse/pull/125401) fix：`merge`/`Merge`/`Buffer` 读 data lake 表漏掉较新 commit 的行
- 🔴 [#125495](https://github.com/ClickHouse/ClickHouse/pull/125495) Fix：客户端标量覆盖 row-policy 子查询导致策略旁路
- 🔴 [#120407](https://github.com/ClickHouse/ClickHouse/pull/120407) [SECURITY] 遮盖 HTTP URI 中嵌入的凭证
- 🔴 [#125090](https://github.com/ClickHouse/ClickHouse/pull/125090) 对象存储 reader 创建失败时 read buffer use-after-free
- 🔴 [#125105](https://github.com/ClickHouse/ClickHouse/pull/125105) RabbitMQ 重连后消息插入两次；[#125076](https://github.com/ClickHouse/ClickHouse/pull/125076) Kafka2 分区 shuffle 内存泄漏
- 🔴 [#122094](https://github.com/ClickHouse/ClickHouse/pull/122094) 同名 skip index 删再建后结果错误；[#112857](https://github.com/ClickHouse/ClickHouse/pull/112857) lazy FINAL 丢掉可空主键 NULL 行
- 🔴 [#125412](https://github.com/ClickHouse/ClickHouse/pull/125412) `count()` 在 exact count 优化后再读 projection 会双计
- [#125422](https://github.com/ClickHouse/ClickHouse/pull/125422) Iceberg truncate 分区负整数过滤（≤26.8 写出）；[#125439](https://github.com/ClickHouse/ClickHouse/pull/125439) schema 变更前 tuple 元素读取
- [#125497](https://github.com/ClickHouse/ClickHouse/pull/125497) 拒绝 RFC 2047 解码为 CR/LF/NUL 的 HTTP 头；[#117738](https://github.com/ClickHouse/ClickHouse/pull/117738) 全局内存 tracker 钉在旧峰值
- [#124763](https://github.com/ClickHouse/ClickHouse/pull/124763) 支持部分 Trino SQL 方言；[#124702](https://github.com/ClickHouse/ClickHouse/pull/124702) 加速懒复制 JOIN 列上的 ORDER BY；[#125445](https://github.com/ClickHouse/ClickHouse/pull/125445) 嵌套 ARRAY JOIN 过滤优化
- [#117704](https://github.com/ClickHouse/ClickHouse/pull/117704) 可执行 UDF 共享内存接口；[#125528](https://github.com/ClickHouse/ClickHouse/pull/125528) 本地 Parquet 用缓存 footer 统计剪枝

## DuckDB（309）
- 🔴 [#25702](https://github.com/duckdb/duckdb/issues/25702) hash join build 侧 spill 到磁盘时静默丢行
- 🔴 [#26803](https://github.com/duckdb/duckdb/issues/26803) Parquet 统计静默损坏
- 🔴 [#26881](https://github.com/duckdb/duckdb/issues/26881) dsdgen 小 fractional scale 时 segfault / 死挂
- 🔴 [#26911](https://github.com/duckdb/duckdb/issues/26911) FULL OUTER + LEFT + ORDER BY 触发 Dict-surviving hash join InternalException
- 🔴 [#26984](https://github.com/duckdb/duckdb/issues/26984) DROP 外键父表后 Stale BlockHandle，overflow 字符串读错（1.3.2–1.4.5）
- 🔴 [#26441](https://github.com/duckdb/duckdb/issues/26441) 有序 list 聚合 OOM 时析构 abort 进程
- 🔴 [#26668](https://github.com/duckdb/duckdb/pull/26668) / [#26674](https://github.com/duckdb/duckdb/pull/26674) 持久化列 / Parquet VARIANT 不一致时抛 DataCorruptionException
- [#26873](https://github.com/duckdb/duckdb/pull/26873) 并行 NDJSON 扫描丢失跨 chunk 未终止末行；[#25540](https://github.com/duckdb/duckdb/pull/25540) ORDER BY 把 -0.0 变成 0.0
- [#24667](https://github.com/duckdb/duckdb/pull/24667) MERGE RETURNING 在 WHEN NOT MATCHED BY SOURCE UPDATE 返回全零行
- [#26955](https://github.com/duckdb/duckdb/pull/26955) DECIMAL 宽至 255 位；[#26967](https://github.com/duckdb/duckdb/pull/26967) 多核瓶颈/回归修复；[#26960](https://github.com/duckdb/duckdb/pull/26960) Parquet 扫描三项回归

## StarRocks（189）
- 🔴 [#77754](https://github.com/StarRocks/starrocks/pull/77754) 与 ALTER TABLE OPTIMIZE 并发 load 静默丢数据
- 🔴 [#80156](https://github.com/StarRocks/starrocks/issues/80156) 4.0.5 BinaryColumnBase::append SIGSEGV；[#71283](https://github.com/StarRocks/starrocks/issues/71283) ColumnReader 析构 SIGSEGV
- 🔴 [#80519](https://github.com/StarRocks/starrocks/issues/80519) 4.0.7 BE pipeline 调度停滞（driver_schedule_count=0），整集群阻塞
- 🔴 [#60549](https://github.com/StarRocks/starrocks/issues/60549) CVE-2025-52999；[#80439](https://github.com/StarRocks/starrocks/pull/80439) / [#80458](https://github.com/StarRocks/starrocks/issues/80458) 预置 pprof 工具链 CVE，bump release/20261012
- 🔴 [#80492](https://github.com/StarRocks/starrocks/pull/80492) / [#80444](https://github.com/StarRocks/starrocks/pull/80444) / [#80515](https://github.com/StarRocks/starrocks/pull/80515) 凭证与敏感 query 参数不再明文进 fe.log / HTTP URI
- [#80472](https://github.com/StarRocks/starrocks/pull/80472) PK compaction row source 溢出；[#80488](https://github.com/StarRocks/starrocks/pull/80488) hash join 分区超 32-bit offset 后保持分区
- [#80138](https://github.com/StarRocks/starrocks/pull/80138) lake column-mode 更新按 source segment 记账；[#79483](https://github.com/StarRocks/starrocks/pull/79483) Paimon 全局索引规划
- [#74661](https://github.com/StarRocks/starrocks/pull/74661)–[#74664](https://github.com/StarRocks/starrocks/pull/74664) Lance 原生 Rust reader / 扫描规划（opt-in）

## Doris（165）
- 🔴 [#67031](https://github.com/apache/doris/issues/67031) PipelineTask::set_running 单次 compare_exchange_weak，aarch64 伪失败可致双 worker 同跑一 task
- 🔴 [#67547](https://github.com/apache/doris/pull/67547) dbt-doris 强制 use_pure=True，防静默损坏
- [#68970](https://github.com/apache/doris/issues/68970) Load S3 upload buffer 内存无上限；[#68972](https://github.com/apache/doris/issues/68972) CachedRemoteFileReader 驱逐块后仍直读失败
- [#68958](https://github.com/apache/doris/pull/68958) 有 delete predicate 时不强行 abort MIN/MAX；[#61829](https://github.com/apache/doris/pull/61829) 带 MV 的表备份恢复后 load 失败
- [#68499](https://github.com/apache/doris/pull/68499) SQL plan management；[#68853](https://github.com/apache/doris/pull/68853) FILE 类型；[#61963](https://github.com/apache/doris/pull/61963) Paimon insert（jni & paimon-cpp）
- [#68740](https://github.com/apache/doris/pull/68740) 磁盘健康检查 watchdog；[#68694](https://github.com/apache/doris/pull/68694) FE/BE runtime log 带 query id

## Spark（102）
- 🔴 [#59329](https://github.com/apache/spark/pull/59329) ParquetColumnVector 内存泄漏
- 🔴 [#58929](https://github.com/apache/spark/pull/58929) Structured Streaming isRepartitionBatch 缺 metadata key 会 crash
- [#59305](https://github.com/apache/spark/pull/59305) FILE Catalyst 类型 + FILE EXTERNAL DDL；[#58144](https://github.com/apache/spark/pull/58144) 重排 Window 栈减少 exchange
- [#59410](https://github.com/apache/spark/pull/59410) / [#58013](https://github.com/apache/spark/pull/58013) SPJ 在 join key ⊂ partition key 时的 originalPartitionValues / runtime filter
- [#58506](https://github.com/apache/spark/pull/58506) 条件为 false 的 FULL JOIN 改写为 UNION ALL；[#58034](https://github.com/apache/spark/pull/58034) ANSI JSON_OBJECT

## DataFusion（91）
- 🔴 [#26234](https://github.com/apache/datafusion/issues/26234) 相关子查询混淆两关系同名列 → 错误结果
- 🔴 [#26103](https://github.com/apache/datafusion/issues/26103) Parquet schema 推断把部分文件缺失列标 NOT NULL，表不可读
- [#26247](https://github.com/apache/datafusion/issues/26247) / 修复 [#26248](https://github.com/apache/datafusion/pull/26248) RunEndEncoded 上 MIN/MAX 内部错误
- [#26183](https://github.com/apache/datafusion/issues/26183) / [#26184](https://github.com/apache/datafusion/pull/26184) 带 FILTER 的聚合 CSE 仍对拒绝行求参
- [#26223](https://github.com/apache/datafusion/issues/26223) `SUM(x+c)`→`SUM(x)+c*COUNT(x)` 改写对浮点结果不同；[#26035](https://github.com/apache/datafusion/pull/26035) Substrait 保留 scan offset/limit
- [#24768](https://github.com/apache/datafusion/issues/24768) EPIC：可 spill 的 Hash Join；[#26132](https://github.com/apache/datafusion/pull/26132) 跨 AND/OR 简化矛盾区间谓词

## Velox（78）
- [#18336](https://github.com/facebookincubator/velox/issues/18336) cudf doClose 未同步 in-flight 读就释放 GPU 状态
- [#19060](https://github.com/facebookincubator/velox/pull/19060) decimal pushdown 字面量对齐 Parquet 存储；[#19343](https://github.com/facebookincubator/velox/pull/19343) 自定义比较类型表达式走 CPU
- [#19516](https://github.com/facebookincubator/velox/pull/19516) Iceberg identity 分区用 split 值；[#19520](https://github.com/facebookincubator/velox/pull/19520) nimble 索引行/批迭代器
- [#19540](https://github.com/facebookincubator/velox/pull/19540) qdigest 宽 digest 节点数溢出；[#19300](https://github.com/facebookincubator/velox/pull/19300) Presto mod 不再收窄 long 操作数

## Trino（65）
- 🔴 [#31221](https://github.com/trinodb/trino/pull/31221) Fix SalesforceBasicAuthenticator XML 解析 XXE
- 🔴 [#31543](https://github.com/trinodb/trino/pull/31543) `date_diff` 对 timestamp(p) with time zone 且 p>3 结果错误
- 🔴 [#31544](https://github.com/trinodb/trino/pull/31544) Iceberg MERGE 可串行隔离；[#31554](https://github.com/trinodb/trino/pull/31554) Slice 字节访问忽略 offset
- [#31567](https://github.com/trinodb/trino/pull/31567) timestamp 舍入近边界溢出；[#31350](https://github.com/trinodb/trino/pull/31350) 更高 scale 存储的 decimal 读取
- [#31245](https://github.com/trinodb/trino/pull/31245) Iceberg `$partition` 改为 row 类型；[#31378](https://github.com/trinodb/trino/pull/31378) Iceberg REST S3 remote signing

## ClickBench（32）
- [#2540](https://github.com/ClickHouse/ClickBench/pull/2540) / [#2541](https://github.com/ClickHouse/ClickBench/pull/2541) clickhouse-parquet（含 partitioned）自动结果更新
- [#2444](https://github.com/ClickHouse/ClickBench/pull/2444) Druid historical Guice 启动与 COUNT(*) 解析；[#2548](https://github.com/ClickHouse/ClickBench/pull/2548) rayforce v2.11.5 基准
