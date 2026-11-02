# GitHub 未读通知摘要 2026-10-12

> 截至 08:55（UTC+8 / fetch_start 2026-10-12T00:55:45Z）共 35 条未读。无 @我 / review / assignment。已标为已读。

## 各仓库未读数
ClickHouse 27 · Doris 3 · Spark 2 · Velox 1 · DuckDB 1 · StarRocks 1

## ClickHouse（27）
- 发版：[#116064](https://github.com/ClickHouse/ClickHouse/pull/116064) Release PR for branch 26.8
- 🔴 [#124788](https://github.com/ClickHouse/ClickHouse/issues/124788) File TopK cache 对 Tuple 排序键中 NULL 判定错序，重跑会丢行；修复 [#125288](https://github.com/ClickHouse/ClickHouse/pull/125288)
- 🔴 [#125290](https://github.com/ClickHouse/ClickHouse/issues/125290) `pointInPolygon` 拒绝坐标较大的常量多边形
- 🔴 [#125289](https://github.com/ClickHouse/ClickHouse/issues/125289) Grid `contains` 把超出 bbox 最大边的点映射进 `inner` 单元格
- [#123673](https://github.com/ClickHouse/ClickHouse/pull/123673) FileLog 在监视目录存在硬链接/符号链接时重复读同一文件
- [#109838](https://github.com/ClickHouse/ClickHouse/pull/109838) Iceberg insert 在 schema 列数不匹配时越界 abort
- [#103029](https://github.com/ClickHouse/ClickHouse/pull/103029) 过滤器依赖左表列时 not-ready Set 修复
- [#102499](https://github.com/ClickHouse/ClickHouse/pull/102499) ParquetReaderv3 支持 Shredded VARIANT
- [#125135](https://github.com/ClickHouse/ClickHouse/pull/125135) 支持 Parquet `ALP` 编码
- [#124861](https://github.com/ClickHouse/ClickHouse/pull/124861) 经 URL 读 Parquet 的 TopN 动态过滤
- [#113336](https://github.com/ClickHouse/ClickHouse/pull/113336) 无行数估计时仍把较小侧放在 hash join build 侧
- [#116175](https://github.com/ClickHouse/ClickHouse/pull/116175) 应用 patch parts 的 merge 时重算 TTL infos
- [#101039](https://github.com/ClickHouse/ClickHouse/pull/101039) 共享存储上非复制 MergeTree 的 leader 选举
- [#125280](https://github.com/ClickHouse/ClickHouse/pull/125280) consecutive-keys cache 布局，避免跨 16 字节边界的逐行存储
- [#124117](https://github.com/ClickHouse/ClickHouse/pull/124117) 大小写不敏感 UTF-8 子串搜索与 constness/尾长/行布局无关
- [#114043](https://github.com/ClickHouse/ClickHouse/pull/114043) 客户端增加完整 AI agent（`?` 命令）
- [#96886](https://github.com/ClickHouse/ClickHouse/pull/96886) 独立表达式编译改用 Analyzer 替代 ExpressionAnalyzer
- [#116222](https://github.com/ClickHouse/ClickHouse/pull/116222) HTTP body 经 ReadBuffer/WriteBuffer 读写，替代 iostream
- [#125275](https://github.com/ClickHouse/ClickHouse/pull/125275) File/URL/对象存储读在文件数 ≥ 线程数时重平衡工作

## Doris（3）
- [#62441](https://github.com/apache/doris/pull/62441) spill 目录选择 data race 与内存跟踪少报修复
- [#68921](https://github.com/apache/doris/pull/68921) 按变换后的分区值路由分区 Iceberg 写入

## Spark（2）
- [#56903](https://github.com/apache/spark/pull/56903) 默认关闭 History Server UI 日志访问（安全）
- 🔴 [#56990](https://github.com/apache/spark/issues/56990) 经 VIEW 查询时 EXPLAIN COST 输入大小估计错误

## DuckDB（1）
- 🔴 [#18259](https://github.com/duckdb/duckdb/issues/18259) 回放带 default 表达式的 ADD COLUMN 的 WAL 失败

## Velox（1）
- [#19520](https://github.com/facebookincubator/velox/pull/19520) nimble：索引支持的行/批迭代器

## StarRocks（1）
- [#80429](https://github.com/StarRocks/starrocks/pull/80429) 短路 PK compaction tier 资格记账
