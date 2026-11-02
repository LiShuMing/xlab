# archive —— 只读归档

历史快照区。**只允许修正失效的导航链接，不允许改写结论、补写新证据或删除记录。**
这里的价值在于"当时确实是这样记录的"，任何润色都会破坏这个价值。

| 子目录 | 内容 | 文件 |
| --- | --- | --- |
| [migrations/](migrations/) | 迁移与退役记录（含配套 `.json` 清单，被测试脚本校验） | 14 |
| [audits/](audits/) | 审计与状态快照（知识库审计、项目状态、任务历史） | 3 |
| [digests/](digests/) | 周期性产出与一次性速记：邮件阅读、GitHub 日报与未读通知摘要、博客、站点记录 | 13 |
| [projects/](projects/) | 历史项目报告（物化视图、RCA、股票、提示词） | 12 |
| [me/](me/) | 个人介绍（非技术文档，保留但不属于知识资产） | 2 |

## 命名约定

```
YYYY-MM-DD-<来源>-<主题>.md
```

日期在前是为了不依赖目录层级检索。`digests/` 下原 `2026-10-11.md` 这类
只有日期的文件名，因不同来源同日冲突，迁入时加了来源后缀（`-email`、`-github`、
`-github-notifications`）。同日多来源时靠后缀区分，不看目录。

## 已迁出资料的去向

两批共 **184 份**源文档提取到私有知识仓库
[Cygnus](https://github.com/LiShuMing/cygnus)，2026-10-14 逐文件校验后 xlab
中的源正文退役、不保留跳转文件。迁移资料仍为 `needs-review`，不代表技术内容已审核；
阅读私有链接需要仓库权限。恢复方式见
[退役记录](migrations/2026-10-14-cygnus-source-retirement.md)。

| 资料 | 维护入口 |
| --- | --- |
| ClickHouse | [books/clickhouse-book](https://github.com/LiShuMing/cygnus/tree/main/books/clickhouse-book) |
| JDK | [books/deep-jdk-book](https://github.com/LiShuMing/cygnus/tree/main/books/deep-jdk-book) |
| LLVM | [books/Deep_Understanding_LLVM](https://github.com/LiShuMing/cygnus/tree/main/books/Deep_Understanding_LLVM) |
| DuckDB | [books/duckdb-internals](https://github.com/LiShuMing/cygnus/tree/main/books/duckdb-internals) |
| Flink | [books/flink-code-book](https://github.com/LiShuMing/cygnus/tree/main/books/flink-code-book) |
| Spark | [books/spark-internals](https://github.com/LiShuMing/cygnus/tree/main/books/spark-internals) |
| DataFusion | [research/datafusion](https://github.com/LiShuMing/cygnus/tree/main/research/datafusion) |
| Umbra | [research/umbra](https://github.com/LiShuMing/cygnus/tree/main/research/umbra) |
| Velox | [research/velox](https://github.com/LiShuMing/cygnus/tree/main/research/velox) |
| Codex 源码书 | [books/codex-code-book](https://github.com/LiShuMing/cygnus/tree/main/books/codex-code-book) |
| Linux 内核书 | [books/deep-linux-book](https://github.com/LiShuMing/cygnus/tree/main/books/deep-linux-book) |

另有 96 份 Codex/Linux 源稿归档至 Cygnus，总计 280 份迁出源文档。本批 174 个源路径
全部登记：161 个归档或适配，13 个历史文档/生成输出仅保留于 Git 历史与备份。
详情见[退役记录](migrations/2026-10-14-books-email-learning-retirement.md)。
Calcite、RisingWave、Claude、Feynman 资料不在本批范围。

[邮件摘要](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest)与
[每日学习](https://github.com/LiShuMing/lyra/tree/main/modules/daily-learning)
在 Lyra 维护，本目录只保留迁出前的历史产出。

## 应用与项目迁出记录

| 事项 | 记录 |
| --- | --- |
| Constellation 迁出 | [2026-10-13-constellation.md](migrations/2026-10-13-constellation.md) |
| DayLog 迁入 Carina | [2026-10-14-daylog-source-retirement.md](migrations/2026-10-14-daylog-source-retirement.md) |
| Python 工具与研究模块 | [2026-10-14-python-source-retirement.md](migrations/2026-10-14-python-source-retirement.md) |
| FragmentTutor 等五个项目移除 | [2026-10-15-five-project-retirement.md](migrations/2026-10-15-five-project-retirement.md) |
| 最后四组书稿（76 文件） | [2026-10-15-remaining-books-retirement.md](migrations/2026-10-15-remaining-books-retirement.md) |
| Haskell → OCaml/Lean 4 | [2026-10-29-functional-learning.md](migrations/2026-10-29-functional-learning.md) |
