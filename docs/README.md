# 文档导航与维护归属

`docs/` 是保留在 xlab 的 Markdown / Obsidian 资料，不是根站点的构建输入。
项目运行与开发入口见 [PROJECTS.md](../PROJECTS.md)；知识捕获工作流见
[SKILL.md](../SKILL.md)，写作参考见 [skills/](skills/)。

## 已迁入 Cygnus 的知识资料

两批共 **184 份**源文档已提取到私有知识仓库
[Cygnus](https://github.com/LiShuMing/cygnus)。该数量依据两批迁移清单，
不代表全部 xlab 文档，也不代表技术内容已经审核。迁移资料仍为 `needs-review`；
来源与逐文件校验以 Cygnus 的迁移记录为准。阅读私有链接需要已有仓库权限。

以下资料统一在 Cygnus 维护。2026-10-14 完成逐文件校验后，xlab 中对应的
184 份源正文及对应旧目录已退役，不保留跳转文件；其他资料仍保留。历史原件可从
备份分支恢复，详见 [退役记录](migrations/2026-10-14-cygnus-source-retirement.md)。

| 原 xlab 路径（已移除） | Cygnus 维护入口 |
| --- | --- |
| [ClickHouse](https://github.com/LiShuMing/cygnus/tree/main/books/clickhouse-book) | [books/clickhouse-book](https://github.com/LiShuMing/cygnus/tree/main/books/clickhouse-book) |
| [JDK](https://github.com/LiShuMing/cygnus/tree/main/books/deep-jdk-book) | [books/deep-jdk-book](https://github.com/LiShuMing/cygnus/tree/main/books/deep-jdk-book) |
| [LLVM](https://github.com/LiShuMing/cygnus/tree/main/books/Deep_Understanding_LLVM) | [books/Deep_Understanding_LLVM](https://github.com/LiShuMing/cygnus/tree/main/books/Deep_Understanding_LLVM) |
| [DuckDB](https://github.com/LiShuMing/cygnus/tree/main/books/duckdb-internals) | [books/duckdb-internals](https://github.com/LiShuMing/cygnus/tree/main/books/duckdb-internals) |
| [Flink](https://github.com/LiShuMing/cygnus/tree/main/books/flink-code-book) | [books/flink-code-book](https://github.com/LiShuMing/cygnus/tree/main/books/flink-code-book) |
| [Spark](https://github.com/LiShuMing/cygnus/tree/main/books/spark-internals) | [books/spark-internals](https://github.com/LiShuMing/cygnus/tree/main/books/spark-internals) |
| [DataFusion](https://github.com/LiShuMing/cygnus/tree/main/research/datafusion) | [research/datafusion](https://github.com/LiShuMing/cygnus/tree/main/research/datafusion) |
| [Umbra](https://github.com/LiShuMing/cygnus/tree/main/research/umbra) | [research/umbra](https://github.com/LiShuMing/cygnus/tree/main/research/umbra) |
| [Velox](https://github.com/LiShuMing/cygnus/tree/main/research/velox) | [research/velox](https://github.com/LiShuMing/cygnus/tree/main/research/velox) |

## 仍在 xlab 的资料

- [books/](books/)：其他书籍与长篇笔记，不因上述部分迁移而整体退役
- [reading-open-source/](reading-open-source/)、[about-llm/](about-llm/)：其余源码阅读与 LLM 笔记
- [learn/](learn/)：学习计划；未写的关联笔记标为计划项，不伪造空文件
- [reports/](reports/)、[build-projects/](build-projects/)：历史研究与项目资料
- [meta/](meta/)、[migrations/](migrations/)：审计、规划及迁移历史
- [skills/](skills/)：可复用写作与工具指南

实际项目的 README、设计与测试说明跟随所属源码目录。迁出应用见
[Constellation 迁移记录](migrations/2026-10-13-constellation.md)及
[DayLog 源码退役记录](migrations/2026-10-14-daylog-source-retirement.md)；
DayLog 已迁入 Carina，FragmentTutor 仍在 xlab。目录存在或有 README 不表示构建与测试已通过。

## 保留与隐私边界

根知识库不整体清空。私人记录、运维资料、运行数据、配置及历史排除项
必须单独审查，不能当作普通残余目录清理、公开复制或重新发布其内容。
不要为了修复旧链接恢复凭据、私人日志或数据快照；只更新安全的导航说明。
[旧知识库规划](meta/migration-guide.md) 中的 `_index`、`read`、`build`、
`_templates` 是未落地的方案，不是当前存在的目录或已完成迁移。
