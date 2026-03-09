> 原始 Prompt（保留）
>
> 我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（StarRocks）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。
>
> 阅读Clickhouse从2025年的change log(https://clickhouse.com/docs/whats-new/changelog/2025)，总结Clickhouse重大feature/optimzation及场景的变化，从技术、产品的角度，分析并洞察Clickhouse的产品定位及迭代方向、商业价值。并在该文档中按照博客的方式输出一篇介绍文章。保留该pompt。

下面这篇我按“技术博客”来写：先把 2025 年 ClickHouse 的大变化按主题归类，再从产品/商业视角做一层“为什么要这么做”的解读；同时尽量用 **changelog 里的 PR 链接**做锚点，并用官方 release blog/专题文章补充背景。

---

# ClickHouse 2025：从“极速 OLAP 引擎”到“数据湖 + 搜索 + 可观测性”的通用实时数据底座

2025 年 ClickHouse 的节奏依旧很“工程师”：几乎按月发版（25.1 → 25.12，含 25.3/25.8 LTS），并且每个版本都有明确的主线：**更强的查询执行与优化器、更实用的数据湖（Iceberg/DeltaLake/Catalog）能力、更像搜索引擎的索引体系（text / vector / skip index）、以及面向 Cloud/Observability 的产品化能力**。官方也做了全年回顾，列出了 25.1~25.12 全部 release post 索引，基本可以当“年度脉络目录”。 ([ClickHouse][1])

如果你把 ClickHouse 的定位理解为“更快的列存数据库”，2025 的变化会让你意识到：它正在把自己打造成一个**能直接吃数据湖、能做向量/文本检索、能承载可观测性高基数数据的实时数据平台**——而速度仍然是它的宗教。

---

## 1) 数据湖主线：Iceberg / DeltaLake / Catalog 全面“平台化”

### 1.1 从“能读”到“能写”，再到“能治理”

2025 年最清晰的一条主线，是 ClickHouse 对 open table formats 的推进：Iceberg/DeltaLake 不再只是“外部表读一下”，而是逐步补齐写入、演化、运维能力。

* **Iceberg 写入创建**：#83983 ([clickhouse.ac.cn][2])
* **Glue / Rest catalog 支持写入**：#84136、#84684 ([clickhouse.ac.cn][2])
* **把 Iceberg position delete files 合并进数据文件（OPTIMIZE）**：#85250 ([clickhouse.ac.cn][2])
* **Iceberg drop table（连 catalog 元数据一起删）**：#85395 ([clickhouse.ac.cn][2])
* **Iceberg schema evolution：复杂类型、字段 ID 读取、压缩 metadata.json、TimestampTZ 等兼容性**：#73714、#83653、#81451、#83132 ([clickhouse.ac.cn][2])

这些点看似零散，但合起来其实是在回答同一个产品问题：

> “用户把事实数据放在 Iceberg/DeltaLake 上以后，ClickHouse 能不能**像一个一等公民的计算引擎**那样参与生产链路，而不是只能当个旁路查询器？”

这背后直接对应 Databricks / Snowflake / Trino 生态的现实：大家都在围绕 Iceberg 形成“统一数据底座”，计算引擎如果只会读，就很难吃到更核心的 workload。

### 1.2 Catalog：从实验到 Beta，再到“云里可用”

Catalog 这一块，2025 的推进非常明确：Unity/Glue/Rest/Hive Metastore 目录从实验性提升到 Beta。#85848 ([clickhouse.ac.cn][2])
并且还有更底层的补洞，比如 Unity Catalog 数据类型支持、权限不足时仍可列举表等兼容性修复。#80740、#81044 ([clickhouse.ac.cn][2])

再看“把概念讲清楚”的官方博客：ClickHouse Cloud 在 25.8 中把 Glue/Unity 的集成推到 beta，并给了 demo 视角：**“只要在你的 catalog 里，我就能查”**，这句话的产品意味很重。 ([ClickHouse][3])

### 1.3 DeltaLake：不仅支持，还引入 delta-kernel-rs

changelog 里也能看到 DeltaLake 相关的增强与修复，例如基于 `delta-kernel-rs` 的实现进度条/性能修复。#78368 ([clickhouse.ac.cn][2])
这类动作很“工程化”：不是喊口号，而是在把外部格式的复杂性（schema、manifest、delete files、快照）逐步纳入可控范围。

**行业解读（利与弊）**

* **利**：ClickHouse 从“仓库”升级为“能直接接入湖仓治理体系的计算引擎”。对企业来说，意味着更少 ETL、更低数据复制成本、更灵活的 BI/探索查询。
* **弊**：Iceberg/DeltaLake 的语义很深（快照一致性、delete vectors/position deletes、catalog 权限模型），ClickHouse 要把它们做得“像原生表一样好用”，工程复杂度会持续上升；并且它得在“保持极致性能”和“兼容各种湖仓边界条件”之间做艰难取舍。

---

## 2) 查询引擎与优化器：JOIN、延迟物化、Top-N、以及“更像数据库”的计划优化

如果说数据湖是“外扩边界”，那么 2025 的另一条主线就是：**把 ClickHouse 的查询执行模型继续压榨到极限，同时让优化器更聪明、更可控**。

### 2.1 JOIN：从更快到更聪明（重排序 + 新算法）

* **DPsize join reorder（实验性）**：#91002 ([clickhouse.ac.cn][2])
* **支持 MergeTree 的 direct（nested loop）join**：#89920 ([clickhouse.ac.cn][2])

配合 release blog（25.10、25.12 等）对 JOIN 的重点描述，你能感到 ClickHouse 在补齐传统数据库里“优化器该做的事”，同时仍然保持它对 pipeline / vectorized execution 的执念。 ([ClickHouse][4])

**作为 OLAP 引擎研发者的直觉**：
ClickHouse 过去在 JOIN 上给人的感觉是“快，但你得写得对”；2025 的方向像是在把它往“快，而且尽量帮你写对”推——这对产品化太关键了。

### 2.2 延迟物化（lazy / late materialization）继续扩大战果

* 25.4 release blog 直接把 **lazy materialization** 作为 headline 特性之一。 ([ClickHouse][5])
* 25.12 继续强调通过“延迟读取 + join-style execution model”等手段加速典型查询模式。 ([ClickHouse][6])
* changelog 里也有“通过更大限制改进延迟物化列性能”的条目：#90309 ([clickhouse.ac.cn][2])

这其实是一种非常务实的优化路径：把最常见的 dashboard / top-n / 选择性过滤场景（读很少列、过滤/排序很强）做到更快，直接转化为用户体验。

### 2.3 Top-N 与 skip index：把“最常见的慢查询”狠狠干掉

* **用 skip index + 动态阈值过滤器优化 `ORDER BY ... LIMIT N`**：#89835 ([clickhouse.ac.cn][2])
* **WHERE 支持混合 AND/OR 的 skip index 分析（新增 `use_skip_indexes_for_disjunctions`，默认开）**：#87781 ([clickhouse.ac.cn][2])

这两条的产品价值很直接：Top-N 是 BI 面板里最常见的形态之一，哪怕提升 20%，在规模化场景里都是真金白银。

---

## 3) 索引与“搜索化”：text index、vector search、以及更强的 Parquet

2025 年 ClickHouse 的索引体系越来越像一个“通用检索底座”，尤其是文本与向量。

### 3.1 向量检索：从 Beta 到 GA，并补齐过滤语义

* **向量相似度索引 GA**：#85888 ([clickhouse.ac.cn][2])
* **向量搜索支持预过滤/后过滤，并提供更细控制**：#79854 ([clickhouse.ac.cn][2])
* **BFloat16 列可建向量相似度索引**：#78850 ([clickhouse.ac.cn][2])

这基本就是对 RAG / embedding 检索的正面回答：不仅要 ANN（近似最近邻），还要把“过滤条件 + 检索召回”组合得像样，否则一落到真实业务（多租户、权限、业务维度过滤）就会很尴尬。

### 3.2 文本索引：从“有”到“可运维”

* **SYSTEM DROP TEXT INDEX CACHES**：#90287 ([clickhouse.ac.cn][2])
* 甚至还有 “text index 可用于 ReplacingMergeTree” 的修复/增强：#90908 ([clickhouse.ac.cn][2])

这类功能看着不起眼，但非常“产品”：缓存可控、运维可控，才敢在生产里大规模上。

### 3.3 Parquet：新 reader + page-level 下推，直接打到湖仓场景的命门

* **新的 Parquet reader（更快、支持 page-level filter pushdown + PREWHERE，实验性开关 `input_format_parquet_use_native_reader_v3`）**：#82789 ([clickhouse.ac.cn][2])

这对“直接查对象存储/数据湖”的意义巨大：很多时候 ClickHouse 的瓶颈不在执行，而在“读取与解析”。把 Parquet 读得更聪明，等于把数据湖故事的地基加固了。

---

## 4) 数据变更与投影：让 ClickHouse 更像“可用的数据库”，而不只是“快的查询器”

### 4.1 Lightweight Update/Delete：向混合负载迈一步

* **MergeTree lightweight update**：#82004 ([clickhouse.ac.cn][2])
  并且 changelog 明确写了语法与 delete 的启用模式，这不是“实验玩具”，而是把工程边界（何时可用、怎么启用、语义是什么）交代清楚。

### 4.2 Projections：从“物化副本”到更像“二级索引”

2026 年初 ClickHouse 官方还专门写了一篇文章回顾：从 25.6 起，projections 更轻量、更像二级索引（只存排序键 + pointer），显著降低存储开销。 ([ClickHouse][7])
把它放回 2025 的主线里看：这和 “late materialization / skip index / top-n” 是同一种哲学——用更低成本的结构换取更强的查询加速与可控性。

---

## 5) Cloud / 安全 / 可观测性：商业化能力在 2025 更“显性”

### 5.1 Cloud-only 能力开始写进 changelog：数据掩码

* **行级安全的数据掩码（ClickHouse Cloud only）**：#90552 ([clickhouse.ac.cn][2])

这很关键：当你开始在官方 changelog 里明确标注 “Cloud only”，说明产品已经进入“开源内核 + 云增值能力”更清晰的分层阶段。

### 5.2 安全：真实世界的漏洞响应

安全更新日志里记录了 **CVE-2025-1385**（library bridge + 误配置可导致任意代码执行的风险）并说明了修复版本范围。 ([ClickHouse][8])
这类条目从商业视角也很重要：企业会看你如何处理漏洞、是否有清晰披露与支持策略。

### 5.3 可观测性与 ClickStack：把“高基数时序/日志/trace”当成主战场之一

25.8 release blog 提到 **初步 PromQL 支持**，以及围绕可观测性生态的推进。 ([ClickHouse][9])
再叠加 2025 年 ClickHouse 关于 ClickStack 的持续更新与生态文章（包括对 AI agents/MCP 的连接），你会看到 ClickHouse 在争取一个非常现实的市场：**“可观测性是数据问题，用分析型引擎做更划算”**。 ([ClickHouse][10])

---

# 总结：ClickHouse 2025 的定位与迭代方向（带点“老江湖”味道）

**1）定位在上移：从“极速 OLAP”变成“实时数据平台底座”。**
数据湖（Iceberg/DeltaLake/Catalog）+ 搜索（text/vector）+ 可观测性（PromQL/ClickStack）这三条腿，让 ClickHouse 的 TAM（可服务市场）明显变大：不再只和 OLAP 仓库打架，而是进入“湖仓计算 + 检索 + 观测”的更大竞技场。 ([clickhouse.ac.cn][2])

**2）技术策略很一致：用 execution model 的极致优化，反哺产品体验。**
lazy/late materialization、skip index、Top-N、JOIN 优化/重排序——这些都不是“为了论文”，而是为了把最常见的生产查询（面板、探索、关联分析）做得更快更稳。 ([ClickHouse][6])

**3）商业价值更清晰：Cloud 分层、治理能力、生态连接开始成体系。**
Cloud-only（如数据掩码）直接瞄准企业治理付费点；Catalog 打通瞄准湖仓生态入口；可观测性/Agentic tooling 是增长楔子。 ([clickhouse.ac.cn][2])

**4）潜在风险也真实存在：平台化意味着复杂度上升。**
当 ClickHouse 试图同时“像数据库、像湖仓计算、像搜索引擎、像观测平台”，工程复杂度会指数上升。它需要持续把复杂性关在内部，并给用户一个“仍然简单、仍然快”的表象——这对架构与团队是长期挑战。

---

这篇文章你可以直接贴到你的博客里用；如果你后续想把它“升级成可持续写作模板”，我建议把结构固化成三段式：**年度主线 → 主题拆解（每条 3-5 个 PR 锚点）→ 产品/商业解读（利弊 + 竞争格局）**，以后你写 StarRocks/Trino/Databricks 的年度回顾也能复用。

[1]: https://clickhouse.com/blog/clickhouse-2025-roundup?utm_source=chatgpt.com "What's new in ClickHouse – 2025 roundup"
[2]: https://clickhouse.ac.cn/docs/whats-new/changelog/2025 "2025 Changelog | ClickHouse Docs - ClickHouse 教程"
[3]: https://clickhouse.com/blog/query-your-catalog-clickhouse-cloud?utm_source=chatgpt.com "If it's in your catalog, you can query it"
[4]: https://clickhouse.com/blog/clickhouse-release-25-10?utm_source=chatgpt.com "ClickHouse Release 25.10"
[5]: https://clickhouse.com/blog/clickhouse-release-25-04?utm_source=chatgpt.com "ClickHouse Release 25.4"
[6]: https://clickhouse.com/blog/clickhouse-release-25-12?utm_source=chatgpt.com "ClickHouse Release 25.12"
[7]: https://clickhouse.com/blog/projections-secondary-indices?utm_source=chatgpt.com "ClickHouse projections now behave like true secondary ..."
[8]: https://clickhouse.com/docs/whats-new/security-changelog?utm_source=chatgpt.com "Security changelog | ClickHouse Docs"
[9]: https://clickhouse.com/blog/clickhouse-release-25-08?utm_source=chatgpt.com "ClickHouse Release 25.8"
[10]: https://clickhouse.com/blog/how-to-build-ai-agents-mcp-12-frameworks?utm_source=chatgpt.com "How to build AI agents with MCP: 12 framework ..."
