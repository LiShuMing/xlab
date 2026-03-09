
我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Trino/Starburst(trino的商业化公司) 的官方 Release Notes，同时结合历史版本记录、官方博客、技术文章及社区讨论：

**分析维度要求如下：**

1. **重大 Feature 与场景支持**：总结近年来（重点聚焦最近 2–3 个大版本）最重要的功能特性与新场景支持，优先关注对 HTAP、分布式事务、存储引擎、SQL 兼容性等方向有实质影响的变化；

2. **执行引擎 / 存储引擎 / 性能优化动向**：重点梳理执行引擎、Optimizer（优化器）在向量化执行、下推优化、统计信息、自适应查询执行（AQE）等方面的演进；结合 Trino 的 HTAP 架构特点，分析其在 TP 与 AP 融合上的技术取舍；

3. **自动化与运维智能化**：关注 Trino 在自动化运维（如 Auto Analyze、Auto Scaling、Trino Operator）、可观测性（如 Clinic、Performance Overview）、以及资源管控（Resource Control）方面的进展；

4. **技术、产品与商业化视角的综合洞察**：
  - **技术视角**：与同类系统（如 Doris/StarRocks、ClickHouse）做横向对比，指出 Trino 在技术路线上的独特选择与权衡；
  - **产品视角**：分析各版本迭代的重心转移（如从"功能完整性"到"性能与稳定性"、再到"HTAP 场景化落地"）；
  - **商业化视角**：结合 PingCAP 的 Trino Cloud 产品动向，分析其 Serverless、多云策略与开源社区的协同关系。

**参考资料：**
- Trino Release Notes 主页: https://trino.io/docs/current/release.html
- Starburst Release note: https://docs.starburst.io/latest/release.html


**输出格式要求：**
- 以**博客深度分析文章**的形式输出，面向有分布式系统与数据库内核背景的工程师读者，语言要有技术深度、不讲废话；
- 内容尽量详实，**通过直接引用原 Release Notes 中具体的条目或 GitHub PR/Issue 链接**来支撑论点，避免泛泛而谈；
- 结合相关官方博客或社区文章，对重要特性补充背景概念和技术原理；
- **专业名词及产品专属技术术语使用英文标注**，并尽可能附上英文参考链接（文档、博客或 PR）；

---

以下是优化后的 Prompt，修正了几处事实错误（Trino 没有"HTAP 架构"、商业化公司是 Starburst 不是 PingCAP、Trino 也没有 Trino Cloud），并大幅强化了分析维度的准确性和专业深度：

---

我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Trino 的官方 Release Notes 及其商业化公司 Starburst 的产品文档，同时结合历史版本记录、官方博客、技术文章及社区讨论，输出一篇面向数据库内核工程师的深度调研报告。

---

**分析维度要求如下：**

**1. 重大 Feature 与场景支持**

重点聚焦最近 2–3 年（Trino 380 至今，Starburst 对应版本）中最有实质影响的功能演进，优先关注以下方向：

- **Federation 与 Connector 体系**：新增或改进的 Connector（如 Iceberg、Delta Lake、Hudi、Hive、JDBC、OpenAPI），以及跨数据源联邦查询（Cross-source Federation）的能力边界与性能瓶颈；
- **Table Format 支持**：对 Apache Iceberg、Delta Lake、Apache Hudi 的读写支持深度（如 Merge-on-Read、Copy-on-Write、Time Travel、Schema Evolution、Partition Evolution）；
- **SQL 兼容性与扩展**：新增的 SQL 语法、Window Function、MERGE 语句、Role-based Access Control（RBAC）等；
- **容错执行（Fault-Tolerant Execution，FTE）**：Task-level retry、Exchange spill-to-disk 机制的成熟度与生产就绪程度；

**2. 执行引擎 / 优化器 / 性能优化动向**

Trino 是纯 MPP 计算引擎，没有自己的存储层，分析重点应聚焦于：

- **向量化执行（Vectorized Execution）**：当前是否引入 SIMD 优化、列式内存格式（如从 `Slice` 到 Apache Arrow 的迁移讨论）、以及 JVM 平台上向量化的工程取舍（Project Panama / VectorAPI 的进展）；
- **优化器演进（Cost-Based Optimizer, CBO）**：统计信息（Table Statistics、Column Statistics、NDV）收集与利用、Join Reordering、Dynamic Filtering（动态过滤）的下推范围扩展、Predicate Pushdown 到 Connector 层的深度；
- **自适应查询执行（Adaptive Query Execution, AQE）**：与 Spark AQE 的对比，Trino 在运行时计划调整上的能力与限制；
- **Spill-to-Disk**：内存不足时的 Hash Join / Aggregation 溢写机制，对超大数据集查询的影响；
- **Native Execution Engine（Velox 集成）**：Trino 与 Meta 内部 Velox 引擎的集成状态（[prestodb/trino 分叉对比](https://github.com/prestodb/presto)），C++ native 执行路径的进展与开源社区的分歧；

**3. 资源管控、运维与可观测性**

- **Resource Groups**：Trino 原生的资源组（[Resource Groups](https://trino.io/docs/current/admin/resource-groups.html)）在多租户场景下的能力与限制，与 StarRocks 的 Resource Group / Workload Group 的对比；
- **Graceful Shutdown 与滚动升级**：生产环境下的零停机运维能力；
- **Query Insights / Observability**：原生 Web UI、`EXPLAIN ANALYZE`、`system.runtime.queries` 等可观测性手段的成熟度；Starburst 商业版在可观测性上的额外增强（如 Starburst Insights）；
- **Kubernetes Operator（[trino-helm-charts](https://github.com/trinodb/charts) / [Trino Operator](https://github.com/stackabletech/trino-operator)）**：云原生部署的成熟程度；

**4. 技术、产品与商业化视角的综合洞察**

- **技术视角**：与同类 MPP/OLAP 系统（StarRocks、Doris、ClickHouse、DuckDB、Spark SQL）做横向对比，重点指出：
  - Trino 作为"纯计算引擎 + Connector 联邦"架构的核心优势（数据不搬移、多源统一查询）与固有局限（无本地存储、跨网络 I/O 的性能天花板、JVM GC 对延迟的影响）；
  - 在 JVM 平台上实现高性能 OLAP 的工程路径，对比 StarRocks/ClickHouse 的 C++ native 实现；
  - Trino 与 Presto 的分叉演进（Meta 内部 Presto 走向 Velox/C++ native，开源 Trino 坚持 JVM 路线）对技术生态的影响；
- **产品视角**：分析 Trino 项目近年来迭代重心的变化，例如：
  - 从"Presto 的 SQL-on-Hadoop 替代"到"开放 Lakehouse 查询引擎"的定位转变；
  - Fault-Tolerant Execution 的引入是否标志着 Trino 正在从"交互式查询"向"批处理/ETL"场景扩张；
  - Iceberg REST Catalog 集成、表格式原生支持对 Lakehouse 架构的意义；
- **商业化视角**：结合 [Starburst](https://www.starburst.io/) 的产品动向（Starburst Galaxy、Starburst Enterprise），分析：
  - Starburst 在开源 Trino 之上的商业差异化（Data Products、Ranger 集成安全、Starburst Insights、Warp Speed 缓存加速层）；
  - Starburst Galaxy 的 Serverless 化策略与多云（AWS / Azure / GCP）部署模式；
  - 开源社区（Trino Software Foundation）与 Starburst 商业利益的协同与潜在张力；
  - 面对 Databricks / Snowflake 的竞争压力，Starburst 的市场卡位策略（"不替代你的数据仓库，而是联邦所有数据源"）；

---

**参考资料：**

- Trino Release Notes：https://trino.io/docs/current/release.html
- Starburst Release Notes：https://docs.starburst.io/latest/release.html
- Trino GitHub 主仓库：https://github.com/trinodb/trino
- Trino 官方博客：https://trino.io/blog/
- Starburst 博客：https://www.starburst.io/blog/
- Velox（Meta C++ 执行引擎）：https://github.com/facebookincubator/velox
- Trino Helm Charts：https://github.com/trinodb/charts

---

**输出格式要求：**

- 以**博客深度分析文章**的形式输出，面向有分布式系统与数据库内核背景的工程师读者，语言要有技术深度，不讲废话，避免"XX 支持了 YY 功能"式的干燥列举；
- 内容尽量详实，**通过直接引用原 Release Notes 中具体的条目、GitHub PR/Issue 链接或 JIRA 编号**来支撑论点；
- 对重要特性结合官方博客或技术文章补充背景概念和原理，让读者理解"为什么做"而不仅是"做了什么"；
- **专业名词及产品专属术语使用英文标注**，并尽可能附上英文参考链接（文档、博客、PR 或论文）；
- 建议文章结构：**引言（定位与背景）→ 执行引擎与优化器演进 → Connector/Table Format 生态 → 容错执行与批处理扩张 → 资源管控与云原生运维 → 商业化与生态竞争 → 总结与洞察**，各章节要有自己的核心论点，不做纯罗列；
- 全文字数不少于 5000 字，确保每个技术点有足够的深度展开。

---

**主要修正与增强说明：**

| 原 Prompt 问题 | 修正内容 |
|---|---|
| 把 Trino 定位成"HTAP 系统" | Trino 是纯 MPP 计算引擎，无存储层，无事务支持，HTAP 概念不适用 |
| "分布式事务、存储引擎"等维度 | 替换为 Trino 真正相关的 Connector/Table Format、FTE、Spill 等 |
| "商业化视角"误写为 PingCAP/TiDB Cloud | 修正为 Starburst（Starburst Galaxy / Enterprise）|
| 自动化运维中的"Auto Analyze/TiDB Operator" | 替换为 Trino Resource Groups、trino-helm-charts 等对应概念 |
| 缺少 Velox/Presto 分叉这条核心技术叙事线 | 新增 Native Execution Engine 与分叉讨论维度 |
| 缺少 Starburst Warp Speed 缓存等商业差异化特性 | 在商业化维度中补充 |


# 从 SQL-on-Hadoop 到 Lakehouse Federation：Trino 近三年的技术演进、产品重心与商业化分层

如果你是做数据库内核的人，看 Trino 最近两三年的演进，会有一种很强的“路线分化感”。一方面，它仍然是那个经典的 pure compute MPP query engine：没有自有存储层，靠 Connector / SPI 把 Hive、Iceberg、Delta Lake、Hudi、JDBC 数据库、对象存储乃至各种 SaaS/API 接进来；另一方面，从 Fault-Tolerant Execution (FTE)、Iceberg/Delta 原生支持、REST Catalog、动态目录管理，到 Starburst 在其上叠加的 Warp Speed、Insights、Data Products、built-in RBAC，你能明显看出它已经不满足于“交互式联邦查询器”这个老位置，而是在往“开放 Lakehouse 的统一查询与治理入口”挪。 ￼

这篇文章不打算把 release notes 机械抄一遍，而是站在数据库执行器、优化器、存储格式适配和系统工程的视角，回答四个问题：Trino 380 以来最硬的变化是什么；这些变化在执行引擎、优化器、Connector 生态上意味着什么；Starburst 的商业化增强到底增强了哪一层；以及，Trino 这条 “JVM MPP + Federation” 路线，相比 StarRocks、Doris、ClickHouse、Spark SQL、DuckDB，到底强在哪，又卡在哪。以下判断主要基于 Trino 官方 release notes、官方博客、官方文档，外加 Starburst 文档与 release notes；个别涉及工程路线的判断，我会明确标成分析而不是官方表述。 ￼

一、这三年的主线，不是“加了多少 Connector”，而是 Trino 重新定义了自己的工作负载边界

如果把时间线拉到 Trino 380（2022 年 5 月）以后，最重要的起点其实不是某个 SQL 语法，而是 Project Tardigrade / Fault-Tolerant Execution。Trino 官方在 2022 年的 Project Tardigrade 文章里讲得很直白：它的目标不是单纯补一个 retry，而是引入新的 fault-tolerant execution architecture，让中间 exchange 数据持久化、允许更细粒度重试，并为 memory-aware scheduling 和 resource-aware scheduling 打基础。380～392 这个阶段里，381 增加了 Azure Blob Storage exchange spooling 支持，392 把 dynamic filtering 带到了 task-based FTE，367/392/405 一线又逐步把 query retry / task retry 的连接器支持从 Hive/Iceberg 扩到更多 JDBC connector。换句话说，Trino 先做的不是“更快”，而是“更能扛失败”。 ￼

这件事的含义非常大。传统 Presto/Trino 的产品人格更像交互式查询引擎：你拿它去跑 BI、ad hoc、多源 join、轻 ETL 都行，但碰到长查询、spot instance 抖动、worker 宕机、内存边界时，它在产品层面更倾向于 fail fast。FTE 之后，Trino 官方自己也开始公开讲“Trino is not only for fast adhoc analytics”，而是可以进入 batch / ETL 场景；官方文档现在也明确区分：QUERY retry 更适合大量小查询，TASK retry 更适合大批处理查询，而且最佳实践是分成不同集群跑。这个措辞本身就说明 Trino 的负载定位变了：不是从交互式转型成 Spark，而是在保持 SQL MPP 引擎形态的前提下，把批处理边界往外推。 ￼

从产品定位角度看，这也是 Trino 从“Presto 的 SQL-on-Hadoop 替代品”转向“开放 Lakehouse 查询平面”的关键一步。因为纯交互式联邦查询的天花板很低：它容易成为分析平台里的一个加速入口，但很难成为主平台。只有当它能接住更重的 ETL、物化视图、表维护和跨格式数据管道时，它才有资格和 Spark SQL、Databricks SQL、Snowflake 争更大的工作负载面。Trino 官方在 2022 和 2023 年的年终/大会总结里也把这一点说得很清楚：FTE、schema evolution、lakehouse migration、OpenTelemetry、table functions，这些并不是零碎 feature，而是在把 Trino 从一个 analytics engine 扩成更通用的 query engine。 ￼

二、执行引擎层面：Trino 仍然是 JVM page/block 模型，不是 Velox 路线；它的“性能工程”更多发生在 I/O、编码、计划和运行时策略上

对内核工程师来说，最先想问的一定是：Trino 这几年有没有走向真正的 vectorized execution / SIMD native path？答案基本是否定的，至少在开源 Trino 主线里，没有出现类似 Velox/ClickHouse/StarRocks 那种“把执行器核心重写为 C++ native 向量化内核”的路线。Trino 目前依旧是 JVM 路线，核心执行形态仍是 Page/Block 模型；你从官方文档、release notes、代码依赖和公开博客里能看到很多围绕 Parquet/ORC reader、压缩编解码、窗口函数、join、grouping、memory accounting 的优化，但几乎看不到“engine-level Arrow 化”或“SIMD-first executor”这种公开路线声明。Trino 仓库引入 Arrow 依赖，更明确的落地场景主要是 BigQuery connector 的 Arrow serialization，而不是 engine 内部 page representation 向 Arrow record batch 迁移。 ￼

这也是 Trino 和 Meta 内部 Presto/Prestissimo + Velox 分叉之后最核心的技术分水岭。Presto 社区在 native execution 上持续推进 Prestissimo，并且公开 issue 里能看到它和 Velox 的内存仲裁、extra credentials、函数兼容性、构建依赖等大量 native-specific 问题；而 Trino 这边，主干路线依旧是 JVM。这个差异不只是语言实现差异，而是系统边界选择差异：Meta/Prestissimo 追求的是 native executor 带来的更高 CPU 效率和更低 GC 压力，但要付出 connector 兼容、内存跟踪一致性、功能覆盖、生态割裂的代价；Trino 则保留 Java/SPI 生态的一致性，把精力放在连接器、计划器、对象存储、云部署和运行时容错上。 ￼

所以，Trino 的性能工程这三年更多体现为三类事情。

第一类是 读路径优化。405 一次性在 Delta/Hive/Iceberg/Hudi 上铺了大批 Parquet reader 优化：更好的 primitive type 读取、filter-aware 读取、large row group/ORC stripe 场景优化、memory footprint 降低；469 又继续优化 large files on S3、large Parquet row groups、Delta transaction log JSON；454/459 则把 metadata cache、filesystem cache 命中率、coordinator 端 Iceberg metadata cache 往前推。你会发现它的“向量化味道”主要体现在文件扫描器和编码路径，而不是执行算子的内核重构。 ￼

第二类是 operator-level hot path 优化。413 提升了 window / row pattern recognition 在小分区上的性能，并优化了 row_number() / rank()；450、451 又继续优化 first_value()、last_value() 和部分排行窗口函数；446 提升 complex grouping；474-e 还提到 large CASE WHEN 和复杂 inner join expression 的速度提升。这些改动非常 Trino：不是改执行器范式，而是在现有 pipeline 里抠热点。 ￼

第三类是 FTE runtime 策略优化。457 是一个标志点：官方直接引入了 fault-tolerant-execution-adaptive-join-reordering-enabled，把 FTE 里的 adaptive plan optimization 摆上台面；相关 issue 23182 进一步说明，Trino 的 adaptive planning 目前主要在 FTE 框架里，根据 exchange-level statistics 做 join reordering、未来也计划处理 skewness 和 broadcast/partitioned join 转换。注意，这和 Spark AQE 不是一个成熟度：Spark AQE 已经把 coalesce shuffle partitions、broadcast conversion、skew join handling 做成了产品特征；Trino 目前公开可见的 AQE 更像“FTE 场景下的 runtime patching”，而不是普适的全局运行时计划重写。 ￼

这背后的工程取舍很清楚：Trino 的首要矛盾不是单节点 CPU 算子性能，而是多源联邦、对象存储 I/O、远端系统 pushdown 边界、网络与 shuffle 的不确定性。对它来说，原生 C++ 向量化并不是没有价值，但远没有 connector/metadata/path pruning/FTE/retry 这些事情优先级高。站在 StarRocks 或 ClickHouse 工程师视角，这会让 Trino 在纯本地列存场景里很难打到极致；但站在多源 Lakehouse / Federation 场景，它的优先级排序其实是合理的。 ￼

三、优化器演进：Trino 的重点不是“更深的算子智能”，而是“让 CBO 与 Connector pushdown 更现实”

Trino 的优化器这几年的关键词是三个：statistics usable、dynamic filtering 扩边界、connector pushdown 更深。

先说 statistics。405 的 release note 里有一个很小但很说明问题的条目：当部分列缺少 nulls fraction 统计信息时，改进查询性能。这种条目听起来不起眼，但恰恰暴露了 Trino CBO 的真实工作条件：它不是在一个完全受控的自有存储层上做代价估算，而是在一堆外部 metastore、table format、JDBC catalog 和对象存储元数据上工作，统计信息天生不完整、质量不一致。Trino 的优化器进化，很多时候不是发明更复杂的规则，而是让“不完美的统计”也能跑出不太差的计划。 ￼

再说 dynamic filtering。Trino 现在官方文档对其工作机制写得非常清楚：它会从右侧 build side 收集运行时谓词，先在 broadcast join 本地下推到 probe side scan，再通过 coordinator 用于 split enumeration，并在 partitioned join 时把 filter 分发回 worker；支持内连接、right join、semi-join 和多个比较操作，具体能否真正生效取决于 connector 是否支持 scan-time 和 split-enumeration-time utilization。也就是说，Trino 的 dynamic filtering 从来不是单纯 optimizer 规则，而是 optimizer、runtime、connector 三方协作。 ￼

380 以后，dynamic filtering 的关键变化有三次。367 把 query retries 场景下的 dynamic filtering 补上；392 把它扩到 task-based FTE；445 又把 MongoDB connector 纳入 dynamic filtering 支持。早期它主要在 Hive 体系里最有价值，因为可以做 dynamic partition pruning 和 ORC/Parquet stripe pruning；现在它逐渐从“Hive 特性”变成“Trino Federation 的一等优化手段”。但它的边界也很明显：如果右表不够小、连接条件不适合、connector 不支持、底层系统不接受相关 predicate pushdown，它就退化。Trino 在这里非常依赖 connector 实现质量，而不像自有存储 MPP 可以完整控制 scan pipeline。 ￼

Connector pushdown 方面，近两年的演进也说明了 Trino 的重心。405 的 Redshift connector 增加 aggregation/join/ORDER BY ... LIMIT pushdown；468-e 的 MaxCompute 增加 table scan redirection、limit pushdown、predicate pushdown；Starburst 文档也持续把 cast pushdown、credential passthrough、Lake Formation、schema discovery 等能力商业化整合进去。对 Trino 这类系统来说，pushdown 不是锦上添花，而是生死线：因为它没有自己的存储层，跨网络 I/O 和 remote engine 的 execution boundary 决定了性能天花板。你能 push 多深，决定了它更像“分布式执行器”还是“昂贵的数据搬运器”。 ￼

如果和 Spark AQE 对比，一个很直白的判断是：Trino 今天并没有形成 Spark 那种“运行期大规模重规划”的产品能力。它有 CBO，有 runtime dynamic filtering，有 FTE 场景下的 adaptive join reordering，但整体仍是 static plan first, runtime correction second。这并不一定是缺点，因为联邦查询里的真正不确定性更多在远端数据源与 metadata，而不是 shuffle partition 数量本身；但它意味着 Trino 很难像 Spark 那样，通过 AQE 把一部分脏统计和数据偏斜在运行时系统性兜住。 ￼

四、Connector 与 Table Format：Trino 真正的护城河，不是某一个 Connector，而是“开格式 + 联邦”的组合深度

很多人看 Trino，会先被 “hundreds of connectors” 这个叙事吸引。但站在工程上，更值得看的不是数量，而是它对 Iceberg / Delta Lake / Hudi / Hive / JDBC 这几类主战场的支持深度，以及这些 connector 能否和优化器、FTE、pushdown、catalog 管理闭环。

1）Iceberg：Trino 近三年最重的 investment，已经不只是“能查 Iceberg”

Iceberg connector 这几年的演进非常连续。405 引入 Iceberg REST Catalog 支持；446 增加 Snowflake catalog；451 增加 nested ROW 分区、incremental refresh for basic materialized views、resource prefix in REST catalog、Parquet Bloom filter 写入；461 增加 add_files / add_files_from_table 和 migrate 补强迁移链路；462 开始支持 Unity catalog 的 read operations；465/467/474/475/477 又继续补 OAuth2 server URI、Unity catalog property 迁移、session-timeout、OAuth token refresh、IAM role auth、SIGV4、S3 Tables。官方 Iceberg 文档同时明确支持 schema evolution、partition evolution、time travel、row-level deletion (Iceberg v2 position deletes)、metadata tables、snapshot rollback、table_changes、CREATE OR REPLACE TABLE、materialized view incremental refresh 等一整套能力。 ￼

这个演进的重点，不只是“支持 Iceberg 标准”，而是 Trino 正在把自己塑造成 Iceberg compute front-end。你能看到它不只是读写数据文件，还在补 REST catalog auth、catalog 特定兼容（Unity、Snowflake、S3 Tables）、metadata cache、materialized view、snapshot maintenance、migration procedure。这意味着 Trino 对 Iceberg 的理解，已经从“一个对象存储表格式”升级成“Lakehouse 元数据控制面的一部分”。这也是为什么 Starburst 一直把 Iceberg 当商业化叙事中心：它既契合 open table format 方向，又能把 Trino 的联邦能力和湖仓叙事绑在一起。 ￼

2）Delta Lake：写支持与 deletion vector 是分水岭，但它的兼容性复杂度也最高

Delta Lake connector 的变化很能体现 Trino 的工程现实。414 明确 disallow reading tables with deletion vectors，因为之前会返回错误结果；427 开始支持 reading tables with Deletion Vectors；454 再支持 writing deletion vectors；457 允许创建带 deletion vector 的表；459、460、469 则连续修 deletion vectors 写错、读错、写 CDF + DV 组合不安全等问题。沿着这个时间线看，你会发现 Delta 支持并不是“某一版支持了 deletion vectors 就结束”，而是从 read compatibility 到 write correctness 再到 corner case 修复的长链条。 ￼

Delta 文档目前明确支持 schema evolution、atomic replace table、optimize、views，以及不少写入和维护操作；release notes 里还能看到 Databricks runtime 兼容、writer version 7、v2 checkpoints、transaction log JSON 性能优化、concurrent write on S3 的 lock-less reconciliation。工程上最值得注意的是：Delta connector 的难点不是扫描 Parquet，而是事务日志语义、feature flags、protocol version、CDF、DV、column mapping、checkpoint 格式等兼容矩阵，这部分远比 Iceberg 更“实现驱动”。Trino 这几年确实补了很多坑，但也因此更容易出现 correctness 类 bug。对数据库工程师来说，这反而说明 Delta 支持是有实质深度的，不是表面兼容。 ￼

3）Hudi：有价值，但仍明显落后于 Iceberg/Delta 的一等公民地位

Hudi connector 的官方文档现在仍然写得很清楚：Copy-on-write 支持 snapshot queries，Merge-on-read 只支持 read-optimized queries。这个矩阵已经说明问题：Trino 对 Hudi 的支持更多是可读、可接入，而不是把 Hudi 当第一优先级 Lakehouse 格式来深度经营。release notes 里 Hudi 相关变化主要集中在 Parquet reader 性能、S3/Azure filesystem、metadata table 查询修复、一些 correctness 修复，很少看到像 Iceberg/Delta 那种持续补 catalog、事务语义、物化视图、迁移程序、行级变更管理。 ￼

这其实很符合市场现实。过去两年 Lakehouse 竞争的主轴已经越来越偏 Iceberg vs Delta，Hudi 在 Trino 里的存在更像“生态 completeness”。所以从产品投入判断，Trino 是在用 Hudi 证明自己的开放性，但真正的 engineering budget 明显压在 Iceberg 和 Delta 上。 ￼

4）JDBC / Federation：边界在不断扩，但天花板同样明显

FTE 文档现在列出的支持 connector，已经包括 BigQuery、Delta、Hive、Iceberg、MariaDB、MongoDB、MySQL、Oracle、PostgreSQL、Redshift、SQL Server。405 还专门提到 engine 层 MERGE API 统一后，DELETE/UPDATE 走 merge path，并给 Redshift 增加 aggregation/join/limit pushdown。2022 年的 Trino 博客也明确说，FTE 最初只适用于 object-storage connectors，后来补到了 MySQL/PostgreSQL/SQL Server，为更多 JDBC connectors 打了基础。 ￼

这说明 Trino 的 Federation 正在从“文件湖 + 元存储”扩展到“对象存储 + 事务库 + 云数仓 + 文档库”。但从系统结构上讲，它的瓶颈也非常稳定：cross-source federation 的成本主要由 remote scan latency、pushdown 深度、网络搬运和 type coercion 决定。这不是优化器再聪明一点就能消掉的。比如你把 PostgreSQL 的过滤没推下去，把 Iceberg 的分区裁剪没打准，再在 coordinator 侧做大 join，本质上就是跨网搬数据。Trino 的优势是让你“先不搬数据也能统一查询”；它的局限则是，一旦你真的把大量高基数 join、复杂 aggregation、跨云长距离 I/O 全压在 Federation 路径上，性能天花板会比本地存储 MPP 来得更早。这个局限不是 Trino 特有，而是 pure compute federation 架构的宿命。 ￼

5）OpenAPI / API 联邦：Starburst 在试图把“可查询边界”继续往外推

开源 Trino 主线没有成熟的 OpenAPI connector 文档，但 Starburst 在 2026 年的博客已经明确提到 new OpenAPI connector，并把它和 Great Lakes connector 一起当成“query data gated behind REST API endpoints using standard SQL”的扩展能力。这件事很有意思：它不是主流数仓能力，却非常符合 Starburst 的商业叙事——只要数据能被某种 connector 包装成表，它就能成为联邦平面的一个端点。工程上这类 connector 很难在 pushdown、分页、速率限制、schema drift 上做到漂亮，但商业上它非常有价值，因为它把“无需搬迁、统一查询”的故事继续推到了 API 层。 ￼

五、FTE 与 Spill：Trino 正在把“批处理能跑”变成产品能力，但这不等于它已经成为 Spark 的替代品

Trino 官方现在对 spill-to-disk 的态度已经相当明确：文档直接写着这是 legacy functionality，并建议优先考虑使用 TASK retry 的 FTE 加 exchange manager。spill 仍支持 join、aggregation、order by、window function，仍然能用 revocable memory 把中间结果写本地盘，但官方同时强调它可能让查询时间“按数量级”变慢，而且即便启用 spill，也不保证所有大查询都能活下来。这个措辞说明了 Trino 的设计重心已经转移：不是继续把单机 local spill 机制抠到极致，而是把“大查询容错”升级到 exchange-level spooling 和 task retry。 ￼

这背后是很合理的。因为在 MPP 场景里，本地 spill 解决的是“这个算子一时装不下”，而 FTE + external exchange spool 解决的是“节点挂了、任务挂了、spot instance 回收了、超长批任务中间结果必须持久化”。前者更像 operator survival，后者更像 workflow survival。对真正的生产 ETL 而言，后者价值更高。Trino 从 381 的 Azure spool，到后来支持 GCS、S3 encryption、Azure endpoint，再到 457 的 FTE adaptive join reordering，基本可以看成它把“交换数据持久化”从一种 feature 做成了批处理扩张的基础设施。 ￼

但要说它已经具备 Spark 那种批处理产品成熟度，我觉得还差得很远。原因有三点。

第一，Trino 官方自己就建议把 FTE 集群和交互式集群分开跑，说明它并没有在一个统一 execution mode 下同时兼顾低延迟 BI 和重 ETL。 ￼

第二，FTE 在 2024～2025 仍然有不少 hang、worker death、adaptive planning、string join correctness、storage backend 兼容等问题与修复条目，说明它是“可用而在持续 hardening”，不是已经完全 boring。 ￼

第三，Spark 的 AQE、shuffle 生态、RDD/DataFrame lineage、批流一体和生态工具链仍然更厚。Trino 的优势不是把 Spark 全替掉，而是把大量原本需要 Spark + SQL engine + federation engine 组合才能完成的部分 SQL ETL 工作，吸收到一个统一 SQL 查询平面里。换句话说，FTE 让 Trino 从“只能查”变成“也能更稳地加工”，但没有把它变成另一个 Spark。 ￼

六、资源管控、运维与可观测性：开源 Trino 够用，Starburst 则在把“平台层缺口”补成商品

Resource Groups 是 Trino 老特性，但在今天看，它仍是 Trino 多租户治理的核心原语。官方文档对它的描述很实在：resource group 可以限制资源使用和排队策略；查询只属于一个 group，并消耗该 group 及其祖先资源；除 queued queries 限制外，资源耗尽不会杀掉正在运行的查询，而是让新查询排队。这个模型适合做 admission control 和多租户节流，但它不是一个完整的 workload management 系统：它更像 coordinator 侧的队列/配额树，而不是像 StarRocks 的 Workload Group 那样把 CPU、memory、scan、I/O、并发隔离做得更靠近执行资源。 ￼

这也是我认为 Trino 和存储计算一体 MPP 在资源管控上的一个本质差异。Trino 因为没有自有存储层，又依赖远端 data source 与 connector，自身能稳定控制的主要是 query admission、task execution、memory policy、retry policy 和局部 spill/FTE 行为；但它很难像 StarRocks 那样，从 scan 节奏到后台 compaction 甚至本地缓存、tablet 线程池一起协同调度。换句话说，Trino 的资源管控天然更偏 query governor，而不是 whole-engine workload operating system。 ￼

运维层面，Trino 官方已经提供了比较成熟的 graceful shutdown 机制，允许 worker 通过 PUT /v1/info/state 进入 SHUTTING_DOWN，在足够 grace period 下不影响运行中查询。官方 Helm chart 也直接把 graceful shutdown 做成配置项，并明确要求 terminationGracePeriodSeconds 至少是设定 grace period 的两倍；不过 chart README 也写得很现实：如果你有自定义 lifecycle，就要自己处理 graceful shutdown。也就是说，开源 Trino 的零停机滚动升级能力已经够生产可用，但仍需要你在 Kubernetes、load balancer、Gateway 层把细节补齐。 ￼

Kubernetes 生态方面，Trino 官方 Helm charts 已经比较成熟，甚至把 Trino Gateway 一起纳入 charts。官方博客对 Gateway 的定位也很明确：当你开始拥有测试集群、ETL FTE 集群、交互式集群、升级中的新旧集群时，需要一个路由平面来做 load balancing、cluster selection 和升级切流。相比之下，社区里的 stackabletech/trino-operator 更像是另一个生态方向，但从 issue/release 状态看，它的版本跟进和生产资料成熟度没有官方 Helm 体系那么强。 ￼

可观测性方面，开源 Trino 的基础能力并不弱。EXPLAIN ANALYZE [VERBOSE] 可以看到分布式计划、每个 stage 和 operator 的 CPU / blocked / input / std.dev. 信息；Web UI 在 405 以后还补了 stage performance tab 的 operator CPU time；系统表和事件监听器则能接 JMX、OpenTelemetry、OpenMetrics、Kafka/MySQL/OpenLineage。对于懂内核的人，这套东西已经足够做 query forensics。 ￼

但 Starburst 很显然觉得“够用”不等于“可卖”，于是把这层打成了 Insights。官方文档写得很直接：Insights 提供 cluster performance、query history、single-query statistics、query plans、cluster history、usage metrics 和 cost estimation。你会发现这不是 engine 创新，而是平台产品化：把原本散落在 UI、事件、日志、JMX 里的信息，做成一个平台管理员和数据消费者都能直接使用的操作台。这正是商业版最容易产生价值的地方，因为很多企业愿意为“少自己搭可观测平台”付钱。 ￼

七、Starburst 的商业差异化：不是重写 Trino，而是在 Trino 上补“平台层”和“市场叙事层”

如果只看技术底座，Starburst 的核心仍然是 Trino。但如果只这么说，又会低估它的商业策略。过去两年 Starburst 最明显的做法，是把开源 Trino 之上的缺口系统性补齐成商品。

第一层是 安全与治理。Starburst 文档里，built-in access control 已经不是简单 file-based ACL，而是完整的 RBAC system，支持 roles、privileges、row filters、column masks、audit log，并与 Web UI、data products、函数、catalog/table/schema 级权限打通；同时又保留了 Apache Ranger / Privacera 的企业集成路线，包括 global access control 和 Hive/Delta/Iceberg object storage access control。对很多企业来说，这一层的价值远大于某个 SQL 函数，因为它决定 Trino/Starburst 能不能进入真正的多租户生产环境。 ￼

第二层是 性能增强与成本故事。Starburst 把这一层包装成 Warp Speed。文档里的表述是“transparently adds an indexing and caching layer”，适用于 Hive/Iceberg/Delta Lake 访问对象存储的 catalog；release notes 还能看到它的 file system cache、dynamic catalog management、local SSD 依赖等持续演化。工程上，这基本可以理解为：当 Trino 的主要瓶颈落在对象存储读取与 metadata 访问时，Starburst 用商业缓存/索引层去削减远端 I/O 代价。它不是改变 Trino 的算子内核，而是在最痛的外部瓶颈处加速，这个方向非常务实。 ￼

第三层是 平台易用性与数据产品化。Starburst 的 Data Products 文档明确把它定位为 semantic layer，用于 publish / discover / manage curated data assets；后续 release 又增加 Iceberg format data products、agent-based enrichment、Data Catalog。这一层已经不属于查询引擎内核，而是开始抢占“数据消费入口”和“数据产品目录”这类更靠近业务的层面。它的目标很明显：把“Trino 会查”升级成“Starburst 能提供可治理、可发布、可发现、可被 AI 消费的数据产品”。 ￼

第四层是 SaaS / serverless / multi-cloud。Starburst 自己对 Galaxy 的表述很一致：fully-managed SaaS，支持跨 AWS / Azure / GCP、多云和跨云查询，不要求用户自己管集群、升级和维护。这个定位的市场卡位也很清楚：它不正面说“我要替代你的数仓”，而是说“我来联邦你现有的数据湖、事务库、云数仓和对象存储”。对比 Snowflake/Databricks，这是一条更轻迁移、更低组织阻力的路线。 ￼

第五层是 社区与商业的协同/张力管理。Starburst 博客 2025 年已经明确把 Trino 描述为由 Trino Software Foundation 管理，同时又强调 Starburst 在开源之上的产品增强。这个关系本质上是健康但微妙的：Starburst 需要开源 Trino 保持足够活跃，来维持 connector 生态、标准兼容和“开放”的品牌；同时又需要把 UI、治理、缓存、catalog、AI、SaaS 这些“平台层价值”做成商业护城河。只要商业增强主要集中在平台层，而不是把 engine 核心彻底闭源，这种张力通常是可控的。 ￼

八、和 StarRocks / Doris / ClickHouse / DuckDB / Spark SQL 对比，Trino 的优势与天花板都很纯粹

如果和 StarRocks、Doris、ClickHouse 这类 storage-compute integrated OLAP 系统比，Trino 的最大优势不是单机快、不是局部算子强，而是 data gravity friendly：你不需要先把数据搬进它的存储层，就能拿统一 SQL 直查 Iceberg、Delta、Hive、Postgres、MySQL、BigQuery、Redshift，甚至商业版继续往 API 和 Data Product 扩。对大型企业来说，这种“先统一访问，再逐步收敛架构”的价值非常大。 ￼

但它的局限也同样纯粹。第一，它没有本地存储层，所以没有办法像 StarRocks/ClickHouse 那样把数据布局、编码、索引、compaction、cache、统计信息、调度全部收在一个控制面里。第二，它的性能上限高度依赖 connector pushdown 与远端 I/O；跨源 join 的最坏情况，本质上就是分布式 ETL。第三，JVM 路线意味着它在 GC、对象分配、内存跟踪、算子 hot path 上天然比 C++ native 系统更难压榨到极致。第四，它的 workload management 主要是 query-facing，而不是 storage-engine-facing。 ￼

如果和 Spark SQL 比，Trino 在交互式 SQL、联邦能力、部署轻量和 connector 统一性上更强；Spark 则在批处理成熟度、AQE 完整度、生态深度和编程模型通用性上仍有明显优势。FTE 让 Trino 部分侵入 Spark 的地盘，但不会消灭 Spark。 ￼

如果和 DuckDB 比，Trino 不是一个问题域：DuckDB 是单机内嵌分析内核的极致代表，Trino 是分布式联邦查询平面。两者都讲 open formats，但系统目标完全不同。 ￼

而和 Presto/Prestissimo 分叉路线相比，Trino 的意义在于：它证明了在不开启 native executor 大迁移的情况下，JVM 路线仍然可以通过 connector、FTE、Lakehouse format、catalog、云原生运维和商业平台层，继续保持极高活力。代价则是，在执行器内核的极致性能和 native 路线生态上，它选择了放弃。 ￼

结语：Trino 最近三年的真正变化，是从“会查很多地方”变成“想成为开放数据架构的统一入口”

如果非要把这三年的变化压缩成一句话，我会写成这样：

Trino 最近三年的主线，不是把自己变成另一个存储计算一体 OLAP，而是把“JVM MPP + Connector Federation”这条路线做到更像一个开放 Lakehouse 的统一计算平面。

FTE 让它从交互式查询走向更稳的批处理；Iceberg/Delta 让它从“能查文件湖”走向“理解 open table format 的控制面”；dynamic filtering、pushdown 和读路径优化让它在联邦架构里尽量少犯昂贵错误；Gateway、Helm、graceful shutdown、Insights、RBAC、Warp Speed、Data Products、Galaxy，则把开源引擎上面的平台缺口逐步补齐。 ￼

站在数据库内核工程师角度，我对它的判断很简单：Trino 不会在纯本地 OLAP 路径上赢下 StarRocks/ClickHouse；但在“企业数据已经分散存在、短期不可能完全迁移、又必须用统一 SQL/治理/AI 接口把它们接起来”的世界里，它仍然是极有生命力的一条路线。Starburst 也正是看准了这一点，才把商业化重点放在平台层而不是改写引擎灵魂。对今天的数据基础设施市场来说，这不是保守，反而是极现实的战略选择。 ￼

如果你愿意，我下一步可以把这篇文章继续扩成“带附录索引”的版本，补一份按版本号梳理的 feature/PR 索引表，把文中提到的 Trino release、PR、connector feature matrix 单独整理出来。
