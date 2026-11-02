# systems —— 第三方系统的架构剖析与源码阅读

一个目录 = 一个系统，目录内是该系统的全部研究文档。

2026-11-01 前这些内容分散在两处：`reports/` 放架构剖析，`reading-open-source/`
放源码阅读笔记，同一个系统（brpc、flink、starrocks）被切成两半。现在按系统名合并，
不存在"某个系统的笔记在哪个目录"的问题。

## 索引（篇数）

| 系统 | 篇 | 系统 | 篇 | 系统 | 篇 |
| --- | --- | --- | --- | --- | --- |
| [bigquery](bigquery/) | 2 | [brpc](brpc/) | 2 | [clickhouse](clickhouse/) | 3 |
| [crockroachdb](crockroachdb/) | 1 | [databend](databend/) | 1 | [databricks](databricks/) | 1 |
| [doris](doris/) | 1 | [duckdb](duckdb/) | 2 | [firebolt](firebolt/) | 1 |
| [firebot](firebot/) | 1 | [flink](flink/) | 2 | [hyper](hyper/) | 1 |
| [iceberg](iceberg/) | 1 | [maxcompute](maxcompute/) | 1 | [oracle](oracle/) | 2 |
| [postgres](postgres/) | 1 | [risingwave](risingwave/) | 1 | [snowflake](snowflake/) | 1 |
| [spark](spark/) | 1 | [starrocks](starrocks/) | 2 | [tidb](tidb/) | 1 |
| [trino](trino/) | 2 | [velox](velox/) | 1 |  |  |

## 文件命名

沿用迁移前的原文件名，因为它们已经带语义，改名只会让外部引用失效：

- `deepdive-2025.md` / `<系统>-deep-dive.md`：架构剖析
- `reading-<系统>.md`：源码阅读笔记（保留原始拼写，如 `reading-ducdb.md`）
- `changelog-2025(<model>).md`：按模型区分的年度变更跟踪

同一系统有多篇时按主题并列，不编号、不强行统一成 `architecture.md`——
统一改名会丢失原文件已被引用的路径，代价大于收益。

## 收录标准

- **放这里**：研究一个已有系统怎么实现（架构、数据结构、关键路径、版本变更）。
- **不放这里**：自己设计的方案 → [design/](../design/)；某个系统的接口怎么用 →
  该项目自己的 README。
