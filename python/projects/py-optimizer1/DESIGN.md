# Optimizer Expert Analyzer Agent 设计文档（多引擎更新版）

## 1. 文档目标

本文档定义一个面向查询优化器源码分析的 Agent 系统设计。系统目标不是做“源码问答”，而是做**源码驱动的、可追踪、可复核、可比较的 Optimizer 深度分析系统**。

系统需要支持如下引擎/框架的统一分析与横向对比：

- ClickHouse
- StarRocks
- Apache Doris
- GPDB / GPORCA
- Apache Calcite
- CockroachDB
- PostgreSQL
- Columbia（研究型框架/原型）

最终输出应包括：

1. 单引擎 Optimizer 的结构化分析结果
2. 基于统一指标体系的 Rule / Trait / Stats / Cost / Observability / Extensibility 解剖结果
3. 多引擎对比矩阵与差异报告
4. 全过程带证据链的 Markdown / JSON 产物

---

## 2. 设计目标与非目标

### 2.1 设计目标

系统需要回答下列问题：

1. 某个引擎的 Optimizer 框架与生命周期是什么？
2. 各阶段有哪些 Rule、Trait、Enforcer、Stats、Cost、Post-Opt 逻辑？
3. 它们在源码中如何实现？
4. 它们如何映射到经典数据库理论：关系代数、logical property、physical property、memo、costing？
5. 与其他引擎相比，哪些能力对齐，哪些缺失，哪些取舍不同？
6. 结论是否具备明确的源码证据？

### 2.2 非目标

当前阶段不追求：

- 自动证明优化器语义正确性
- 自动构造完备的规则覆盖测试集
- 对所有引擎自动生成完全可运行的 benchmark SQL
- 对学术原型和工业代码做“表面平等”的绝对量化打分

---

## 3. 多引擎场景下的核心挑战

### 3.1 引擎异质性极强

这些观察对象并不属于同一类系统：

- **StarRocks / CockroachDB**：明确使用成本优化器（CBO）作为主体。StarRocks 官方文档直接以“cost-based optimizer”与统计信息采集为核心能力；CockroachDB 官方文档明确说明其 optimizer 会枚举大量等价计划并选择最低代价计划。  
- **PostgreSQL**：传统 planner/optimizer + GEQO 作为特定复杂 join 场景下的启发式路径。PostgreSQL 官方文档明确区分常规 planner 与 GEQO。  
- **GPORCA**：Greenplum 中独立于 legacy Postgres planner 的优化器，且官方文档明确存在 ORCA 与 fallback 到 Postgres Planner 的路径。  
- **Apache Calcite / Columbia**：更像优化器框架或研究/中间层，而不是完整数据库执行引擎。Calcite 官方教程明确以 planner rules 和 trait negotiation 为核心；Columbia 在后续研究论文中被直接描述为“基于 Cascades 的 open source top-down optimizer”。  
- **ClickHouse**：需要把“query optimization / analyzer / statistics / execution-oriented heuristics”与传统 Cascades/Volcano 式 rule framework 区分开，避免错误套模。  
- **Doris**：文档层面同时存在发布版本与 dev/unreleased 文档，Nereids 与老优化器共存历史也会影响分析边界。  

因此系统不能假设所有引擎都具备：

- 显式 Memo
- 明确 RBO/CBO 分层
- Trait/Enforcer 体系
- 独立 Post-Optimizer 阶段
- 同粒度的统计信息或 explain/trace 接口

### 3.2 “同名能力”未必同语义

例如：

- “Rule” 在 Calcite 中是 planner rule，在 PostgreSQL 中往往需要从路径构造、join search、predicate pushdown 逻辑中反向抽象，并不总有显式 rule registry。
- “Trait/Property” 在 Cascades/Volcano 系系统里更显式；在其他系统里，可能以 pathkeys、distribution requirement、ordering metadata、physical props 等不同形式存在。
- “Stats” 在不同系统里，粒度、来源、刷新方式、存储位置完全不同。

### 3.3 文档成熟度不一致

- PostgreSQL、CockroachDB、Calcite、StarRocks、ClickHouse 有相对完整公开文档。  
- GPORCA 有产品文档，但源码/文档风格与 PostgreSQL 不一致。  
- Doris 官方 dev 文档会混入 unreleased 内容。  
- Columbia 更多依赖论文、代码和历史资料。  

因此系统必须支持：

- **源码优先**
- **官方文档辅助**
- **论文/历史资料补全**
- **对不确定项显式标注**

---

## 4. 引擎分型与统一比较边界

为了可比性，建议先对观察对象做分型，再在各型内部和跨型间做“受限对比”。

### 4.1 推荐分型

#### A. Cascades / Volcano 风格或接近此风格
- StarRocks
- GPORCA
- Columbia
- Calcite（框架层）
- CockroachDB（虽有自身实现，但在 rule/cost/property 结构上与该类更接近）

#### B. 传统 planner + path enumeration / heuristic + cost mixing
- PostgreSQL
- 部分 Doris 历史路径

#### C. 执行引擎/分析型系统中带有优化器与 analyzer 的混合架构
- ClickHouse
- Doris（现代 Nereids 部分接近 A，但仍需保留过渡复杂性）

### 4.2 比较边界原则

#### 原则 1：先做“结构等价类”对比，再做全局对比
例如：
- Cascades-like 生命周期之间先对比
- PostgreSQL / legacy planner 类之间先对比
- 再在总报告中做“设计哲学差异”总结

#### 原则 2：对“显式实现”与“隐式实现”分开记载
例如 PostgreSQL 中很多能力没有以 rule class 的形式暴露，但不代表能力不存在。

#### 原则 3：对“框架”与“完整产品”分开打标签
Calcite/Columbia 作为框架或研究原型，不应要求其 observability、stats persistence、运维接口与完整数据库同级。

---

## 5. 总体架构

建议系统采用如下架构：

```text
Plan
→ Discover
→ Extract
→ Interpret
→ Verify
→ Persist
→ Compare
→ Report
```

其中：

- **Plan**：基于引擎类型和统一 schema 生成任务图
- **Discover**：定位源码骨架、入口、核心类、目录
- **Extract**：抽取事实，不做解释
- **Interpret**：结合数据库理论解释事实
- **Verify**：验证结论与证据匹配，标出不确定项
- **Persist**：写入标准化 JSON + Markdown
- **Compare**：对不同引擎结果做矩阵化对比
- **Report**：生成人类可读的分析与差异总结

---

## 6. 统一分析 Schema（必须先定义）

这是整个系统的地基。所有引擎都向这套 schema 对齐。

### 6.1 Framework Schema

字段建议：

- `engine_name`
- `engine_type`
- `optimizer_style`
- `main_entry`
- `optimizer_phases`
- `logical_physical_split`
- `memo_or_equivalent`
- `search_strategy`
- `best_plan_selection`
- `post_optimizer_stage`
- `evidence`

### 6.2 Rule Schema

字段建议：

- `rule_id`
- `rule_name`
- `engine`
- `rule_category` (`rbo` / `cbo` / `scalar` / `post_opt` / `implicit`)
- `lifecycle_stage`
- `source_files`
- `registration_points`
- `trigger_pattern`
- `preconditions`
- `transformation_logic`
- `input_operators`
- `output_operators`
- `relational_algebra_form`
- `depends_on_stats`
- `depends_on_cost`
- `depends_on_property`
- `examples`
- `confidence`
- `evidence`

### 6.3 Trait / Property Schema

- `property_name`
- `property_type` (`logical` / `physical`)
- `representation`
- `propagation_logic`
- `enforcer`
- `where_used`
- `impact_on_search`
- `evidence`

### 6.4 Statistics / Cost Schema

- `stats_source`
- `stats_objects`
- `stats_granularity`
- `storage_location`
- `collection_trigger`
- `collection_scheduler`
- `operator_estimation_logic`
- `cost_formula_location`
- `cost_dimensions`
- `evidence`

### 6.5 Observability / Explainability Schema

- `explain_interfaces`
- `trace_interfaces`
- `rule_fire_visibility`
- `memo_dump_support`
- `session_controls`
- `debug_hooks`
- `evidence`

### 6.6 Extensibility Schema

- `rule_extension_path`
- `property_extension_path`
- `cost_extension_path`
- `stats_extension_path`
- `plugin_registration`
- `testing_support`
- `evidence`

---

## 7. Agent 分层设计

不要用一个大 Agent 包打天下，建议拆成以下子 Agent。

### 7.1 Repository Mapper Agent

职责：
- 建立源码地图
- 标识 optimizer 相关目录
- 找到入口类/文件、rule registry、stats/cost/explain 目录
- 提取 call graph 种子

输出：
- `repo_map.json`
- `directory_summary.md`

### 7.2 Lifecycle Analyzer Agent

职责：
- 识别 optimizer 生命周期
- 输出 phase 划分
- 建立 phase 间调用关系
- 标识 logical → physical → best plan → post-opt 路径

输出：
- `framework/lifecycle.json`
- `framework/lifecycle.md`

### 7.3 Rule Miner Agent

拆成四个子类：
- RBO Rule Miner
- CBO Rule Miner
- Scalar Rule Miner
- Post-Optimizer Rule Miner

职责：
- 枚举规则
- 找注册点
- 抽 match/apply 逻辑
- 给出关系代数表达
- 标出依赖 stats/cost/property 的位置

### 7.4 Property & Enforcer Agent

职责：
- 枚举 property/trait/pathkey/distribution/order 等体系
- 分析 propagation / enforcement
- 输出对 plan search 的影响

### 7.5 Statistics & Cost Agent

职责：
- 分析统计信息采集、存储、调度
- 分析 operator-level cardinality / selectivity / cost 评估
- 梳理 cost model 的输入与公式位置

### 7.6 Observability & Extensibility Agent

职责：
- 分析 explain/trace/debug/session knobs
- 分析 rule/property/cost/stats 的扩展路径

### 7.7 Comparison Agent

职责：
- 基于标准 JSON 生成多引擎 comparison matrix
- 识别缺失、异同、取舍
- 生成最终对比报告

### 7.8 Verifier Agent

职责：
- 只负责挑错，不负责重新分析
- 检查 unsupported claims
- 检查证据是否存在
- 检查“猜测”是否被写成“事实”
- 检查 lifecycle 中是否存在断链

---

## 8. 任务重构（对应 Task1 / Task2 / Task3）

---

## 8.1 Task1：指标定义与任务图生成

### 目标

根据统一 schema 和某个引擎的 repo map，生成：

1. 该引擎的分析任务图
2. 各任务对应的证据要求
3. 各任务对应的 prompt 模板
4. 后续 Task2 可执行的 YAML/JSON 任务清单

### 输出

- `artifacts/task_graph.yaml`
- `artifacts/metric_dictionary.json`
- `prompts/*.md`

### 注意事项

- Task1 不直接产出“最终分析报告”
- Task1 负责定义“要分析什么”和“如何采证”
- 对不同引擎的任务图必须尽量同构，但允许“not applicable”

---

## 8.2 Task2：逐任务执行与标准化产物生成

建议拆成 7 个批次：

### Batch A：Framework / Lifecycle
输出：
- `framework/overview.md`
- `framework/lifecycle.md`
- `framework/framework.json`

### Batch B：RBO Rules
输出：
- `rules/rbo/*.md`
- `rules/rbo/index.json`

### Batch C：CBO Rules
输出：
- `rules/cbo/*.md`
- `rules/cbo/index.json`

### Batch D：Scalar Rules
输出：
- `rules/scalar/*.md`
- `rules/scalar/index.json`

### Batch E：Traits / Properties / Enforcers
输出：
- `traits/*.md`
- `traits/index.json`

### Batch F：Post Optimizer
输出：
- `post_optimizer/*.md`
- `post_optimizer/index.json`

### Batch G：Stats / Cost / Observability / Extensibility
输出：
- `stats/*.md`
- `cost/*.md`
- `observability/*.md`
- `extensibility/*.md`
- 对应 `index.json`

### 文档模板建议

每个 Markdown 都必须包含：

1. 概念定义
2. 源码位置
3. 调用链
4. 理论解释
5. 关系代数 / property / cost 表达
6. 证据列表
7. 不确定点
8. 可信度

---

## 8.3 Task3：多引擎对比与差异总结

这阶段不直接自由写长文，而是先自动生成对比矩阵。

### 必备矩阵

1. `rule_coverage_matrix.md/csv`
2. `trait_property_matrix.md/csv`
3. `stats_cost_capability_matrix.md/csv`
4. `observability_matrix.md/csv`
5. `extensibility_matrix.md/csv`
6. `lifecycle_alignment_matrix.md/csv`

### 最终报告结构建议

- 引擎分型与比较边界
- 生命周期差异
- RBO/CBO/Scalar/Post-Opt 规则对齐情况
- Property/Enforcer 差异
- Stats/Cost 差异
- Explain/Trace/Debug 差异
- 扩展性差异
- 设计哲学与工程权衡
- 能力缺失与优势总结

---

## 9. 关键注意事项（这版新增的重点）

### 9.1 不要强行把所有引擎都映射成“同一种 Optimizer”

这是最容易犯的错。

- Calcite 是 planner/optimizer 框架，规则与 trait 非常显式。Calcite 官方教程直接把 planner rules 和 trait negotiation 作为优化核心之一。  
- PostgreSQL 则是 planner + path enumeration + GEQO 的混合模式，很多能力并没有显式 rule class。  
- Greenplum 在 GPORCA 与 legacy planner 之间存在 fallback 路径。  

因此报告里要允许出现：
- `explicitly implemented`
- `implicitly implemented`
- `framework-provided`
- `not applicable`

### 9.2 同一引擎内部可能存在多条 optimizer 路径

重点案例：
- Doris：老优化器与 Nereids 历史并存痕迹可能混杂，且部分 dev 文档是 unreleased。  
- Greenplum：GPORCA 与 Postgres planner fallback 并存。  
- PostgreSQL：标准 planner 与 GEQO 并存。  

因此 repo mapping 阶段必须先确定：
- 哪条路径是主路径
- 哪条路径是 fallback / optional / session-controlled
- 哪些功能只在某条路径下存在

### 9.3 文档版本要冻结

尤其是：
- Doris dev docs 会混入 unreleased 内容
- PostgreSQL 当前文档随版本演进
- ClickHouse/StarRocks 文档持续更新

因此每次分析必须记录：
- 仓库 commit hash
- branch
- 文档版本 / URL
- 分析时间

### 9.4 源码事实和专家解释必须分层

每份输出应分成：

#### Facts from source
#### Interpretation / assessment

这样后续比较或人工复核时，不会把推断和事实混淆。

### 9.5 需要允许“证据不足”的结论

对于 Columbia、部分历史分支、文档缺失模块，必须允许输出：
- `unknown`
- `evidence_missing`
- `needs_manual_review`

而不是强行生成完整故事。

### 9.6 关系代数表达要允许“不完全映射”

很多 Scalar Rule 或物理 property 规则，并不是标准关系代数里的直接等式变换。

因此应允许：
- 经典关系代数表达
- 扩展代数表达（带排序、分发、limit、window、physical properties）
- 若无法严谨映射，则标注“工程表达”

### 9.7 对比报告应区分三种差异

建议明确区分：

1. **设计哲学差异**
2. **工程完成度差异**
3. **功能缺失差异**

否则很容易把“根本就不是同一路线”的引擎误判成“落后”。

### 9.8 对 ClickHouse 要特别注意

ClickHouse 官方文档更强调 analyzer、query optimization guidance、statistics kinds、execution-oriented optimization，而不是把优化器公开包装成典型 Cascades 规则框架。  
因此 ClickHouse 的分析必须允许：
- 更偏 analyzer / planner / storage-aware optimization 的能力拆解
- 不强行要求显式 rule registry / memo / enforcer

### 9.9 对 PostgreSQL / GPORCA 要特别注意

PostgreSQL 官方文档明确描述 planner/optimizer 以 scan path、join path、join order search 等为主，并且 GEQO 是独立启发式路径。Greenplum 官方文档则明确 ORCA 和 fallback 机制。  
因此：
- PostgreSQL 应重点抽 path generation、join search、GEQO、planner stats usage
- GPORCA 应重点抽 cascades-like rule/property/cost/search，同时单独记录 fallback 行为

### 9.10 对 StarRocks / Doris 要特别注意

StarRocks 官方文档明确把 CBO 与统计信息采集作为核心能力，还暴露了 join reorder 相关系统变量。Doris 近年版本与文档中也强调统计信息自动收集和 hints。  
因此这两类引擎要重点分析：
- join reorder
- stats lifecycle
- rule-based rewrite + cost-based implementation split
- explain/trace/session variables

---

## 10. 可靠性保障机制

### 10.1 每条结论必须绑定证据

每个结果都要绑定：
- 文件路径
- 类名 / 函数名
- 行号区间（若可获得）
- 注册点 / 调用点
- 相关测试 / 文档

### 10.2 抽取与解释分离

#### Phase A：Source Fact Extraction
只抽事实

#### Phase B：Semantic Interpretation
再解释成 RBO/CBO/trait/stats/cost 等概念

### 10.3 引入 Verifier

Verifier 要检查：
- 结论是否有源码位置支撑
- 是否把猜测写成事实
- lifecycle 是否断链
- 某 rule 是否只有声明没有实现
- 是否遗漏关联的 property / costing / stats 路径

### 10.4 JSON 作为真相层，Markdown 只是渲染层

- JSON：用于系统内部对比、校验、矩阵生成
- Markdown：用于人类阅读

---

## 11. 目录组织建议

```text
optimizer_analysis/
  engines/
    clickhouse/
      framework/
      rules/
        rbo/
        cbo/
        scalar/
        post_optimizer/
      traits/
      stats/
      cost/
      observability/
      extensibility/
      artifacts/
        repo_map.json
        call_graph.json
        task_graph.yaml
        evidence_index.json
    starrocks/
      ...
    doris/
      ...
    gpdb_orca/
      ...
    calcite/
      ...
    cockroachdb/
      ...
    postgres/
      ...
    columbia/
      ...
  comparison/
    matrices/
    reports/
  schemas/
    framework.schema.json
    rule.schema.json
    trait.schema.json
    stats.schema.json
    cost.schema.json
    observability.schema.json
    extensibility.schema.json
  prompts/
    lifecycle.prompt.md
    rule_interpretation.prompt.md
    scalar_rule.prompt.md
    property_analysis.prompt.md
    stats_cost.prompt.md
```

---

## 12. Prompt 模板设计建议

### 12.1 Rule Interpretation Prompt

输入：
- rule name
- source file
- registration point
- match/apply logic
- involved operators
- nearby tests/comments

输出要求：
1. rule 属于哪类
2. 触发条件
3. 输入模式
4. 输出模式
5. 是否依赖 stats/cost/property
6. 关系代数表达
7. 优化目标
8. 证据列表
9. 不确定点

### 12.2 Property / Trait Prompt

输出要求：
1. property 定义
2. 类型
3. 传播逻辑
4. enforcement 逻辑
5. 对 search space 的影响
6. 源码证据

### 12.3 Stats / Cost Prompt

输出要求：
1. 统计信息来源
2. 采集哪些字段
3. 存储位置
4. 调度逻辑
5. 哪些 operator 消费这些 stats
6. cost 公式位置
7. 对 best plan 的影响
8. 不确定点

---

## 13. 推荐执行路线

### Phase 1：先做 schema + repo mapper

只完成：
- schema 设计
- repo map
- framework/lifecycle 基础抽取
- rule inventory

### Phase 2：完成 rule / trait / stats 抽取

重点：
- rule 分类
- trait/property 分类
- stats/cost 入口识别

### Phase 3：完成关系代数表达与深度解释

重点：
- rule semantics
- algebra mapping
- property semantics
- costing semantics

### Phase 4：引入第二批引擎开始 comparison

推荐顺序：
1. StarRocks / Doris / Calcite / PostgreSQL
2. 再加入 GPORCA / CockroachDB / ClickHouse
3. 最后处理 Columbia 这类研究原型

### Phase 5：完善矩阵与总报告

- 自动矩阵
- 设计哲学差异
- 功能对齐与缺失
- 工程完成度对比

---

## 14. 结论

在加入 ClickHouse、StarRocks、Doris、GPORCA、Calcite、CockroachDB、PostgreSQL、Columbia 之后，这个 Agent 系统的关键不再只是“能不能读源码”，而是：

1. 能否先做正确的引擎分型
2. 能否把异构 optimizer 对齐到统一 schema
3. 能否把事实与解释分层
4. 能否允许 not-applicable / unknown / fallback 路径存在
5. 能否把所有结论绑定到源码证据

真正可靠的方案不是一个“万能 prompt”，而是：

**统一 ontology + Harness 循环 + 分阶段 Agent + Verifier + 标准化产物目录 + 对比矩阵生成。**

只有这样，最终得到的报告才会既详实，又可复核，还能支撑后续多个引擎长期演进对比。

