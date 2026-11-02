# 系统设计

本目录收纳**可复用的系统设计方法与方案**：如何把"海量""高并发""低延迟"这类模糊
需求拆成可判定的约束，再据约束选方案，以及每个方案的取舍与验证方式。

它不收纳对第三方系统的源码阅读与研究笔记 —— 那些在 [systems/](../systems/)，
本页只做路由。

## 收录标准

满足以下任一条件即可放入本目录：

1. 描述一个自己动手设计或实现过的系统，包含约束、方案、取舍与验证；
2. 给出某类问题的通用设计框架（选型决策树、正确性依据、复杂度边界）；
3. 记录某类设计的典型错误及其反例。

以下内容放在原处，不进本目录：

| 内容 | 位置 | 原因 |
| --- | --- | --- |
| 某开源系统的架构剖析、实现细节 | [systems/](../systems/) | 是"研究某个系统"，不是"设计一个系统" |
| 源码阅读笔记 | [systems/](../systems/) | 阅读路径与代码锚点，不构成设计方案 |
| 面试题库与答题练习 | [playbooks/interview/](../playbooks/interview/) | 是准备方法，不是设计结论 |
| 学习计划与进度追踪 | [notes/ai-learning-plan.md](../notes/ai-learning-plan.md) | 计划项，随进度变化频繁 |
| RAG 应用架构笔记 | [notes/rag-systems.md](../notes/rag-systems.md) | 属于 AI 学习计划 Phase 2 的准备材料，随计划推进 |

## 文档清单

| 文档 | 主题 | 一句话 |
| --- | --- | --- |
| [top-k.md](top-k.md) | 海量数据 Top-K | 决定方案的是 K 与内存的关系、是否允许近似、是原始行还是聚合后排序，N 的大小几乎不参与决策 |
| [vectorized-execution.md](vectorized-execution.md) | 向量化执行 | 批处理化把逐行的解释开销与缓存失效摊薄，典型分析型负载 10–100x |
| [llm-inference-optimization.md](llm-inference-optimization.md) | LLM 推理优化 | 瓶颈在 prefill 是算力、在 decode 是显存带宽；KV cache 组织方式决定吞吐上限 |
| [ai-platform-design.md](ai-platform-design.md) | 多租户 AI 平台 | 用一道系统设计题把资源配额、背压、故障恢复、发布灰度串成一条链路 |

## 新增文档约定

- 文件名用 kebab-case，主题明确（`top-k.md` 而不是 `q3.md`）；
- 开头先写**结论与决策树**，再展开论证，避免读到最后才知道结论；
- 每个方案标出复杂度、内存、精度三轴代价，标出不适用的边界；
- 涉及正确性的结论必须给出可执行的验证方式（对拍、不变量、变异测试），
  而不是"看起来对"；
- 引用外部结论时给可追溯的公开来源；本地绝对路径不作为分发链接。

## 迁移记录

2026-11-01，本目录建立，以下文档按主题迁入（内容保持原样，仅加归属注记）：

| 原路径 | 现路径 | 说明 |
| --- | --- | --- |
| `docs/learn/vectorized-execution.md` | [vectorized-execution.md](vectorized-execution.md) | 执行引擎设计，不属于 AI 学习计划 |
| `docs/learn/llm-inference-optimization.md` | [llm-inference-optimization.md](llm-inference-optimization.md) | 推理服务设计；学习进度仍在 [AI 学习计划](../notes/ai-learning-plan.md) |
| `docs/questions/q1.md` | [ai-platform-design.md](ai-platform-design.md) | 原文件无标题，迁入时补标题 |
| （新建） | [top-k.md](top-k.md) | 本次会话产出的 Top-K 设计 |

`docs/questions/` 在迁出后已无文件，该目录随之消失。2026-11-01 `docs/` 整体重构后，
原 `docs/learn/` 的三篇笔记分别归入本目录与 [notes/](../notes/)；原 `docs/meta/` 拆为
[contracts/](../contracts/) 与 [archive/audits/](../archive/audits/)。

历史审计记录 [knowledge-base-audit-2026-05.md](../archive/audits/knowledge-base-audit-2026-05.md)
仍按当时的 `learn/` 路径描述，作为历史快照保留，不回改。
