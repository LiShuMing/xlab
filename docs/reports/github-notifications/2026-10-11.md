# GitHub 未读通知摘要 2026-10-11

> 两批通知：截至 11:06 共 4997 条（接近 API 上限，更早的可能不全），11:06–15:58 新增 94 条。均已标为已读。

## 需要我处理（StarRocks @我）
- [#79981](https://github.com/StarRocks/starrocks/pull/79981) 查询队列槽位按各自截止时间过期
- issue [#68479](https://github.com/StarRocks/starrocks/issues/68479) 嵌套分区 MV INACTIVE→ACTIVE 后无法重新激活/重建；修复 PR [#68798](https://github.com/StarRocks/starrocks/pull/68798)

## 各仓库未读数（第一批）
ClickHouse 2337 · DuckDB 595 · StarRocks 429 · Doris 408 · DataFusion 365 · Velox 288 · Spark 243 · Trino 210 · ClickBench 122

## ClickHouse
- 发版：v26.9.15.5-stable、v26.8.23.6-lts、v26.7.26.8-stable、v26.3.47.6-lts
- 🔴 [#125116](https://github.com/ClickHouse/ClickHouse/issues/125116) AllocationQueue eviction 自死锁；复现 [#125127](https://github.com/ClickHouse/ClickHouse/pull/125127)
- 🔴 [#112035](https://github.com/ClickHouse/ClickHouse/issues/112035) LEFT JOIN 右表 indexHint 导致静默错误结果
- 🔴 [#125136](https://github.com/ClickHouse/ClickHouse/issues/125136) 关闭时等待统计刷新卡死；修复 [#125165](https://github.com/ClickHouse/ClickHouse/pull/125165)
- 🔴 [#125158](https://github.com/ClickHouse/ClickHouse/pull/125158) 排序 spill 后 heap-use-after-free
- [#111414](https://github.com/ClickHouse/ClickHouse/pull/111414) part 元数据重写持久化，防断电丢数据
- [#124763](https://github.com/ClickHouse/ClickHouse/pull/124763) 支持部分 Trino SQL 方言
- [#124320](https://github.com/ClickHouse/ClickHouse/pull/124320) 多规划器统一基数估计
- [#115580](https://github.com/ClickHouse/ClickHouse/pull/115580) 提交结果未知时不删除暂存 Iceberg 文件
- [#101796](https://github.com/ClickHouse/ClickHouse/pull/101796) 实验性 cuckoo / binary fuse filter 跳数索引

## DuckDB
- 🔴 [#26828](https://github.com/duckdb/duckdb/issues/26828) WAL 回放后首次 checkpoint 致 ART 索引丢行（1.4.0 起）
- 🔴 [#26839](https://github.com/duckdb/duckdb/issues/26839) `COPY ... ORDER BY` 写 parquet 段错误
- 🔴 [#26849](https://github.com/duckdb/duckdb/issues/26849) postgres schema 并发修改返回错误结果
- [#26793](https://github.com/duckdb/duckdb/issues/26793) 嵌套 join 丢等值条件变成笛卡尔积

## StarRocks
- [#76228](https://github.com/StarRocks/starrocks/pull/76228) Iceberg v3 删除向量
- [#79483](https://github.com/StarRocks/starrocks/pull/79483) Paimon 全局索引规划框架
- [#76468](https://github.com/StarRocks/starrocks/pull/76468) nestloop join 全局 runtime filter

## Doris
- [#68884](https://github.com/apache/doris/pull/68884) 4.1.5 发版
- [#68883](https://github.com/apache/doris/pull/68883) Arrow Flight / Variant / VARBINARY 修复移植
- [#68032](https://github.com/apache/doris/pull/68032) cloud 模式 spill 到对象存储
- [#68814](https://github.com/apache/doris/pull/68814) 新增 typeof 函数

## DataFusion
- 🔴 [#26082](https://github.com/apache/datafusion/issues/26082) `IN` 列表含 `CASE` 结果错误
- [#22248](https://github.com/apache/datafusion/pull/22248) 区间算术扩展到 UDF
- [#26123](https://github.com/apache/datafusion/pull/26123) JoinSelection 跳过带动态过滤的 HashJoin

## Velox
- [#19222](https://github.com/facebookincubator/velox/pull/19222) join 处理 probe 提前关闭
- [#18467](https://github.com/facebookincubator/velox/pull/18467) Parquet size statistics
- [#19120](https://github.com/facebookincubator/velox/issues/19120) 提案：行格式 spill
- [#19405](https://github.com/facebookincubator/velox/pull/19405) IVF RaBitQ FastScan

## Spark
- [#59313](https://github.com/apache/spark/pull/59313) Rust/C++ 原生数据源
- [#59027](https://github.com/apache/spark/pull/59027) 范围谓词 range join
- [#59353](https://github.com/apache/spark/pull/59353) 修复 CrossValidatorModel.load 子模型错误

## Trino
- Trino 484 发版说明 [#31411](https://github.com/trinodb/trino/pull/31411)
- 🔴 [#31543](https://github.com/trinodb/trino/pull/31543) 带时区 timestamp(p>3) date_diff 错误
- [#27251](https://github.com/trinodb/trino/pull/27251) Elasticsearch TopN 和聚合下推
