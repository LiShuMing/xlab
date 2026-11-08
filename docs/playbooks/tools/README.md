# playbooks —— 做事的方法

回答"这件事该怎么做"，不回答"这个系统是怎么实现的"（那是 [systems/](../systems/)）。

| 入口 | 内容 | 篇 |
| --- | --- | --- |
| [interview/](interview/) | 面试准备：算法、C++、数据库、OS/网络题库与答题方法、职业选择 | 12 |
| [learn/](learn/) | 学习方法：AI 与 C++ 的学习路径、资源清单 | 3 |
| [perf.md](perf.md) | 性能分析方法 | 1 |
| [review.md](review.md) | 代码评审方法 | 1 |
| [tools.md](tools.md) | 常用命令速查（NUMA、绘图等） | 1 |
| [knowledge-base.md](knowledge-base.md) | 个人知识库的构建与维护方法 | 1 |
| [skills/](skills/) | 运维脚本与写作参考：`ecs-health-check`、`mihomo-proxy` 的 `scripts/`，`writing-companion` 的 `references/` | 3 组 |

## 两种形态

- **文档形态**（`interview/`、`learn/`、根级 `.md`）：读了照着做。
- **素材形态**（[skills/](skills/)）：只保留 `scripts/` 与 `references/`，按需查阅或执行。

`skills/` 与其余文档合并进本目录，是因为它们回答同一个问题——"怎么做"；
拆成两个一级目录时，写作指南该进 `skills/` 还是 `how-to-do/` 没有稳定答案。

## 写作方法

[skills/writing-companion/references/tech-writing-patterns.md](skills/writing-companion/references/tech-writing-patterns.md)
是本仓库报告与笔记的写作规范入口，`docs/` 下新增文档时优先遵循它。
