Incremental View Maintenance (IVM) 技术调研报告

面向数据库内核工程师：Snowflake / Databricks / BigQuery / StarRocks + 学术前沿 + StarRocks 落地建议

⸻

1. Executive Summary

这份报告的核心结论可以先摆在桌面上，免得大家在 IVM 丛林里被树枝抽脸：

第一，工业界主流“增量计算”方案，本质上已经明显分成了三条路线。
Snowflake Dynamic Tables 走的是 declarative pipeline + automatic IVM + delayed freshness semantics（声明式流水线 + 自动增量维护 + 延迟视图语义），强调的是“用户写 SQL，系统决定刷新节奏、增量/全量策略与 DAG 编排”；Databricks Materialized View 则更偏 transaction log / row tracking / change data feed 驱动的 best-effort incrementalization（基于 Delta/Iceberg 变更日志与行跟踪的尽力增量化），并允许通过 refresh policy 显式控制“失败 / 回退 / 强制全量”；BigQuery Materialized View 本质上仍是 optimizer-integrated MV（深度绑定优化器的物化视图），其核心卖点是 smart tuning（自动重写）+ query-time compensation（查询时补偿未刷新的 base-table 变化）。StarRocks 当前的 Async MV 更像是 partition-level selective recomputation（分区级选择性重算）+ rewrite-first acceleration（以改写加速为中心），而不是严格意义上的通用、细粒度 delta-based IVM。 ￼

第二，真正困难的地方并不在“把 append-only 聚合做增量”，而在 non-monotonic operators（非单调算子）：例如 outer join、window function、COUNT DISTINCT、top-N / rank、非确定函数、子查询、复杂 set operator。工业系统的共同现实是：
越接近 full SQL，越需要额外状态、日志、约束、重算回退或语义降级。 Snowflake 通过“支持表 + unsupported ⇒ full refresh”来兜底；Databricks 通过 row tracking / deletion vectors / CDF / refresh policy 来把“可增量化”与“可工程化”绑定；BigQuery 干脆把 incremental MV 与 non-incremental MV 拆开，承认复杂 SQL 需要整视图刷新。这个分界线，不是产品经理保守，而是理论和工程账本共同抽出来的。 ￼

第三，近五年学术界的重要趋势，不再只是“写 delta 公式”，而是三类升级：
一类是 generalized IVM models（广义 IVM 语义模型），例如 DBSP 把 IVM 提升为“stream derivatives（流上的导数）”，覆盖 relational algebra、nested relations、aggregation、unnest、monotonic / non-monotonic recursion；
一类是 fine-grained complexity / optimality（细粒度复杂度与最优性），开始回答“哪些查询不可能同时做到低更新代价 + 低枚举延迟”；
另一类是 specialized operator research（特殊算子专门算法），例如 window / holistic aggregate、foreign-key-aware IVM、factorized IVM。学术界在告诉工业界：通用 IVM 没有银弹，必须依赖 query class、constraints、state layout、update pattern 与 cost model 的协同。 ￼

第四，对 StarRocks 的现实建议不是“一步到位做全 SQL IVM”，那会很像试图用一把螺丝刀修整台核反应堆。更可行的路线是：
Phase 1：从“partition refresh + query rewrite”升级到“operator-scoped incremental refresh（限定算子族的增量刷新）”；
Phase 2：引入 lightweight delta state（轻量 delta 状态）和 refresh planner（刷新规划器）；
Phase 3：围绕 SPJG + append-friendly aggregate + limited outer join/window 建立严格的可增量化边界与 explainability（可解释性）。
这条路最贴合 StarRocks 当前架构与工程收益。 ￼

⸻

2. IVM 理论基础

2.1 什么是 IVM

Incremental View Maintenance (IVM，增量视图维护) 的目标是：
给定视图 V = Q(D)，当底表发生更新 ΔD 后，不是重新计算 Q(D + ΔD)，而是直接计算一个更便宜的 ΔV，再令：

V' = V \oplus \Delta V

其中 ⊕ 可以是 bag union（袋并）、upsert、delete+insert、或更一般的 semiring/ring 上更新。DBSP 2023 明确把这个问题提升为“对数据流求导”的统一框架，能够表示 relational algebra、aggregation、unnest、nested relations，甚至单调与非单调递归。 ￼

2.2 代数视角：单调 vs 非单调

从内核实现角度，最关键的不是 SQL 长得多华丽，而是查询是否 monotonic（单调）。

单调查询：输入追加不会导致旧结果失效，只会增加新结果。典型如：
	•	SELECT ... FROM T WHERE ...
	•	GROUP BY 上的 SUM/COUNT（在 bag 语义且只追加时）
	•	某些 equi-join（在只追加条件下）

非单调查询：输入更新可能导致已有结果需要撤销、重写或重新排序。典型如：
	•	DISTINCT
	•	COUNT DISTINCT
	•	MIN/MAX（在 delete/update 下）
	•	OUTER JOIN
	•	RANK/ROW_NUMBER/TopN
	•	NOT EXISTS / anti-join
	•	很多 window function

Flink 的 changelog model 把这个事情说得很直白：table 本质上是 INSERT/UPDATE/DELETE 流，持续查询要维护结果表，就得能发出对应的 retract/update。也就是说，非单调不是“不能做”，而是要求系统具备更强的状态和回撤机制。 ￼

2.3 理论下界与工程含义

近年的 IVM 理论研究，一个重要方向是问：
哪些查询，根本不可能在任意更新下都保持极低 update cost？

2024 年的综述《Recent Increments in Incremental View Maintenance》总结了 fine-grained complexity 路线：研究重点已经不是“能不能增量”，而是“在 preprocessing / update time / enumeration delay 之间的最优 trade-off 是什么”。这意味着工业系统里常见的“某些 SQL 不支持增量、或必须退回全量”并不是实现偷懒，很多时候是理论边界在敲锣。 ￼

2.4 三种常见工程实现范式

范式 A：Delta algebra / higher-order IVM
代表：DBToaster、F-IVM、DBSP。
思路是把查询递归求 delta，甚至 materialize higher-order deltas。优点是理论漂亮，局部查询类上更新极快；缺点是状态爆炸、编译复杂、对 full SQL/工程系统集成成本高。DBToaster 2014 与 F-IVM 2024 都属于这条线。 ￼

范式 B：Change-log driven maintenance
代表：Flink changelog、Databricks Delta/CDF/row-tracking。
系统围绕变更日志、主键/row-id、update-before/update-after 做维护。优点是工程闭环强，适合流批融合；缺点是对 source format、row identity、状态管理依赖重。 ￼

范式 C：Selective recomputation / hybrid maintenance
代表：BigQuery incremental MV、StarRocks partition refresh、Snowflake AUTO/full fallback。
核心不是追求 every-row delta，而是尽量缩小重算范围、并让优化器或刷新调度器决定何时使用 materialized result。优点是工程可控、上线快；缺点是“严格 delta IVM”能力较弱。 ￼

⸻

3. 工业界现状

⸻

3.1 Snowflake Dynamic Tables

3.1.1 架构定位

Snowflake 将 Dynamic Tables 定位为 declarative streaming transformation primitive（声明式流式转换原语）。官方文档强调它们基于查询定义和 target lag 自动刷新；2024 年 4 月已 GA。Snowflake 在 2025 论文中进一步提出 Delayed View Semantics (DVS，延迟视图语义)：DT 的内容保证等价于“过去某个时间点”的逻辑视图，并通过 automatic IVM 实现秒到小时级延迟范围的 declarative pipeline。 ￼

3.1.2 增量机制

Snowflake 的增量刷新依赖两个关键点：

其一，change tracking（变更跟踪）。
增量模式下，所有底层对象都需要开启 change tracking 且 time travel retention 非零；创建 dynamic table 时若底表未开启，系统会尝试自动开启。 ￼

其二，target lag + DAG scheduling（目标滞后 + DAG 调度）。
Dynamic table 由 target lag 驱动刷新；DOWNSTREAM 可让整个 DAG 由下游驱动，最末端表手动 refresh 时会连带刷新上游依赖。Snowflake 明说 target lag 是目标不是保证，实际 lag 会受 warehouse 大小、数据量和 query complexity 影响。 ￼

从系统语义看，它不是要求用户手写 Stream + Task；Snowflake 官方明确对比说，dynamic table 自动完成本来需要 stream + task + MERGE 的增量处理。 ￼

3.1.3 Refresh mode 与状态

Snowflake 支持 AUTO / INCREMENTAL / FULL 三种刷新模式。
AUTO 在创建时一次性决定实际模式；若 incremental 不支持或预计性能差，则选择 full。这个“只在创建时决定一次”的语义非常重要——避免运行时模式抖动，但也让 schema / query 变化后的 reinitialize 更明显。官方 troubleshooting 文档还明确说 actual refresh mode creation-time immutable（创建后不可变）。 ￼

3.1.4 支持算子矩阵（截至 2026-03）

根据官方“Supported queries”文档，Dynamic Tables 的 incremental refresh 当前支持：
	•	DISTINCT
	•	GROUP BY
	•	CROSS JOIN
	•	UNION ALL
	•	UNION（2025-08 起支持，语义等于 UNION ALL + SELECT DISTINCT）
	•	许多 deterministic built-in functions 与 immutable UDF
	•	certain lateral flatten 场景（但不能选 SEQ 列） ￼

不支持或有限支持的包括：
	•	subquery operators（例如 WHERE EXISTS 一类子查询）
	•	MINUS / EXCEPT / INTERSECT
	•	PIVOT / UNPIVOT
	•	SAMPLE
	•	sequences
	•	外部函数
	•	某些 outer join 形态（例如双方都是带 GROUP BY 的子查询、或 non-equality outer join） ￼

状态判断：
	•	Dynamic Tables 整体：GA（2024-04） ￼
	•	UNION incremental support：GA/已发布特性（2025-08 release note） ￼
	•	dual warehouse for init/reinit：已发布特性（2025-12） ￼

3.1.5 Limitations 与本质瓶颈

Snowflake 的瓶颈很典型：

一是 语义复杂度换成 mode fallback。
只要 query construct 超出 incremental envelope，就退回 full refresh。这个设计很务实：不在运行时制造半吊子错觉。 ￼

二是 DVS 语义不是“最新快照”，而是“过去某个一致时间点的视图”。
这比传统 streaming upsert log 更容易 reasoning，但也说明它不是毫秒级 CEP 式系统，而是为 seconds-to-hours 延迟区间设计。 ￼

三是 某些 source/schema/policy 变化触发 reinitialization。
替换上游对象、依赖 schema 变化、policy 变化、clone/replication 场景都可能让 incremental state 失效，回到初始化。 ￼

一句话评价：
Snowflake 的强项不是“全 SQL delta algebra”，而是“用较强的语义包装 + 自动调度 + 增量/全量二选一”把 IVM 产品化了。

⸻

3.2 Databricks Materialized View

3.2.1 架构定位

Databricks 的 Materialized View 现在明显已经嵌入 Lakeflow Spark Declarative Pipelines / serverless pipelines 体系。GCP 文档写得很清楚：MV 元数据保存在 Unity Catalog，缓存数据 materialize 在 cloud storage，同时系统会创建 internal tables 支撑 incremental refresh。这个味道很 Databricks：底层是日志与 pipeline，不是单纯 optimizer cache。 ￼

3.2.2 增量机制

Databricks 官方文档把 incremental refresh 描述为 best-effort attempt（尽力尝试）：
刷新时检测 source change，并只处理新变更；若不能 incrementalize，就 full recompute。并且——这个点很关键——incremental refresh 只在 serverless compute / serverless pipelines 下可用。classic compute 上 MV 会全量重算。 ￼

其可增量化能力高度依赖底层数据源特征。官方推荐在 source table 上开启：
	•	Deletion Vectors
	•	Row Tracking
	•	Change Data Feed
并明确说某些 incremental refresh 操作需要 row tracking；支持的 source 包括 Delta tables、materialized views、streaming tables、Unity Catalog managed Iceberg tables（v2/v3，推荐 v3）。 ￼

这意味着它走的是典型 log/state-aware IVM：
不是仅凭 SQL 公式做静态改写，而是依赖底层 format/runtime 暴露足够强的 row identity 和 mutation metadata。

3.2.3 支持算子矩阵

Databricks 2026 文档给了非常明确的 incremental refresh support table。已支持的包括：
	•	SELECT expressions（deterministic built-in + immutable UDF）
	•	GROUP BY
	•	WITH / CTE
	•	UNION ALL
	•	WHERE / HAVING
	•	INNER JOIN
	•	LEFT OUTER JOIN
	•	FULL OUTER JOIN
	•	RIGHT OUTER JOIN
	•	OVER window functions（但需要指定 PARTITION_BY 才能 incrementalize）
	•	QUALIFY
	•	EXPECTATIONS（部分场景例外） ￼

这份矩阵比大多数工业文档都“胆大”。但别急着鼓掌到把桌子拍裂，因为它同时配套了：
	•	unsupported ⇒ full recompute
	•	REFRESH POLICY 可设 AUTO / INCREMENTAL / INCREMENTAL STRICT / FULL
	•	INCREMENTAL STRICT 下若无法增量化则直接失败，而不是偷偷回退全量 ￼

官方还暴露了实际采用的刷新技术标签：
	•	ROW_BASED
	•	PARTITION_OVERWRITE
	•	WINDOW_FUNCTION
	•	APPEND_ONLY
	•	GROUP_AGGREGATE
	•	GENERIC_AGGREGATE
这说明 Databricks 内部不是一个单一算法，而是 多种 maintenance technique 的 planner/dispatcher。 ￼

状态判断：
	•	Incremental refresh for MV：Public Preview（截至 2026-02 文档） ￼
	•	EXPLAIN CREATE MATERIALIZED VIEW：Beta，可用于判断 query 是否 incrementalizable。 ￼

3.2.4 Limitations 与本质瓶颈

Databricks 官方自己已经把红线写出来了：
	•	full refresh 代价高的场景，推荐直接用 streaming tables 保证 exactly-once，而不是 MV；
	•	对“只应处理一次”的 source（Kafka、Auto Loader、会删历史的 ingest table），不建议用 MV；
	•	带 row filters / column masks 的 source 不支持 incremental refresh；
	•	UDF 行为变化时，系统可能无法完全感知，需要用户主动做 full refresh。 ￼

所以 Databricks 的真实定位不是“MV 万能论”，而是：

对适合批式语义、但底层有足够变更元数据的查询，尽力增量；
对严格流语义或 once-only 数据，转向 streaming tables。

这是很健康的边界感。很多系统把所有东西都叫 MV，最后把用户送进 semantic swamp（语义沼泽）。

一句话评价：
Databricks 在工业系统里，对“operator-scoped incrementalization + policy-controlled fallback”这件事，走得相当靠前；但它的代价是对底层表格式、serverless runtime、日志能力有明显绑定。

⸻

3.3 BigQuery Materialized View

3.3.1 架构定位

BigQuery 的物化视图是 optimizer-integrated MV 的典型代表。
官方文档突出三点：
	•	automatic refresh
	•	fresh data via base-table compensation
	•	smart tuning（自动重写）：查询 base table 时也可被重写到 MV。 ￼

BigQuery 的特别之处在于，它不是简单地“MV 只返回上次刷新结果”。对于 incremental MV，如果 base table 的新变化不会 invalidate MV，BigQuery 会读 MV + base-table delta 来返回 fresh result；如果变化会 invalidate，则回读 base tables。这个设计让它在用户体验上非常丝滑，也很像 optimizer-driven hybrid maintenance。 ￼

3.3.2 Incremental vs Non-incremental 二分

BigQuery 现在明确区分两类：
	•	Incremental materialized views：支持有限 SQL，支持 smart tuning，且“always fresh”语义通过 query-time compensation 实现。
	•	Non-incremental materialized views：allow_non_incremental_definition = true，支持更复杂 SQL，但每次 refresh 是整视图刷新；不支持 smart tuning。 ￼

这是一种非常清醒的产品分层：
复杂性别硬塞进增量引擎，直接拆型。

3.3.3 支持与限制

官方文档显示，incremental MV 使用受限 SQL 语法；而一些复杂能力被列为不支持或 preview：
	•	RIGHT/FULL OUTER JOIN：不支持增量 MV
	•	self-join：不支持
	•	window functions：不支持增量 MV
	•	ARRAY subquery、non-deterministic functions、UDF、TABLESAMPLE、FOR SYSTEM_TIME AS OF、Generative AI functions：不支持增量 MV
	•	LEFT OUTER JOIN 与 UNION ALL：Preview 支持，但 smart tuning 不支持。 ￼

另外，non-incremental MV：
	•	支持 OUTER JOIN / UNION / HAVING / analytic functions
	•	但必须整视图刷新
	•	不支持 smart tuning
	•	一般需要 max_staleness 配置，且更适合容忍 staleness 的批报表场景。 ￼

BigQuery 还明确说：
	•	MV 不能嵌套在其他 MV 上
	•	不能查询 external / wildcard tables、logical views（logical view reference 仅 Preview）、snapshots
	•	SQL 定义创建后不能修改。 ￼

3.3.4 Smart Tuning 与“新鲜结果”

BigQuery 的独门招牌是 smart tuning。2025 年 release note 说明 smart tuning 对某些跨项目场景已 GA；而 MV intro 文档也强调：incremental MV 的重要价值就是支持 smart tuning 和 fresh result。 ￼

但这里有个微妙点：
并非所有 incremental MV 都享受 smart tuning。
LEFT OUTER JOIN / UNION ALL preview incremental MV 明确不支持 smart tuning；non-incremental MV 也不支持。这个边界非常重要，否则用户会误以为“只要建了 MV，优化器一定自动吃上”。现实没这么童话。 ￼

3.3.5 代价模型

BigQuery 文档还给了很坦率的成本模型：
	•	query cost：读取 MV + 必要时读取 base tables
	•	maintenance cost：refresh 时处理的 bytes / slots
	•	storage cost：MV 自身存储
	•	某些 aggregate（如 AVG / APPROX_COUNT_DISTINCT）底层以 proprietary sketch/intermediate bytes 存储，而不是直接存最终值。 ￼

这意味着 BigQuery 的“增量”并不是零成本魔法，而是把 compute、storage、optimizer rewrite 和 freshness compensation 绑成一套账。

状态判断：
	•	BigQuery MV 整体：GA
	•	Smart tuning：GA（特定范围扩展于 2025） ￼
	•	LEFT OUTER JOIN / UNION ALL incremental support：Preview ￼
	•	logical view reference：Preview ￼

一句话评价：
BigQuery 的强项是 optimizer integration + fresh result compensation + smart tuning；弱项是增量 SQL 包络相对保守，复杂查询更多靠 non-incremental MV 解决。

⸻

3.4 StarRocks Materialized View

3.4.1 当前能力定位

StarRocks 官方文档中的 Async MV 自 v2.4 起支持，多表 join、更多 aggregate function、手动/定时/基于 base-table change 的异步刷新，以及分区级刷新；自 v2.5 起支持基于 SPJG 形态的 automatic transparent rewrite。 ￼

但从现有公开能力边界看，StarRocks 的主轴仍是：
	1.	预计算结果存储
	2.	partition-aware refresh
	3.	query rewrite acceleration

而不是对任意查询做 row-level delta algebra。

3.4.2 架构特征

StarRocks 的 Async MV 支持 base table 来自：
	•	default catalog
	•	external catalog（v2.5）
	•	existing materialized views（v2.5）
	•	existing views（v3.1） ￼

并支持：
	•	ASYNC：自动或周期刷新
	•	MANUAL：仅手动刷新
	•	partition refresh 减少成本
	•	SPJG rewrite 自动改写 ￼

3.4.3 当前状态判断
	•	Async MV：GA / 已长期可用能力（自 v2.4 起） ￼
	•	一系列增强特性按版本上线，例如
	•	Auto Analyze：v3.0+
	•	Deferred Refresh：v3.0+
	•	Random Bucketing：v3.1+  ￼

3.4.4 与“真正 IVM”的差距

StarRocks 当前公开文档没有把自己描述成：
	•	row-level change-propagation engine
	•	general delta planner
	•	changelog/retract-aware operator framework

相反，它更强调 部分分区重刷 + rewrite。这意味着它对很多查询的“增量”更接近：
	•	找到受影响分区
	•	重算这些分区
	•	用 MV 参与 rewrite

而非：
	•	按 operator 推导 delta expression
	•	保存辅助状态
	•	对 join/aggregate/window/distinct 精细维护

这也是为什么当前 StarRocks 更像 incremental recomputation system（增量重算系统），而不是通用 IVM engine（增量维护引擎）。
这不是贬义，反而说明它在工程上走的是一条更实用、更适合 OLAP 内核现状的路线。 ￼

⸻

4. 横向对比矩阵

维度	Snowflake Dynamic Table	Databricks MV	BigQuery MV	StarRocks Async MV
核心定位	Declarative pipeline + DVS	Log/state-aware MV on serverless pipelines	Optimizer-integrated MV	Precompute + rewrite + partition refresh
增量驱动	Change tracking + scheduler	Delta/Iceberg logs, row tracking, CDF, DV	Automatic refresh + query-time compensation	Base-table change / schedule / manual
刷新模式	AUTO / INCREMENTAL / FULL	AUTO / INCREMENTAL / INCREMENTAL STRICT / FULL	Incremental vs Non-incremental split	ASYNC / MANUAL
增量失败策略	退 full refresh	退 full 或 fail（strict）	incremental 失败时读 base / 非增量型整刷	受影响分区重刷/整刷
Query rewrite	不是核心卖点	对 MV 本身刷新为主；更偏 pipeline	Smart tuning 是核心卖点	SPJG rewrite 很重要
Outer Join	有限制	支持多种 join 增量化	LEFT JOIN Preview，RIGHT/FULL 不支持增量	可物化，但非通用 delta 维护
Window Function	受限	支持部分 window incrementalization	incremental 不支持；non-incremental 可支持	主要靠重算，不是原生 IVM
COUNT DISTINCT	没有公开宣称通用强支持	取决于 planner / source / operator support	sketch-friendly aggregate 有部分支持，但语法受限	更偏预聚合/重写，不是通用增量
一致性语义	Delayed View Semantics	Batch-equivalent result per refresh	Fresh result via compensation / staleness knobs	取决于 refresh 时机
延迟区间	秒到小时	serverless update cadence	背景刷新 + 查询补偿	分钟级到批量级
适合场景	SQL-driven transformation DAG	Delta-centric lakehouse 增量处理	高频查询加速 + optimizer rewrite	OLAP 查询加速、分区重刷
当前状态	GA	Incremental refresh Public Preview	MV GA；部分特性 Preview	GA

依据： ￼

⸻

5. 技术瓶颈深度分析

5.1 本质瓶颈一：非单调算子需要“撤销能力”

SUM += delta 这类事情很好做。
难的是：新数据到来后，你得知道哪些旧结果要撤销。
	•	COUNT DISTINCT 需要维护元素出现次数或 sketch/aux state；
	•	OUTER JOIN 可能让 previously-unmatched 行变成 matched，结果需要回收；
	•	ROW_NUMBER / RANK / TopN 一个新值插进来，后面整段都可能重排；
	•	MIN/MAX 在 delete 下尤其麻烦，没有候选集就只能重扫。

这就是为什么工业系统不是不喜欢这些算子，而是它们会把 IVM 从“写个 delta 脚本”变成“维护一个副本状态机”。

5.2 本质瓶颈二：没有 row identity，就很难做精细增量

Databricks 把 row tracking、DV、CDF 强调到近乎絮叨，正说明一点：
缺少稳定行标识和 mutation log，就难以做低成本的增量维护。 ￼

Snowflake 通过 change tracking 缓解；BigQuery 更偏 optimizer 端补偿；StarRocks 原生表当前更强的是 partition/refresh 级别控制，而不是底层 row lineage 公开能力。这是架构现实，不是文案修辞。

5.3 本质瓶颈三：通用 IVM 会状态爆炸

DBToaster 与 F-IVM 的启示很漂亮：高阶 delta、factorization、ring abstraction 都能把某些查询的 update cost 压得很低。
但现实里，一旦进入 full SQL：
	•	状态物化组合数暴涨
	•	维护路径复杂
	•	schema evolution/policy/UDF/nondeterminism 把 correctness 搅浑
	•	explainability 下降，用户根本不知道为什么这次是 incremental，下次成 full 了。 ￼

所以工业系统普遍选择 限定 query class + 明确 fallback。

5.4 本质瓶颈四：优化器与维护器往往是两套世界

BigQuery 把 optimizer rewrite 做得最深；StarRocks 也很强调 rewrite。
但“可被 MV answer”与“MV 能低成本维护”其实是两回事：
	•	某 MV 很适合 rewrite，但维护很贵；
	•	某 MV 易增量维护，但 rewrite 命中范围窄；
	•	某 MV 查询很快，但 freshness SLA 不满足。

这就是为什么真正成熟的系统需要 cost model = query benefit + maintenance cost + freshness value，而不是只看一个 query latency benchmark。

5.5 本质瓶颈五：一致性语义并不免费

Snowflake 的 DVS 论文点出了一个常被忽略的怪物：
流式 IVM 不是只有“快不快”，还有“这个结果到底对应哪个时间点、隔离级别怎么解释”。 ￼

BigQuery 通过 query-time compensation 实现“fresh result”，Databricks 更偏 refresh-bounded batch semantics，StarRocks 则更偏 refresh-point semantics。
同样叫“物化视图”，语义差异其实很大。

⸻

6. 可行方案探讨：从学术到工程

6.1 DBToaster / Higher-order IVM

代表论文：
Ahmad, Kennedy, Koch, Nikolic, VLDB 2012；Koch et al., VLDB Journal 2014。
核心是 viewlet transform：不仅 materialize query 本身，还 materialize higher-order deltas，以换取极低 update cost。 ￼

价值：
对 join-aggregate 类查询很强，尤其是高频、细粒度更新。

工程 gap：
	•	状态膨胀
	•	编译与 plan 管理复杂
	•	SQL 特性越丰富，变换链越容易爆炸
	•	对分布式 OLAP 执行器集成难度高

结论：
适合作为 StarRocks 某些 SPJG+Agg 模板的局部理论指导，不适合全量照搬。

6.2 DBSP

代表论文：
Budiu, Chajed, McSherry, Ryzhyk, Tannen, PVLDB 2023。
DBSP 试图给 rich query languages 一个通用、heuristic-free 的 IVM 定义，覆盖 nested relations、aggregation、flatmap、monotonic/non-monotonic recursion。 ￼

价值：
给“增量化可否统一表达”提供了极强理论框架；对 future-proof planner 很有启发。

工程 gap：
	•	工业 SQL optimizer/executor 并不是 DBSP IR
	•	runtime state model、fault tolerance、distributed scheduling 集成成本高
	•	很适合新系统（如 Materialize 风格），不一定适合老内核直接嫁接

结论：
更适合给 StarRocks 设计“IVM IR / delta planner”时借鉴抽象，而不是直接作为执行框架。

6.3 Factorized IVM / Foreign-key-aware IVM

代表论文：
Nikolic & Olteanu, SIGMOD 2018 / VLDBJ 2024；
Svingos et al., SIGMOD 2023《Foreign Keys Open the Door for Faster Incremental View Maintenance》。 ￼

价值：
	•	利用 FK/PK、功能依赖、层次型 join 结构降低维护复杂度
	•	很贴近工业仓库里“事实表 + 维表”的经典星型模型

工程 gap：
	•	需要 optimizer 可信地识别 constraints
	•	需要维护 planner 知道哪些 delta 可以沿 FK 局部传播
	•	constraints 在数据湖/弱约束场景下常常并不可靠

结论：
这是对 StarRocks 最有现实价值的一条学术路线。
因为 OLAP 场景里大量 MV 就是 star schema join + group by，FK-aware 增量化很有希望做出高 ROI。

6.4 Window / Holistic Aggregate 研究

代表论文：
Wesley & Xu, PVLDB 2016《Incremental Computation of Common Windowed Holistic Aggregates》；
Vogelsgesang et al., SIGMOD 2022《Efficient Evaluation of Arbitrarily-Framed Holistic SQL Aggregates and Window Functions》。 ￼

价值：
说明 window/holistic aggregate 不是完全无解，而是需要专门状态结构与 frame-aware 算法。

工程 gap：
	•	算法通常针对特定窗口类型、特定 aggregate
	•	与分布式 shuffle / spill / vectorized execution 结合不简单
	•	与 SQL planner 的组合复杂度高

结论：
StarRocks 可以从这里挑选少数高价值模式试点，例如：
	•	tumbling/hopping time bucket 上的可追加窗口
	•	partition-local ROW_NUMBER with bounded partition churn
	•	approximate distinct over append-only partition

而不是一开始就碰 full arbitrary framed window。

6.5 Flink Changelog Model

Flink 的 dynamic table / changelog stream 模型不是传统 DB IVM 论文，但它提供了非常有用的工程范式：
把所有维护都视为 INSERT/UPDATE_BEFORE/UPDATE_AFTER/DELETE 流传播。 ￼

价值：
这对 StarRocks 若未来想把 MV 刷新与 CDC / streaming ingestion 打通，会很有帮助。

工程 gap：
StarRocks 当前主执行模型仍是查询引擎 + refresh task，不是原生 retract-stream executor。
这一步跨度很大，不能硬跳。

⸻

7. 对 StarRocks 的启示与建议

7.1 不要把目标写成“通用全 SQL IVM”

这条建议最重要。
如果目标一开始写成“支持 window / distinct / outer join / subquery / set op 的统一增量维护”，最后大概率会变成一个设计文档非常好看、落地却像被猫咬过的毛线球。

更合理的目标应该是：

在 StarRocks 现有 Async MV + Rewrite + Partition Refresh 基础上，
逐步引入 operator-scoped incremental refresh，
对高价值查询族实现低成本、可解释、可验证的增量维护。

7.2 推荐路线：三阶段演进

Phase 1：从“分区级增量重算”升级到“受限算子族的真增量”
优先支持：
	•	SPJG
	•	append-heavy fact table
	•	FK-aware dimension join
	•	distributive/algebraic aggregate：SUM/COUNT/MIN/MAX/AVG
	•	可选：COUNT DISTINCT 先只做 approximate/sketch 化

做法不是维护复杂全局状态，而是：
	•	识别受影响 partition
	•	在 partition 内做 delta scan
	•	生成 delta intermediate
	•	merge 到 MV partition

这一步和 StarRocks 当前 partitioned MV 设计最兼容。

Phase 2：引入 lightweight maintenance state
为少数算子引入辅助状态，例如：
	•	distinct-state sketch / bitmap / HLL
	•	join-side existence bitmap
	•	aggregate partial state
	•	per-partition watermark / refresh checkpoint

这一步要非常克制：
只对收益显著的 query class 开 state，不搞全系统状态泛滥。

Phase 3：引入 IVM Planner + Explainability
借鉴 Databricks 的 EXPLAIN CREATE MATERIALIZED VIEW 思路，为 StarRocks 提供：
	•	query incrementalizability explain
	•	why-fallback-to-recompute
	•	expected state footprint
	•	refresh technique chosen

这个能力极关键。没有 explainability，用户会被系统的“偶尔增量、偶尔全量”逼疯。

7.3 推荐的首批支持范围

从 ROI 角度，建议 StarRocks 第一批重点覆盖：

A. Star-schema aggregate MV

SELECT d1.k, d2.k2, SUM(f.v), COUNT(*)
FROM fact f
JOIN dim1 d1 ON ...
JOIN dim2 d2 ON ...
WHERE ...
GROUP BY ...

原因：
最常见、收益大、约束清晰、可借助 FK-aware IVM 思想。

B. Append-only partitioned aggregate MV
按天/小时分区的事实表，insert-only 或 mostly-append。
原因：
和 StarRocks 分区裁剪、partition refresh 天然契合。

C. Limited LEFT JOIN
只允许：
	•	fact LEFT JOIN dimension
	•	dimension relatively static
	•	no nested aggregation on both sides
	•	equality join only

D. Approximate distinct MV
先从 HLL / bitmap_union 一类 sketch aggregation 开始，而不是死磕精确 COUNT DISTINCT。

7.4 不建议第一阶段碰的能力

这些最好先别去摸老虎屁股：
	•	arbitrary window functions
	•	full outer join / anti join
	•	general subquery decorrelation 后的增量维护
	•	self-join with arbitrary updates
	•	rank/topN under frequent update/delete
	•	non-deterministic UDF
	•	lake external tables 上强一致 row-level IVM

这些全是“理论上可以写论文，工程上容易写遗书”的区域。

7.5 StarRocks 实现层面的关键模块建议

从内核视角，建议抽象出以下模块：

1. MV Incrementalizability Analyzer
输入 logical plan，输出：
	•	supported / unsupported
	•	required assumptions（append-only、FK、partition aligned、deterministic）
	•	refresh technique 候选

2. Refresh Planner
在以下策略间选择：
	•	full recompute
	•	partition recompute
	•	delta aggregate merge
	•	hybrid

3. Maintenance State Catalog
存储：
	•	refresh checkpoint
	•	base partition version mapping
	•	optional operator state metadata

4. Delta Execution Subplan Generator
从原 query plan 衍生 delta 子计划，而不是每次都重新手写 refresh SQL。

5. Explain / Observability
暴露：
	•	why incremental
	•	why fallback
	•	rows scanned / rows merged
	•	state bytes
	•	affected partitions
	•	refresh wall time / CPU / memory

7.6 与 StarRocks 当前产品定位的契合点

StarRocks 不是为 transaction-heavy OLTP update stream 而生，它的长处是：
	•	OLAP query optimizer
	•	vectorized execution
	•	partition pruning
	•	aggregate/join acceleration
	•	rewrite framework

所以 StarRocks 最适合做的是：

Warehouse-oriented IVM（面向数仓的 IVM）
而不是
General-purpose changelog algebra machine（通用变更代数机器）

这条定位很关键。顺势而为，比空手抓闪电靠谱得多。

⸻

8. 结论

把四家系统摆在一起看，图景已经很清楚：

Snowflake 证明了：
用 declarative pipeline + delayed view semantics + automatic IVM，可以把流式转换产品化，并把用户从 stream/task 脚本地狱里捞出来。 ￼

Databricks 证明了：
如果底层表格式有 row tracking / CDF / DV，再加 serverless pipeline 与 refresh policy，复杂 query 的“局部增量化”可以做得很激进。 但这条路高度依赖湖仓底层元数据能力。 ￼

BigQuery 证明了：
optimizer-integrated MV + smart tuning + query-time compensation 是另一条强路径。它不追求最宽 SQL 增量包络，而是把“能自动重写并给出 fresh result”的体验做到很强。 ￼

StarRocks 当前的位置则非常明确：
Async MV 已经是强查询加速器，但还不是通用 IVM 引擎。
它最值得做的，不是追求 full-SQL universality，而是把现有 partition refresh / rewrite 框架往 operator-scoped, cost-aware, explainable incremental maintenance 推进。 ￼

再说得更直一点：
StarRocks 最有胜算的方向，不是复制 Snowflake/Databricks/BigQuery 的完整形态，而是结合自身 OLAP 内核优势，做出一个 更偏数仓、分区友好、可解释、对星型模型极强 的 IVM 体系。那会比盲目追求“所有 SQL 都增量”更像一条能跑起来的路。

⸻

9. 参考资料

官方文档 / Release Notes
	•	Snowflake Dynamic Tables docs: Supported queries, Create dynamic tables, Target lag, Refresh, Comparison, Troubleshooting.  ￼
	•	Snowflake release note: Dynamic Tables GA (2024-04-29), UNION incremental support (2025-08), dual warehouses (2025-12).  ￼
	•	Databricks docs: Incremental refresh for materialized views, materialized views architecture, EXPLAIN CREATE MATERIALIZED VIEW, REFRESH POLICY.  ￼
	•	BigQuery docs: Introduction to materialized views, Create materialized views, Use materialized views, release notes.  ￼
	•	StarRocks docs: Asynchronous materialized views, feature support, refresh statement.  ￼

学术论文 / 技术论文
	•	Ahmad, Kennedy, Koch, Nikolic. DBToaster: Higher-order Delta Processing for Dynamic, Frequently Fresh Views. PVLDB 2012 / VLDB Journal 2014.  ￼
	•	Budiu, Chajed, McSherry, Ryzhyk, Tannen. DBSP: Automatic Incremental View Maintenance for Rich Query Languages. PVLDB 2023.  ￼
	•	Nikolic, Olteanu. Incremental View Maintenance with Triple Lock Factorization Benefits. SIGMOD 2018; F-IVM survey/journal follow-up 2024.  ￼
	•	Svingos, Hernich, Gildhoff, Papakonstantinou, Ioannidis. Foreign Keys Open the Door for Faster Incremental View Maintenance. SIGMOD 2023.  ￼
	•	Wesley, Xu. Incremental Computation of Common Windowed Holistic Aggregates. PVLDB 2016.  ￼
	•	Vogelsgesang, Neumann, Leis, Kemper. Efficient Evaluation of Arbitrarily-Framed Holistic SQL Aggregates and Window Functions. SIGMOD 2022.  ￼
	•	Olteanu et al. Recent Increments in Incremental View Maintenance. PODS Gems / 2024 overview.  ￼
	•	Snowflake engineering paper: Streaming Democratized: Ease Across the Latency Spectrum with Delayed View Semantics and Snowflake Dynamic Tables. 2025.  ￼
	•	Apache Flink docs on dynamic tables / changelog streams.  ￼