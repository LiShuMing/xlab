Product Intelligence Agent 设计文档（CLI MVP）

0. 项目目标

构建一个面向 数据 / AI 开发者、产品经理、数据库从业者 的产品情报 agent。
第一阶段聚焦 大数据 / 数据库产品，围绕官方 release notes / changelog / docs / blog 自动抓取最新版本变化，并基于 LLM 生成有深度、有行业背景、有竞品视角的分析报告。
第一阶段交互形式仅提供 terminal CLI，不做 Web UI。

⸻

1. 用户故事

用户故事 1：看某个产品的最新版本分析

作为一名数据库工程师，我希望执行：

pia analyze latest starrocks

然后获得：
	•	该产品最新版本号
	•	本版本的关键变化
	•	技术方向判断
	•	对竞品的影响分析
	•	引用来源

⸻

用户故事 2：分析某个指定版本

作为一名产品经理，我希望执行：

pia analyze version clickhouse 26.2

得到：
	•	该版本的完整分析报告
	•	若本地已分析过，则直接读取缓存结果
	•	若未分析过，则自动抓取并生成

⸻

用户故事 3：查看某个产品的可用版本

pia versions duckdb

输出：
	•	最近 N 个版本
	•	发布时间
	•	来源 URL
	•	是否已缓存分析

⸻

用户故事 4：新增一个产品源

pia product add mydb --config ./products/mydb.yaml

希望系统可以通过一个 markdown/yaml 配置文件增加新产品，而无需改核心代码。

⸻

用户故事 5：生成多产品周报

pia digest weekly --products starrocks,clickhouse,duckdb

输出：
	•	本周变化摘要
	•	重点版本
	•	行业趋势判断
	•	各产品横向对比

⸻

2. MVP 范围

2.1 In Scope

第一阶段只做：
	1.	产品目录管理
	•	支持内置产品：Doris / StarRocks / ClickHouse / DuckDB / Trino / Spark / BigQuery / Snowflake / Databricks
	•	每个产品有一份配置文件，描述：
	•	官网
	•	release notes/changelog 来源
	•	获取版本列表的方法
	•	页面抓取策略
	•	产品类别（open-source / commercial）
	2.	版本发现
	•	抓取产品的 release/changelog 页面
	•	解析出版本号、发布日期、URL、标题
	3.	版本分析
	•	抓取指定版本的原始内容
	•	清洗正文
	•	调用 LLM 生成结构化分析报告
	4.	结果持久化
	•	保存版本元信息
	•	保存清洗后的原文快照
	•	保存分析报告
	•	避免重复分析
	5.	CLI 交互
	•	查询产品
	•	查询版本
	•	分析 latest / 指定版本
	•	列出缓存
	•	重新分析
	•	生成 digest

⸻

2.2 Out of Scope

第一阶段不做：
	•	Web UI
	•	登录态网站抓取
	•	高复杂多 agent 自主规划
	•	自动发邮件 / Slack / 飞书
	•	自治式长期后台任务
	•	自建向量数据库 RAG
	•	自动 PR/commit 级别深挖全部源码

这些可以等 MVP 稳定后再做。

⸻

3. 核心设计原则

3.1 官方来源优先

release notes / changelog / 官方 blog 是一手信号；新闻、第三方评论是二手信号。
分析时必须优先基于官方资料，补充材料只能作为佐证。

3.2 版本是一级实体

这个系统的最小分析单元不是“产品”，而是 产品版本。
每份报告都要绑定：
	•	product_id
	•	version
	•	source_url
	•	source_hash
	•	generated_at
	•	model_id
	•	prompt_version

3.3 可缓存、可重放、可追溯

要能回答：
	•	这份报告基于哪个版本页面生成？
	•	报告是哪个模型、哪个 prompt 生成的？
	•	为什么这次重新分析结果不同？

3.4 先单 agent，后多 agent

MVP 不要一上来堆 supervisor / reviewer / planner 多 agent。
先实现稳定单链路：

discover → fetch → normalize → analyze → persist

后续再在 analyze 阶段内部分裂为多个 specialist agents。

3.5 配置驱动，而不是硬编码

每个产品的抓取行为和 prompt 偏好尽量写在配置里，而不是散落在 Python if/else 中。

⸻

4. 官方数据源建议（第一批内置）

建议内置如下官方入口，作为 seed catalog：
	•	Apache Doris：官方 release notes 总页 / GitHub releases。 ￼
	•	StarRocks：官方 release notes 文档页 / GitHub releases。 ￼
	•	ClickHouse：官方 changelog 页。 ￼
	•	DuckDB：GitHub releases、官方发布博客、release calendar。 ￼
	•	Trino：官方 release notes。 ￼
	•	Spark：官方 news / release pages。 ￼
	•	BigQuery：官方 release notes。 ￼
	•	Snowflake：官方 release notes 总页与 server release notes。 ￼
	•	Databricks：官方 release notes 总页。 ￼

⸻

5. 系统架构

┌─────────────────────────────────────────────────────────┐
│                         CLI                             │
│    analyze / versions / sync / digest / cache / add    │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Application Layer                     │
│  ProductService / ReleaseService / AnalysisService      │
└─────────────────────────────────────────────────────────┘
                         │
         ┌───────────────┼────────────────┐
         ▼               ▼                ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ Source Adapters │ │ LLM Analyzer    │ │ Report Store    │
│ docs/github/rss │ │ prompt + model  │ │ sqlite + files  │
└────────────────┘ └────────────────┘ └────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ Fetch / Parse / Normalize / Diff / Fingerprint          │
└─────────────────────────────────────────────────────────┘


⸻

6. 技术选型建议

6.1 语言

Python 3.11+

理由：
	•	CLI 生态成熟
	•	抓取与 HTML 解析库成熟
	•	LLM SDK 丰富
	•	后续若要接 LangGraph / LiteLLM / OpenAI / Anthropic 很方便

6.2 推荐依赖
	•	CLI：typer
	•	HTTP：httpx
	•	HTML 解析：beautifulsoup4 + lxml
	•	数据模型：pydantic
	•	本地存储：sqlite3 或 sqlmodel/sqlalchemy
	•	Markdown 生成：jinja2
	•	配置：yaml
	•	日志：structlog 或标准 logging
	•	LLM provider 适配：litellm 或自写 provider 层

6.3 为什么 MVP 不建议直接重度上 LangGraph

LangGraph 很适合长流程 agent，但你的第一版重点不是“智能自治”，而是“稳定抓取 + 缓存 + 高质量模板化分析”。
先把业务对象建稳，再决定是否把 analyze 拆成 graph。LangGraph 本身适合后续第二阶段。 ￼

⸻

7. 目录结构建议

product-intel-agent/
├── README.md
├── pyproject.toml
├── src/
│   └── pia/
│       ├── main.py
│       ├── cli/
│       │   ├── analyze.py
│       │   ├── versions.py
│       │   ├── sync.py
│       │   ├── digest.py
│       │   └── product.py
│       ├── config/
│       │   ├── settings.py
│       │   └── loader.py
│       ├── models/
│       │   ├── product.py
│       │   ├── release.py
│       │   ├── report.py
│       │   └── source_doc.py
│       ├── adapters/
│       │   ├── base.py
│       │   ├── github_releases.py
│       │   ├── docs_html.py
│       │   ├── rss.py
│       │   └── manual_page.py
│       ├── services/
│       │   ├── product_service.py
│       │   ├── release_service.py
│       │   ├── fetch_service.py
│       │   ├── normalize_service.py
│       │   ├── analysis_service.py
│       │   ├── digest_service.py
│       │   └── cache_service.py
│       ├── llm/
│       │   ├── provider.py
│       │   ├── prompts.py
│       │   └── schemas.py
│       ├── store/
│       │   ├── db.py
│       │   ├── repositories.py
│       │   └── migrations.py
│       └── utils/
│           ├── versioning.py
│           ├── hashing.py
│           ├── markdown.py
│           └── dates.py
├── products/
│   ├── starrocks.yaml
│   ├── clickhouse.yaml
│   ├── duckdb.yaml
│   └── ...
├── data/
│   ├── app.db
│   ├── raw/
│   ├── normalized/
│   └── reports/
└── tests/


⸻

8. 产品配置文件设计

每个产品一个 YAML。

示例：products/starrocks.yaml

id: starrocks
name: StarRocks
category: open_source
homepage: https://www.starrocks.io/
description: Real-time analytics database

sources:
  - type: github_releases
    url: https://github.com/StarRocks/starrocks/releases
    priority: 100

  - type: docs_html
    url: https://docs.starrocks.io/releasenotes/release-4.0/
    priority: 90

analysis:
  audience:
    - data_engineer
    - database_engineer
    - product_manager
  competitor_set:
    - clickhouse
    - doris
    - trino
  prompt_profile: database_olap

version_rules:
  strategy: semver_loose

设计要点
	•	sources 支持多源，按 priority 排序
	•	analysis.competitor_set 用于后续 prompt 自动带入竞品语境
	•	prompt_profile 用于选择不同产品类型模板，例如：
	•	database_olap
	•	data_platform
	•	lakehouse
	•	query_engine

⸻

9. 数据模型设计

9.1 Product

Product(
  id: str,
  name: str,
  category: str,
  homepage: str,
  description: str,
  config_path: str,
  created_at: datetime,
)

9.2 Release

Release(
  id: str,
  product_id: str,
  version: str,
  title: str,
  published_at: datetime | None,
  source_url: str,
  source_type: str,
  source_hash: str,
  raw_snapshot_path: str,
  normalized_snapshot_path: str,
  discovered_at: datetime,
)

9.3 Report

Report(
  id: str,
  product_id: str,
  release_id: str,
  report_type: str,   # deep_analysis / summary / digest
  model_name: str,
  prompt_version: str,
  content_md: str,
  content_hash: str,
  generated_at: datetime,
)

9.4 SourceDocument

SourceDocument(
  id: str,
  release_id: str,
  url: str,
  title: str,
  kind: str,  # official_release_note / official_blog / news / docs
  content_hash: str,
  local_path: str,
)


⸻

10. 核心工作流

10.1 版本发现工作流

load product config
→ iterate source adapters
→ fetch release index page
→ parse version entries
→ normalize version string
→ upsert releases into sqlite

关键点
	•	一个产品可能有多个源
	•	同一版本可能在 docs 与 GitHub release 同时出现
	•	需要通过 (product_id, normalized_version) 去重

⸻

10.2 单版本分析工作流

input: product + version/latest
→ resolve release
→ check report cache
→ if cache hit and not force:
      return cached report
→ fetch raw source page
→ normalize to clean markdown
→ optional: fetch supplemental official blog/docs
→ build analysis prompt
→ call LLM
→ validate structured output
→ render final markdown
→ persist report
→ print path + summary


⸻

10.3 周报 / digest 工作流

input: products + time window
→ list releases in time window
→ load per-release reports
→ if missing, generate summaries first
→ synthesize cross-product digest
→ persist digest report


⸻

11. 内容抓取与规范化策略

11.1 抓取层

按 source type 使用不同 adapter：

github_releases

适用：
	•	StarRocks
	•	DuckDB
	•	Doris
	•	Trino

策略：
	•	优先使用 GitHub Releases 页面或 API
	•	解析 version、发布日期、body、tag

docs_html

适用：
	•	ClickHouse docs changelog
	•	Snowflake / Databricks / BigQuery release notes
	•	Trino docs release pages
	•	Spark release pages

策略：
	•	抓 HTML
	•	提取主要正文 DOM
	•	转 clean markdown

rss

部分博客可选配

manual_page

用于结构奇怪、需要定制 parser 的产品

⸻

11.2 规范化层

要把不同源站点转成统一的 clean markdown：
	•	去导航、侧边栏、脚注、广告
	•	保留标题层级
	•	保留发布日期
	•	保留 bullet list
	•	尽量保留 PR / issue / commit 链接
	•	给正文计算 hash

输出结构：

NormalizedDoc(
  title: str,
  published_at: datetime | None,
  headings: list[str],
  markdown_body: str,
  extracted_links: list[str],
  content_hash: str,
)


⸻

12. LLM 分析设计

12.1 不建议直接让模型“自由发挥”

建议用两阶段生成：

Stage A：结构化抽取

让模型先抽出：
	•	版本号
	•	核心 feature 列表
	•	performance/optimizer/storage/AI/connector/security/cloud 归类
	•	breaking changes
	•	目标用户
	•	暗示的产品方向

Stage B：专家视角分析

在抽取结果基础上生成长文报告，避免模型在长 release note 上乱飞。

⸻

12.2 推荐输出模板

每个版本分析报告建议固定为：
	1.	TL;DR
	2.	What changed
	3.	Why it matters
	4.	Product direction inference
	5.	Impact on users
	•	data engineer
	•	database engineer
	•	PM / platform owner
	6.	Competitive view
	7.	Potential limitations / caveats
	8.	Raw evidence / links

⸻

12.3 Prompt 设计原则

System Prompt

要求模型扮演：
	•	数据库/大数据领域资深分析师
	•	区分 feature、architecture signal、commercial signal
	•	不夸大，不空话

User Prompt 关键字段

输入必须包含：
	•	product profile
	•	release version
	•	normalized release note markdown
	•	optional supplemental sources
	•	competitor set
	•	audience types
	•	output schema

必须要求模型做的事
	•	区分“显式发布内容”与“推断”
	•	对推断单独标识
	•	输出中保留引用链接
	•	不要把 bugfix 堆成 feature narrative
	•	指出是否只是 patch release

⸻

13. 缓存与去重

13.1 为什么必须缓存

你这个产品天然会反复分析同一个版本。
如果不缓存，成本和延迟都会很差。

13.2 缓存粒度

建议缓存三层：

层 1：raw page cache

按 URL + fetch time 保存原始 HTML

层 2：normalized doc cache

按 source_hash 保存 clean markdown

层 3：report cache

按如下 key 保存：

(product_id, version, report_type, model_name, prompt_version, normalized_hash)

只要输入内容 hash 没变，就不重复生成。

⸻

14. CLI 命令设计

14.1 产品管理

pia product list
pia product show starrocks
pia product add --config ./products/mydb.yaml
pia product validate starrocks

14.2 版本同步

pia sync starrocks
pia sync all

14.3 查看版本

pia versions starrocks
pia versions clickhouse --limit 20

14.4 分析

pia analyze latest starrocks
pia analyze version starrocks 4.0.6
pia analyze latest clickhouse --force
pia analyze version duckdb 1.5.0 --model anthropic/claude-sonnet-4

14.5 digest

pia digest weekly --products starrocks,clickhouse,duckdb
pia digest monthly --category commercial

14.6 缓存

pia cache list
pia cache show starrocks 4.0.6
pia cache purge --product starrocks


⸻

15. MVP 实现优先级

Phase 1：最小可用
	1.	product list
	2.	sync <product>
	3.	versions <product>
	4.	analyze latest <product>
	5.	sqlite + markdown report 持久化

Phase 2：实用化
	1.	多源抓取
	2.	版本去重
	3.	--force
	4.	digest
	5.	报告模板细化

Phase 3：进阶
	1.	竞品横向分析
	2.	增量抓取
	3.	多角色输出风格
	4.	自动补抓官方 blog / docs
	5.	定时任务

⸻

16. 测试策略

单元测试
	•	version normalization
	•	parser correctness
	•	config loading
	•	cache key stability

集成测试
	•	对固定 URL fixture 做抓取 + 规范化
	•	对 mock LLM 输出做端到端测试

回归测试

准备一组已知 release note 样本：
	•	StarRocks
	•	ClickHouse
	•	DuckDB
	•	Trino

校验生成报告是否满足：
	•	结构完整
	•	版本正确
	•	不把 patch release 误判成 major strategy shift

⸻

17. 风险与应对

17.1 风险：不同官网页面结构非常不一致

应对：source adapter + parser profile 配置化，不追求单 parser 通吃。

17.2 风险：商业产品 release notes 常是滚动页面，不是版本页

BigQuery、Snowflake、Databricks 的 release note 更像持续更新流，而不是 GitHub tag 式 release。 ￼
应对：
对这类产品定义“release item”而不是强行要求 semver 版本；MVP 可以先支持：
	•	date-window based item extraction
	•	feature release / platform release item 粒度

17.3 风险：LLM 容易把 patch 夸成战略转向

应对：
先做结构化抽取，再做分析；提示词要求区分 patch / minor / major。

17.4 风险：同一版本在 GitHub release 和文档页内容不同

应对：
按 source priority 合并；保留多个 source document，报告里注明主要依据。

⸻

18. 第二阶段演进方向

当 CLI MVP 跑顺后，再考虑：
	1.	多 agent 分工
	•	release parser agent
	•	domain analyst agent
	•	competitor analyst agent
	•	editor/reviewer agent
	2.	更深的证据链
	•	自动抓 PR / issue / commit
	•	自动抓官方 blog / summit talk
	3.	向量检索
	•	跨版本检索“这个产品最近半年在强化什么方向”
	4.	订阅分发
	•	email/slack/飞书 weekly digest
	5.	Web UI
	•	产品页
	•	版本页
	•	报告对比页
	•	行业趋势页