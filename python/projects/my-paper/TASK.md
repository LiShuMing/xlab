# 基于 Python 构建论文阅读 Agent 的技术设计文档（CLI MVP 版）

## 1. 文档目标

本文档定义一个基于 Python 的论文阅读 Agent，**第一阶段以 Terminal CLI 方式实现 MVP**，不提供 Web 页面。系统面向工程师、研究者与技术调研场景，目标是把单篇论文 PDF 转换为：

* 结构化论文摘要
* 背景、问题、创新点、方法、实验、结果、局限分析
* 关键结论的原文证据绑定
* related work / 后续工作补充
* 报告文章输出

CLI MVP 的设计原则是：

1. **先把核心能力做实，而不是先做界面**
2. **所有分析过程可通过命令行参数组合**
3. **所有输出都落盘，便于重跑、diff、版本管理**
4. **CLI 既是开发接口，也是未来服务化的内核**

---

## 2. 为什么先做 CLI MVP

对于你这个项目，CLI 比 Web 更适合作为第一阶段形态，原因有三点。

### 2.1 更适合研发和快速迭代

论文阅读 Agent 的核心难点不在前端，而在：

* PDF 解析质量
* chunking 策略
* 结构化抽取
* 证据绑定
* related work 扩展
* 报告生成质量

这些都更适合在命令行下快速试错、批量跑、保存中间结果。

### 2.2 更适合“参数驱动”的实验

你后面大概率会频繁调整：

* 模型
* chunk size
* top-k
* 是否开启外部检索
* 输出模板
* 引文风格
* 分析深度

CLI 对这类实验极其友好。

### 2.3 更适合工程化沉淀

CLI MVP 很容易：

* 接入 shell 脚本
* 批量分析论文目录
* 放入 cron / pipeline
* 与 Git 管理输出结果
* 后续封装成服务

所以建议把系统先做成一个类似这样的工具：

```bash
paper-agent analyze paper.pdf --template deep-dive --with-related --output ./out
```

---

## 3. MVP 范围重新定义

## 3.1 MVP 必须具备的能力

CLI 版本先做以下能力：

1. 输入单篇 PDF
2. 自动解析章节、段落、页码
3. 提取论文骨架：

   * 背景
   * 问题定义
   * 创新点
   * 方法概述
   * 实验设置
   * 核心结果
   * 局限
4. 对关键结论尽量附证据
5. 生成 Markdown 报告
6. 生成结构化 JSON 中间结果
7. 通过命令行参数控制行为

## 3.2 MVP 暂不做

第一阶段不做：

* Web 页面
* 用户系统
* 多人协作
* 在线数据库
* 长期记忆
* 多 Agent 自由协作
* 大规模文献综述自动化

---

## 4. CLI 产品形态定义

系统命令暂命名为：

```bash
paper-agent
```

CLI 采用子命令模式，类似 `git`、`docker`、`kubectl`。

---

## 5. CLI 命令设计

建议初始设计以下核心子命令。

## 5.1 `analyze`

用于对单篇论文执行完整分析。

### 示例

```bash
paper-agent analyze ./papers/flashattention.pdf \
  --output ./runs/flashattention \
  --template deep-dive \
  --format md,json \
  --with-related \
  --model gpt-5 \
  --top-k 8
```

### 功能

* 执行完整流程
* 解析 PDF
* 构建索引
* 提取结构
* 生成报告

---

## 5.2 `parse`

只做 PDF 解析，不做后续 LLM 分析。

### 示例

```bash
paper-agent parse ./papers/paper.pdf --output ./runs/paper_parse
```

### 功能

输出：

* 原始文本
* section 信息
* chunk 文件
* 图表 caption
* 表格信息

适合单独调试 PDF 解析质量。

---

## 5.3 `index`

基于解析结果建立本地检索索引。

### 示例

```bash
paper-agent index ./runs/paper_parse --embedding-model text-embedding-3-large
```

### 功能

* 建立向量索引
* 建立 BM25 索引
* 保存 metadata

---

## 5.4 `ask`

对已分析的论文执行问答。

### 示例

```bash
paper-agent ask ./runs/flashattention \
  --question "What is the key innovation and what evidence supports it?" \
  --format md
```

### 功能

* 加载已有索引
* 检索相关 chunk
* 生成带引用回答

---

## 5.5 `report`

基于已有分析结果生成不同风格报告。

### 示例

```bash
paper-agent report ./runs/flashattention \
  --template blog \
  --output ./runs/flashattention/blog_report.md
```

### 支持模板

* `summary`
* `deep-dive`
* `blog`
* `group-talk`
* `interview-note`

---

## 5.6 `related`

只做 related work 扩展。

### 示例

```bash
paper-agent related ./runs/flashattention \
  --max-papers 10 \
  --output ./runs/flashattention/related.json
```

### 功能

* 基于论文标题、摘要、关键词检索相关工作
* 输出相关论文与关系说明

---

## 5.7 `batch-analyze`

对一个目录下的多篇论文批量执行分析。

### 示例

```bash
paper-agent batch-analyze ./papers \
  --glob "*.pdf" \
  --output ./runs/batch \
  --template summary
```

### 功能

* 批量处理目录中的 PDF
* 每篇单独生成结果目录

---

## 6. CLI 参数设计

CLI 的价值很大程度上来自参数设计。建议参数分为 6 类。

---

## 6.1 输入输出参数

### 常用参数

* `input`：输入 PDF 文件路径或分析目录
* `--output, -o`：输出目录
* `--format`：输出格式，支持 `md,json,text`
* `--force`：覆盖已有输出
* `--cache-dir`：缓存目录
* `--run-name`：指定本次运行名称

### 示例

```bash
paper-agent analyze paper.pdf -o ./runs/p1 --format md,json --force
```

---

## 6.2 模型参数

* `--model`：主 LLM 名称
* `--embedding-model`：embedding 模型
* `--temperature`
* `--max-tokens`
* `--timeout`
* `--provider`：openai / anthropic / local / custom

### 示例

```bash
paper-agent analyze paper.pdf \
  --model gpt-5 \
  --embedding-model text-embedding-3-large \
  --temperature 0.1
```

---

## 6.3 解析参数

* `--parser`：`pymupdf` / `pdfplumber` / `auto`
* `--chunk-size`
* `--chunk-overlap`
* `--section-aware`
* `--extract-figures`
* `--extract-tables`
* `--skip-references`

### 示例

```bash
paper-agent parse paper.pdf \
  --parser pymupdf \
  --chunk-size 1200 \
  --chunk-overlap 150 \
  --section-aware \
  --extract-figures
```

---

## 6.4 检索参数

* `--top-k`
* `--retrieval-mode`：`vector` / `bm25` / `hybrid`
* `--rerank`
* `--section-filter`
* `--include-figures`
* `--include-tables`

### 示例

```bash
paper-agent ask ./runs/p1 \
  --question "What are the main limitations?" \
  --retrieval-mode hybrid \
  --top-k 6 \
  --section-filter conclusion,discussion
```

---

## 6.5 分析参数

* `--template`
* `--analysis-depth`：`fast` / `standard` / `deep`
* `--with-related`
* `--with-critique`
* `--with-followup`
* `--citation-style`
* `--focus`：`system` / `method` / `experiment` / `theory`

### 示例

```bash
paper-agent analyze paper.pdf \
  --template deep-dive \
  --analysis-depth deep \
  --with-related \
  --with-critique \
  --focus experiment
```

---

## 6.6 调试与工程参数

* `--verbose`
* `--dry-run`
* `--save-trace`
* `--save-prompts`
* `--resume`
* `--from-stage`
* `--to-stage`

### 示例

```bash
paper-agent analyze paper.pdf \
  --save-trace \
  --save-prompts \
  --resume
```

---

## 7. CLI 输出目录结构设计

每次运行都应生成一个独立目录，便于追踪与 diff。

### 推荐结构

```text
runs/
  flashattention/
    metadata.json
    config.json
    raw_text/
      pages.json
      sections.json
    parsed/
      chunks.jsonl
      figures.json
      tables.json
    index/
      faiss.index
      bm25.pkl
      metadata.db
    extracted/
      paper_schema.json
      evidence.json
      related.json
    reports/
      summary.md
      deep_dive.md
      blog.md
    traces/
      stage_parse.json
      stage_extract.json
      stage_report.json
    prompts/
      extract_prompt.txt
      report_prompt.txt
```

### 设计意义

这样做可以：

* 明确区分中间结果与最终结果
* 支持从任一阶段恢复
* 支持版本管理
* 便于测试不同参数效果

---

## 8. 系统模块设计（CLI 视角）

CLI-first 版本仍然保留之前的核心模块，但实现上全部围绕命令行工作流展开。

---

## 8.1 CLI Entry 模块

### 职责

* 解析命令行参数
* 校验参数合法性
* 构建运行配置
* 分发到对应子命令逻辑

### 技术建议

推荐用：

* `typer`：更适合现代 Python CLI，类型提示友好
* 或 `click`

### 示例目录

```text
paper_agent/
  cli/
    main.py
    commands/
      analyze.py
      parse.py
      ask.py
      report.py
      related.py
```

---

## 8.2 Config 模块

### 职责

统一管理：

* CLI 参数
* 默认配置
* 环境变量
* 模型配置
* 路径配置

### 设计建议

配置优先级：

1. CLI 参数
2. 项目配置文件
3. 环境变量
4. 默认值

### 可选配置文件

支持：

```bash
paper-agent analyze paper.pdf --config config.yaml
```

`config.yaml` 示例：

```yaml id="3r2zvz"
model: gpt-5
embedding_model: text-embedding-3-large
chunk_size: 1200
chunk_overlap: 150
retrieval_mode: hybrid
template: deep-dive
with_related: true
save_trace: true
```

---

## 8.3 Pipeline Runner 模块

### 职责

CLI 中最关键的执行器。它负责把完整分析拆成阶段执行。

### 阶段定义

* `parse`
* `chunk`
* `index`
* `extract`
* `bind_evidence`
* `related`
* `report`

### CLI 支持

允许指定：

```bash
paper-agent analyze paper.pdf --from-stage extract --to-stage report --resume
```

这对于调试非常重要。

---

## 8.4 Document Parser 模块

同前版设计，但要强调它必须支持 CLI 独立调用。

### CLI 行为

```bash
paper-agent parse paper.pdf -o ./runs/p1
```

### 输出

* `pages.json`
* `sections.json`
* `chunks.jsonl`
* `figures.json`
* `tables.json`

### 设计要求

Parser 的输出必须是稳定的本地文件，而不是只驻留内存。
因为 CLI MVP 的核心之一就是“中间状态可见”。

---

## 8.5 Retrieval / Index 模块

### 职责

* 建立本地索引
* 支持 ask / extract / report 阶段复用

### CLI 行为

```bash
paper-agent index ./runs/p1 --retrieval-mode hybrid
```

### 输出

* `faiss.index`
* `bm25.pkl`
* `chunk_metadata.json`

---

## 8.6 Extractor 模块

### 职责

从解析后的论文中抽取结构化结果。

### 输出

* `paper_schema.json`
* `claims.json`
* `evidence.json`

### CLI 设计思路

虽然它通常由 `analyze` 间接调用，但也建议支持独立执行：

```bash
paper-agent extract ./runs/p1
```

这样后续调试会轻很多。

---

## 8.7 Report Writer 模块

### 职责

根据结构化结果生成不同风格报告。

### CLI 行为

```bash
paper-agent report ./runs/p1 --template deep-dive
```

### 输出

* `reports/deep_dive.md`
* `reports/blog.md`
* `reports/summary.md`

---

## 8.8 Related Work 模块

### 职责

做外部扩展。

### CLI 行为

```bash
paper-agent related ./runs/p1 --max-papers 8
```

### 说明

MVP 阶段可以把它设计为**可选模块**，避免一开始就把系统复杂度拉高。

---

## 9. 核心工作流设计（CLI MVP）

CLI MVP 的核心不是“一个命令跑完”，而是“一个总命令 + 一组可单独调用的阶段命令”。

### 标准全流程

```text
analyze
  -> parse
  -> chunk
  -> index
  -> extract
  -> bind evidence
  -> related (optional)
  -> report
```

### 用户常见使用方式

#### 场景 1：一键分析

```bash
paper-agent analyze paper.pdf -o ./runs/p1 --template deep-dive --with-related
```

#### 场景 2：先看解析质量

```bash
paper-agent parse paper.pdf -o ./runs/p1
```

#### 场景 3：复用已有结果生成不同报告

```bash
paper-agent report ./runs/p1 --template blog
paper-agent report ./runs/p1 --template group-talk
```

#### 场景 4：针对某个问题问答

```bash
paper-agent ask ./runs/p1 --question "What assumptions does this method rely on?"
```

---

## 10. 项目目录结构设计（CLI 优先）

推荐工程目录如下：

```text
paper-agent/
  pyproject.toml
  README.md
  configs/
    default.yaml
  paper_agent/
    __init__.py
    cli/
      main.py
      commands/
        analyze.py
        parse.py
        index.py
        extract.py
        ask.py
        report.py
        related.py
    core/
      config.py
      runner.py
      state.py
      paths.py
    parser/
      pdf_parser.py
      section_detector.py
      chunker.py
      figure_extractor.py
      table_extractor.py
    retrieval/
      embeddings.py
      vector_store.py
      bm25_store.py
      hybrid_retriever.py
      reranker.py
    extraction/
      paper_schema.py
      claim_extractor.py
      evidence_binder.py
      experiment_extractor.py
    report/
      templates.py
      writer.py
      markdown_renderer.py
    research/
      related_search.py
      followup_search.py
    llm/
      client.py
      prompts.py
      models.py
    storage/
      artifact_store.py
      metadata_store.py
    utils/
      logging.py
      hashing.py
      io.py
  tests/
  runs/
```

---

## 11. 数据与状态管理（CLI 版本）

因为没有 Web 服务，CLI MVP 需要特别强调**本地状态管理**。

## 11.1 状态存储方式

每次运行以目录作为一次 run 的边界，所有状态都以文件形式保存。

### 必须保存的内容

* `config.json`
* `metadata.json`
* 阶段输出
* trace
* prompts
* final reports

### 优点

* 易于 Git 管理
* 易于回滚
* 易于比较不同参数运行结果
* 无需一开始引入服务端数据库

---

## 11.2 Resume 机制

CLI 设计中建议加入：

```bash
--resume
```

含义：

* 若输出目录已存在且某阶段结果已完成，则跳过
* 若某阶段失败，则从失败阶段继续

这对长论文或启用 related work 时很有用。

---

## 12. Prompt / 模板设计（CLI 版）

CLI MVP 特别适合 prompt 实验，因此建议 prompt 外置、可保存。

### 设计要求

* 支持 `--save-prompts`
* 支持 `--prompt-dir`
* 支持不同模板使用不同 prompt

### 目录建议

```text
paper_agent/llm/prompts/
  extract_contribution.txt
  extract_experiment.txt
  report_summary.txt
  report_deep_dive.txt
  ask_with_citation.txt
```

### CLI 示例

```bash
paper-agent analyze paper.pdf \
  --template deep-dive \
  --save-prompts
```

---

## 13. 日志、调试与可观测性

CLI MVP 虽然没有页面，但不能没有可观测性。

### 必须具备

* 控制台日志
* 文件日志
* 每阶段耗时
* 模型调用耗时
* 失败阶段记录
* 检索命中 chunk 输出

### 建议参数

* `--verbose`
* `--debug`
* `--save-trace`

### 示例

```bash
paper-agent analyze paper.pdf --debug --save-trace
```

---

## 14. 测试策略（CLI-first）

CLI MVP 的测试要分三层。

## 14.1 单元测试

针对：

* 参数解析
* chunking
* section detection
* evidence binder
* markdown renderer

## 14.2 集成测试

针对：

* `parse`
* `index`
* `extract`
* `report`

每个命令都应能在测试 PDF 上完成端到端执行。

## 14.3 黄金样本测试

准备若干论文作为 golden set，保存其期望输出：

* `paper_schema.json`
* 若干关键 claims
* 若干 expected citations

这样后续调 prompt、换模型时，能快速看质量是否回退。

---

## 15. MVP 开发路线（CLI 版本）

## Phase 1：CLI 骨架

目标：

* 完成 `paper-agent` 主命令
* 支持 `analyze / parse / ask / report`
* 完成参数解析与配置管理

## Phase 2：解析与本地索引

目标：

* PyMuPDF 解析
* chunking
* 本地 BM25 + 向量索引
* 输出本地 artifacts

## Phase 3：结构化抽取与证据绑定

目标：

* 输出 `paper_schema.json`
* 输出 `evidence.json`
* 初版 Markdown 报告

## Phase 4：Related work 与增强模板

目标：

* 增加 `related`
* 增加 `blog / group-talk / interview-note`
* 增加批处理

---

## 16. 为什么这种 CLI-first 设计是对的

这个项目真正的护城河不在网页，而在：

* PDF 解析质量
* 结构化理解质量
* 证据绑定能力
* 报告模板质量
* related work 扩展的准确性

CLI-first 方案的好处是：

### 16.1 技术聚焦

你不会过早陷入：

* 前端页面
* 用户管理
* Web API 状态管理
* 部署与鉴权

### 16.2 更适合你这种工程师风格

你本身更偏系统、工具、流程、批处理思维。
CLI 工具更符合：

* 参数化实验
* Shell 集成
* 输出落盘
* 稳定迭代

### 16.3 未来扩展自然

将来要做 Web，只需要把 CLI 的核心 pipeline 再封成 service layer。
不需要推翻重来。

---

## 17. 最终建议的 MVP 命令形态

如果只保留最小可用的一组命令，我建议先做这四个：

```bash
paper-agent parse <pdf> -o <dir>
paper-agent analyze <pdf> -o <dir> --template deep-dive
paper-agent ask <run_dir> --question "<text>"
paper-agent report <run_dir> --template blog
```

再逐步加：

```bash
paper-agent related <run_dir>
paper-agent batch-analyze <dir>
paper-agent extract <run_dir>
paper-agent index <run_dir>
```

---

## 18. 结论

本项目第一阶段应明确采用 **Terminal CLI-first** 的产品形态，而不是 Web-first。
CLI 不是临时过渡方案，而是最适合该类“研究工作流工具”的起点形态。它能最大化聚焦真正困难的部分：解析、检索、抽取、证据绑定与报告生成；同时为后续服务化和可视化保留足够清晰的边界。