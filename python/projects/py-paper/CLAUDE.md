# 基于 Python 构建论文阅读 Agent 的技术设计文档

## 1. 文档目标

本文档定义一个基于 Python 的“论文阅读 Agent”系统，用于将单篇或多篇学术论文 PDF 转化为结构化理解结果，并输出带证据链的分析报告。系统不定位为简单的 Chat-with-PDF，而定位为“科研阅读协作 Agent”：

* 能解析论文结构、章节、图表、表格与参考文献；
* 能提取背景、问题定义、创新点、方法、实验设置、核心数据结果、局限性；
* 能对关键结论绑定原文证据；
* 能补充 related work、后续工作、相近开源实现；
* 能生成适合博客、组会、面试、技术调研的报告。

该设计优先追求三件事：**可追溯、可校验、可重跑**。

---

## 2. 背景与动机

现有通用 Agent 与 RAG 框架已经提供了构建文档 Agent 的基础能力。LlamaIndex 明确强调基于数据与工作流构建 agents，并把 document agents / workflows 作为重点方向；Haystack 也提供了面向生产的 agent 与 pipeline 机制，支持带循环与分支的复杂工作流。与此同时，PaperQA 则专门面向 scientific literature，强调基于论文的高准确率问答与引用绑定。PyMuPDF 与 PyMuPDF4LLM 提供了高性能 PDF 提取能力和更适合 LLM/RAG 的结构化导出能力。([LlamaIndex OSS Documentation][1])

但是，这些能力单独使用时仍有明显空缺：
一是单篇论文的“精读分析”往往不够强，尤其是图表、实验结论、作者 claim 与数据支持之间的区分；二是 related work 与综述生成更偏 web research，缺少对单篇论文证据的紧密绑定；三是很多系统更像问答接口，而不是可恢复、可重跑的状态机。基于这些差距，本系统设计为一个“workflow-guided research agent”，以结构化解析和证据绑定为中心，再叠加外部检索和报告生成。([LlamaIndex OSS Documentation][2])

---

## 3. 设计原则

### 3.1 证据优先

所有核心结论必须尽量绑定到：

* 原文段落
* 页码
* 图号/表号
* 外部引用来源

系统的摘要与结论不是“自由生成”，而是“从证据组织出来”。

### 3.2 Workflow 优先于自由 Agent

论文阅读是高结构化任务，更适合固定阶段的工作流，而不是完全自由的多 Agent 自主协作。系统将采用“阶段化状态机 + 局部 Agent 决策”模式。

### 3.3 单篇读准，优先于多篇读广

MVP 阶段先确保单篇论文结构解析、证据提取、报告生成可用，再扩展到 related work 与多文献综述。

### 3.4 可观测与可重跑

每次分析都应记录：

* 输入文件版本
* 解析结果
* 中间状态
* Prompt 版本
* 模型版本
* 引用证据
* 最终报告版本

---

## 4. 目标能力范围

### 4.1 MVP 能力

1. 上传单篇 PDF
2. 自动解析章节、段落、页码
3. 提取背景、问题、创新点、方法、实验、结果、局限
4. 对每个关键结论附原文证据
5. 生成 Markdown 报告

### 4.2 增强能力

1. 图表/表格识别与解释
2. related work 检索与比较
3. 多篇论文对比分析
4. 博客版 / 组会版 / 面试版多风格输出
5. 用户偏好记忆，例如偏系统、偏实验、偏方法

### 4.3 非目标

MVP 阶段不追求：

* 全自动综述数百篇论文
* 完全自主多 Agent 辩论式分析
* 高保真公式语义理解
* 全量参考文献自动精读

---

## 5. 系统总体架构

### 5.1 逻辑分层

系统划分为七层：

1. **文档接入层**
   负责 PDF 上传、文件指纹计算、任务创建。

2. **解析层**
   负责 PDF 文本、章节、表格、图注、参考文献抽取。

3. **结构化抽取层**
   负责识别论文骨架：标题、摘要、问题定义、创新点、方法、实验、局限等。

4. **检索与证据层**
   负责 chunk 索引、混合检索、证据绑定、引用管理。

5. **研究扩展层**
   负责 external search、related work 检索、开源项目调研。

6. **生成层**
   负责生成摘要、问答、结构化 JSON、技术报告、博客文章。

7. **观测评测层**
   负责 trace、日志、评测样本、回放、版本比对。

### 5.2 核心数据流

输入 PDF 后，系统按以下顺序执行：

1. 文件上传与任务初始化
2. PDF 解析，生成原始页面文本与结构化块
3. Section-aware chunking
4. 元数据入库与索引构建
5. 运行论文骨架抽取任务
6. 运行证据绑定任务
7. 运行外部 related work 检索任务
8. 生成报告
9. 保存 trace 与结果

---

## 6. 技术选型

### 6.1 Python 运行时

推荐 Python 3.11+，理由是生态成熟、异步能力完整、与 AI/RAG 框架兼容性最好。

### 6.2 PDF 解析

首选 **PyMuPDF** 作为基础解析库，因其强调高性能 PDF 提取与操作；对于更适合 RAG 的结构化导出，可优先研究 **PyMuPDF4LLM**，其提供 Markdown、JSON、TXT 导出，并支持与 LlamaIndex / LangChain 集成。([PyMuPDF][3])

可选补充：

* `pdfplumber`：用于表格提取实验
* `unstructured`：做版面解析对比
* 视觉模型：补强图表理解

### 6.3 Agent / Workflow 框架

推荐两条路线二选一：

**路线 A：LlamaIndex**
适合 document-centric 场景。官方文档明确将 agents、workflows、document agents 作为核心能力，适合把“文档解析 + 工作流”耦合在一起。([LlamaIndex OSS Documentation][2])

**路线 B：Haystack**
适合更显式的 pipeline 编排。Haystack 强调可重用组件、生产级 agents、带分支和循环的 agentic pipelines，更适合工程上做透明流程控制。([Haystack 文档][4])

**建议**：
MVP 阶段若更重“快速做出文档 Agent”，可选 LlamaIndex；
若更重“显式工作流、可控性、可维护性”，可选 Haystack。
如果你希望自己主导全部状态机逻辑，也可以只用 Python + 检索库，自建工作流层。

### 6.4 科学论文问答参考实现

建议重点研究 **PaperQA** 的设计，因为它明确聚焦 scientific literature，强调面向论文的 agentic RAG 和高准确率引用式回答。它不是完整的论文阅读平台，但非常适合借鉴“证据型回答”这条线。([GitHub][5])

### 6.5 存储与索引

* 元数据库：PostgreSQL / SQLite（MVP）
* 向量库：FAISS（本地）、Qdrant / Milvus（服务化）
* 文本检索：BM25（Whoosh / Elasticsearch / OpenSearch）
* 对象存储：本地文件系统 / S3

建议采用**混合检索**，因为论文中的术语、数值、公式名、图表编号常常不适合只靠向量检索。

### 6.6 模型层

至少分两类：

* **抽取/总结模型**：长上下文、擅长结构化输出
* **问答/生成模型**：擅长引用式解释和报告生成

若要增强图表理解，可加入 vision-capable model。

---

## 7. 核心模块设计

## 7.1 Document Ingestion 模块

### 职责

* 接收 PDF 文件
* 生成任务 ID
* 计算文件哈希
* 写入文件元数据
* 触发解析工作流

### 输入

* `paper.pdf`
* 可选用户偏好：如“关注创新点”“偏实验分析”

### 输出

* `document_id`
* `analysis_job_id`

### 关键字段

```json
{
  "document_id": "uuid",
  "filename": "paper.pdf",
  "sha256": "xxx",
  "uploaded_at": "timestamp",
  "status": "uploaded"
}
```

---

## 7.2 PDF Parsing 模块

### 职责

* 提取每页文本
* 识别标题层级
* 识别摘要、引言、方法、实验、结论等章节
* 抽取图注、表注、参考文献区域
* 输出适合 chunking 的中间表示

### 设计要点

1. 支持双栏 PDF
2. 去除页眉页脚噪音
3. 尽量保留段落边界
4. 图表 caption 单独存储
5. 对参考文献单独分区，避免污染主检索空间

### 输出数据结构

```json
{
  "pages": [
    {
      "page_num": 1,
      "text_blocks": [...],
      "figures": [...],
      "tables": [...]
    }
  ],
  "sections": [
    {"title": "Abstract", "start_page": 1},
    {"title": "Introduction", "start_page": 1}
  ]
}
```

---

## 7.3 Chunking 模块

### 职责

* 将解析结果切分为可检索单元
* 保留结构化元数据
* 支持 section-aware 与 semantic-aware chunking

### Chunk 策略

建议采用混合切分：

1. 按 section 初切
2. 按段落或固定 token 长度细切
3. 保留 chunk overlap
4. 图表 caption 与正文分开索引
5. 表格解析结果作为独立 chunk

### Chunk 元数据

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "section": "Experiments",
  "page_start": 6,
  "page_end": 6,
  "chunk_type": "paragraph",
  "text": "...",
  "citations": [],
  "figure_refs": ["Figure 3"],
  "table_refs": ["Table 2"]
}
```

---

## 7.4 Paper Structure Extractor 模块

### 职责

从 chunk 集合中提取论文骨架。

### 抽取目标

* 标题
* 作者
* 发表 venue / 年份（可选）
* 问题定义
* 核心贡献
* 方法概述
* 实验设置
* 关键结果
* 局限性
* 作者 claim 与 evidence 的对应

### 输出 Schema

```json
{
  "title": "",
  "authors": [],
  "problem_statement": "",
  "main_contributions": [],
  "method_summary": "",
  "experiment_setup": "",
  "key_results": [],
  "limitations": [],
  "open_questions": []
}
```

### 提示策略

* 优先从 Abstract / Introduction / Conclusion 抽问题与贡献
* 从 Method 抽核心机制
* 从 Experiments 抽数据与实验结论
* 从 Discussion / Limitation 抽边界条件
* 若没有显式 limitation 章节，则从 Conclusion 与错误案例中推断，但必须标注为“推断”

---

## 7.5 Evidence Binder 模块

### 职责

把系统抽取的每条结论绑定到原文证据。

### 为什么它是核心模块

没有它，系统会退化成普通摘要器。
有了它，系统才能做到：

* 结论可审计
* 报告可追溯
* 模型错误更易定位
* 用户更信任输出

### 绑定粒度

每一条结果至少绑定：

* `source_chunk_ids`
* `page_numbers`
* `support_type`：direct / inferred
* `figure_or_table_refs`

### 示例

```json
{
  "claim": "作者提出的方法在长序列场景下优于 baseline。",
  "support_type": "direct",
  "source_chunk_ids": ["c1", "c7"],
  "page_numbers": [8, 9],
  "figure_or_table_refs": ["Figure 5", "Table 3"]
}
```

---

## 7.6 Retrieval 模块

### 职责

支持两类检索：

1. **任务型检索**
   为结构化抽取服务，如“检索创新点相关 chunk”“检索实验结果相关 chunk”。

2. **交互型检索**
   为用户问答服务，如“这篇论文的主要假设是什么？”

### 检索策略

推荐：

* BM25 + Vector Hybrid Retrieval
* Reranker 二次排序
* Metadata filtering，例如只搜 `section=experiments`
* 支持 figure/table aware retrieval

### 为什么要混合检索

论文里有大量：

* 专有名词
* 缩写
* 图表编号
* 数字结果
* 数学符号名

这些内容纯向量检索效果通常不稳。

---

## 7.7 Research Expander 模块

### 职责

在单篇论文精读之后，补充外部研究脉络。

### 子任务

1. 检索同主题 survey / tutorial
2. 检索相似方法或 baseline
3. 检索后续 follow-up papers
4. 检索开源实现、代码仓库、官方博客

### 输入

* 论文标题
* 摘要
* 关键词
* 引用网络中的关键 references

### 输出

```json
{
  "related_works": [
    {
      "title": "",
      "why_relevant": "",
      "relationship": "baseline/follow-up/survey/alternative",
      "source": ""
    }
  ]
}
```

### 注意

外部相关工作与论文内证据必须区分标注：

* `source_type = internal_pdf`
* `source_type = external_search`

---

## 7.8 Report Writer 模块

### 职责

生成最终报告。

### 支持输出模板

1. 论文速读版
2. 技术精读版
3. 博客版
4. 组会汇报版
5. 面试讲解版

### 标准报告结构

建议默认包含：

1. 论文背景
2. 论文试图解决的问题
3. 核心创新点
4. 方法机制概览
5. 核心实验设计
6. 关键数据结果
7. 论文的优点
8. 局限与潜在问题
9. 与 related work 的关系
10. 我的评价 / 工程启发

### 输出约束

* 每个关键结论尽量附页码/图表编号
* 区分“作者声称”和“系统评价”
* related work 信息要单独标注外部来源

---

## 7.9 Evaluation 模块

### 职责

评估输出质量。

### 评测维度

1. 结构覆盖率
   是否抽到了 problem / contribution / method / experiments / results / limitations

2. 证据绑定率
   报告中有多少条结论附带来源

3. 事实一致性
   是否出现与原文冲突的表述

4. 检索命中率
   对关键问题的证据是否能被检出

5. 结果可读性
   报告是否结构清楚、适合人阅读

### MVP 阶段的实现建议

* 建一批手工标注论文样本
* 对每篇样本保存 gold annotations
* 比较系统抽取与 gold 的重合度
* 人工 spot check 关键 claim 的证据

---

## 8. 状态机设计

系统采用显式状态机而不是隐式串行流程。

### 8.1 状态定义

* `UPLOADED`
* `PARSING`
* `PARSED`
* `CHUNKED`
* `INDEXED`
* `STRUCTURE_EXTRACTED`
* `EVIDENCE_BOUND`
* `RELATED_WORK_EXPANDED`
* `REPORT_GENERATED`
* `FAILED`

### 8.2 状态转移

```text
UPLOADED
  -> PARSING
  -> PARSED
  -> CHUNKED
  -> INDEXED
  -> STRUCTURE_EXTRACTED
  -> EVIDENCE_BOUND
  -> RELATED_WORK_EXPANDED
  -> REPORT_GENERATED
```

### 8.3 失败恢复

若某一步失败：

* 记录异常
* 标记失败模块
* 支持从最近成功状态重试
* 不重新解析整个 PDF，除非解析结果损坏

---

## 9. 数据模型设计

## 9.1 Document 表

```json
{
  "document_id": "uuid",
  "filename": "paper.pdf",
  "sha256": "...",
  "status": "parsed",
  "created_at": "...",
  "updated_at": "..."
}
```

## 9.2 Chunk 表

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "section": "Method",
  "page_start": 3,
  "page_end": 3,
  "chunk_type": "paragraph",
  "text": "...",
  "embedding_id": "..."
}
```

## 9.3 Extraction 表

```json
{
  "document_id": "uuid",
  "schema_version": "v1",
  "problem_statement": "...",
  "main_contributions": [...],
  "method_summary": "...",
  "key_results": [...]
}
```

## 9.4 Evidence 表

```json
{
  "evidence_id": "uuid",
  "document_id": "uuid",
  "claim_text": "...",
  "support_type": "direct",
  "source_chunk_ids": ["..."],
  "page_numbers": [5, 6],
  "figure_refs": ["Figure 2"]
}
```

## 9.5 Trace 表

```json
{
  "trace_id": "uuid",
  "document_id": "uuid",
  "stage": "structure_extraction",
  "prompt_version": "v3",
  "model_name": "...",
  "input_refs": ["chunk1", "chunk4"],
  "output": {...},
  "latency_ms": 1200
}
```

---

## 10. API 设计

### 10.1 上传论文

`POST /documents`

返回：

```json
{
  "document_id": "uuid",
  "job_id": "uuid"
}
```

### 10.2 查询任务状态

`GET /jobs/{job_id}`

### 10.3 获取结构化结果

`GET /documents/{document_id}/summary`

### 10.4 提问

`POST /documents/{document_id}/ask`

请求：

```json
{
  "question": "这篇论文的核心创新点是什么？"
}
```

响应：

```json
{
  "answer": "...",
  "citations": [
    {"page": 2, "chunk_id": "c1"},
    {"page": 8, "chunk_id": "c9"}
  ]
}
```

### 10.5 生成报告

`POST /documents/{document_id}/report`

请求：

```json
{
  "template": "tech_deep_dive"
}
```

---

## 11. Prompt / Workflow 设计

### 11.1 抽取创新点 Prompt

输入：

* Abstract
* Introduction
* Conclusion
* Method 的前几个关键 chunk

输出格式：

```json
{
  "main_contributions": [
    {
      "text": "...",
      "confidence": 0.87,
      "evidence_chunk_ids": ["..."]
    }
  ]
}
```

### 11.2 抽取实验结果 Prompt

输入：

* Experiment section chunks
* Figure captions
* Table captions

输出：

```json
{
  "key_results": [
    {
      "claim": "...",
      "metric": "...",
      "comparison_target": "...",
      "evidence_refs": ["Table 2"]
    }
  ]
}
```

### 11.3 生成报告 Prompt

输入：

* 结构化抽取结果
* 证据列表
* related work 列表

约束：

* 不允许无证据扩写论文内事实
* 若是推断，必须标“推断”
* external source 单独标注

---

## 12. 观测与运维设计

### 12.1 关键指标

* 解析成功率
* 抽取成功率
* 证据绑定率
* 平均任务时延
* 平均每篇成本
* 用户问答满意度
* 报告人工修改率

### 12.2 日志

需要记录：

* 每一步输入输出
* 检索到的 chunk
* 模型请求参数
* 错误堆栈
* 版本号

### 12.3 回放机制

给定 `trace_id`，可复现一次完整步骤，便于：

* 调 prompt
* 比模型版本
* 比不同 chunking 策略

---

## 13. 安全与边界控制

### 13.1 文件安全

* 限制文件大小
* 检查文件类型
* 隔离存储路径
* 扫描恶意内容

### 13.2 模型输出边界

* 不把推断包装成事实
* 不自动相信外部网页内容
* 对 related work 标记来源

### 13.3 成本控制

* 大文件分阶段处理
* 先抽骨架，再决定是否深读图表
* 限制外部搜索轮次

---

## 14. MVP 实施计划

## 14.1 Phase 1：单篇论文解析与报告

目标：

* 上传 PDF
* 结构化抽取
* 证据绑定
* Markdown 报告生成

技术栈建议：

* FastAPI
* PyMuPDF
* FAISS + BM25
* PostgreSQL / SQLite
* 单模型调用

交付物：

* CLI / Web API
* Markdown 报告
* JSON 中间结果

## 14.2 Phase 2：图表与表格增强

新增：

* figure/table extraction
* 图表解释
* 实验结果更精准归纳

## 14.3 Phase 3：Related Work 扩展

新增：

* 外部检索
* 相似论文对比
* 研究脉络图

## 14.4 Phase 4：多论文对比与个人化

新增：

* 多篇论文横向比较
* 保存用户阅读偏好
* 输出风格模板化

---

## 15. 与现有开源方案的关系

建议采用“借鉴 + 组装”策略，而不是直接复制某个项目。

* **PyMuPDF / PyMuPDF4LLM**：适合作为解析底座，尤其是结构化导出能力。([PyMuPDF][3])
* **PaperQA**：适合借鉴 scientific literature 上的问答与引用策略。([GitHub][5])
* **LlamaIndex**：适合 document agent / workflow 方向，尤其适合快速拼出文档型 Agent。([LlamaIndex OSS Documentation][2])
* **Haystack**：适合显式流程控制、生产级 pipeline 和 agentic workflow。([Haystack][6])

推荐做法是：

* 解析层：PyMuPDF
* 工作流层：LlamaIndex 或自建
* 检索层：自建 hybrid retrieval
* 证据层：自行实现
* 报告层：自行实现
  因为真正差异化的价值，不在框架，而在**论文结构理解 + 证据绑定 + 报告模板**。

---

## 16. 关键风险与应对

### 风险 1：PDF 解析不准

应对：

* 做解析对比基准
* 对双栏、表格、图注单独回归测试
* 保留页面截图 fallback

### 风险 2：模型会“过度总结”

应对：

* 所有结论都要求 evidence refs
* 生成前先做 extraction，再做 writing
* 区分 direct support 与 inferred

### 风险 3：相关工作扩展跑偏

应对：

* external search 单独标注
* 限制每轮搜索目标
* 使用关键词与标题联合检索

### 风险 4：系统变成“ChatPDF”

应对：

* 强制输出结构化 schema
* 强制做 evidence binding
* 强制生成报告而不只是 QA

---

## 17. 结论

本系统的核心不是“把 PDF 丢给大模型”，而是构建一个面向论文阅读的、可恢复的、有证据链的工作流系统。技术上，当前 Python 生态已经具备足够的基础设施：PyMuPDF 适合作为高性能 PDF 解析底座，LlamaIndex 与 Haystack 可分别支持 document-centric 与 pipeline-centric 的 Agent 架构，PaperQA 则证明了 scientific literature 任务上“检索 + 引用 + synthesis”的有效性。([PyMuPDF][3])

真正需要你自己构建的护城河，不是框架拼装，而是以下三点：

1. 论文结构理解能力
2. 结论与证据绑定能力
3. 面向研究者/工程师的高质量报告模板体系

如果你愿意，我下一步可以把这份文档继续落到更工程化的一层，直接补一版：
**项目目录结构 + Python 类设计 + FastAPI 接口定义 + MVP 开发清单**。

[1]: https://developers.llamaindex.ai/python/framework/?utm_source=chatgpt.com "Welcome to LlamaIndex ! | LlamaIndex OSS Documentation"
[2]: https://developers.llamaindex.ai/python/framework/use_cases/agents/?utm_source=chatgpt.com "Agents | LlamaIndex OSS Documentation"
[3]: https://pymupdf.readthedocs.io/?utm_source=chatgpt.com "PyMuPDF documentation"
[4]: https://docs.haystack.deepset.ai/docs/agents?utm_source=chatgpt.com "Agents"
[5]: https://github.com/Future-House/paper-qa?utm_source=chatgpt.com "Future-House/paper-qa: High accuracy RAG for answering ..."
[6]: https://haystack.deepset.ai/?utm_source=chatgpt.com "Haystack | Haystack"
