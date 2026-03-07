我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（StarRocks）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。 

参考 Iceberg的如下release notes, 同时结合历史资料（历史release node）、博客：
- 总结其最近这些年其的重大feature/optimzation及新的场景支持;
- 总结其最近这些年在执行/存储/自动化/性能优化等方面的主要动向；
- 从技术、产品、商业话的视角，分析并洞察其产品在该年的定位及迭代方向的重点变化。

参考其release notes:
- https://iceberg.apache.org/releases/

按照博客的方式输出一篇介绍、思考的报告类文章：
输出时注意：
- 内容尽量详实，通过引用原release note中的commit/link来说明相关的功能feature；
- 语言流畅、减少空话，尽量言之有物，结合相关feature的blog或者PR文章进行补充相关的概念或者名词； 
- 在专业名词或者属于该产品的技术名词，请使用英文备注，并附上英文链接。

---

我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Apache Iceberg 的官方文档、官方博客、GitHub 提交历史（apache/iceberg）、
社区讨论（dev mailing list、GitHub Issues/PR）、学术论文，以及 Netflix、
Apple、Databricks、Tabular 等核心贡献方的技术博客进行综合分析：

**分析维度要求如下：**

1. **核心规范演进（Spec v1 → v2 → v3）**：
   - **Format Version 对比**：Spec v1 / v2 / v3 的核心差异——
     Row-level Deletes（Position Delete vs Equality Delete）的
     设计动机与工程权衡；v3 新增的 Deletion Vector（借鉴 Delta Lake DVs）
     vs v2 Delete File 的性能对比；
   - **Manifest 文件结构**：Manifest List → Manifest File → Data File
     三层元数据结构的设计；Manifest 中的 Column-level Statistics
     （min/max/null count）如何支持 File Skipping；
     Manifest Caching 在高并发读场景下的重要性；
   - **Snapshot 隔离模型**：Snapshot 的 Append / Overwrite / Replace /
     Delete 四种操作语义；Snapshot 引用（Branch / Tag）的设计——
     与 Git 分支模型的类比与差异；Wap（Write-Audit-Publish）模式的
     工程实践；
   - **Partition Spec 演进**：Hidden Partitioning（隐式分区）的设计哲学；
     Partition Spec Evolution（分区策略在线变更）的元数据兼容处理；
     Partition Transforms（identity / bucket / truncate / year/month/day/hour）
     的实现；Sort Order Spec 与 Clustering 的关系；

2. **并发控制与事务模型**：
   - **Optimistic Concurrency Control（OCC）**：Iceberg 的无锁并发写入
     机制——基于 Catalog 的原子 Swap（S3 conditional put / Hive Metastore
     CAS / Nessie 分支）；Commit Conflict 的重试策略（`RetryableCommit`）；
     多 Writer 并发写同一表时的冲突检测粒度；
   - **Catalog 类型对比**：Hive Metastore Catalog、REST Catalog（规范化的
     Catalog API）、AWS Glue Catalog、Nessie Catalog（Git-like 多分支）、
     JDBC Catalog 的技术选型权衡；REST Catalog Spec（`iceberg-rest-spec`）
     的标准化意义；
   - **Row-level Updates 的实现代价**：Copy-on-Write（COW）vs
     Merge-on-Read（MOR）的读写放大分析；Position Delete File 的
     I/O 成本（需要额外读取并 Join）；Equality Delete 的全表扫描风险；
     Deletion Vector 在 v3 中的改进方向；

3. **表维护（Table Maintenance）**：
   - **Compaction（文件合并）**：`rewrite_data_files` / `rewrite_manifests`
     的实现原理；Bin-packing vs Sorting 两种 Compaction 策略；
     Z-Order / Hilbert Curve 多列排序 Compaction 的实现现状；
     Compaction 的并发安全保证（与正在进行的写入不冲突）；
   - **Snapshot 过期与孤儿文件清理**：`expire_snapshots` 的引用计数机制；
     孤儿文件（Orphan Files）产生的根因与 `delete_orphan_files` 的
     实现安全边界；在流式写入场景下的清理策略；
   - **Table Statistics**：`update_statistics` 收集 Column-level NDV、
     Histogram 的实现；Puffin 文件格式（统计信息专用格式）的设计；
     统计信息如何被 Spark / Trino / StarRocks 等引擎消费；

4. **多引擎生态集成**：
   - **Spark 集成**：SparkCatalog / SparkSessionCatalog 的注册机制；
     Spark DataSource V2 API 与 Iceberg 的集成深度；
     Vectorized Parquet Reader 在 Iceberg Scan 中的启用条件；
     Structured Streaming 写入 Iceberg 的 Exactly-Once 语义实现；
   - **Flink 集成**：Flink Iceberg Sink 的两阶段提交（2PC）实现；
     Checkpoint 与 Iceberg Commit 的对齐机制；
     Flink 读取 Iceberg 的 Incremental Scan（基于 Snapshot 区间）；
   - **Trino / StarRocks / DuckDB 集成**：各引擎的 Iceberg Connector
     实现深度对比——是否支持 Delete File 下推、是否支持 Equality Delete
     向量化读取、Metadata Table（`$snapshots` / `$manifests`）的支持度；
   - **Python 生态（PyIceberg）**：PyIceberg 的架构（纯 Python 实现 vs
     Java 桥接）；与 pandas / PyArrow / DuckDB 的互操作；
     PyIceberg 的写入能力现状（是否支持全 DML）；

5. **Iceberg REST Catalog 与云原生生态**：
   - **REST Catalog Spec**：统一 Catalog API 规范的意义——
     解耦引擎与 Catalog 实现；OAuth2 / Token 认证集成；
     Credential Vending（凭证代理）机制（引擎无需直接持有云存储密钥）；
   - **主流 REST Catalog 实现对比**：Polaris（Snowflake 开源）、
     Unity Catalog（Databricks 开源）、Gravitino（Apache 孵化）、
     Nessie 的技术差异与生态博弈；
   - **与 DuckLake 的竞争关系**：DuckLake 对 Iceberg 元数据层的批评
     是否成立；Iceberg v3 的改进是否能弥补元数据性能短板；
     两者的适用场景边界；

6. **技术、社区与商业化视角**：
   - **技术视角**：与 Delta Lake v3、Apache Hudi、DuckLake 的横向对比——
     核心设计哲学差异（文件系统语义 vs 数据库语义）；
     各格式在 Compaction、并发写、引擎兼容性上的工程权衡；
   - **社区治理**：Tabular（Iceberg 原班人马）被 Databricks 收购后
     对 Iceberg 社区独立性的影响；Apple、Netflix、AWS 等公司在
     Spec 演进中的话语权博弈；与 Delta Lake（Linux Foundation）的
     治理模式对比；
   - **商业化视角**：Iceberg 作为"元数据层开放标准"的战略价值——
     为何 AWS（S3 Tables）、Google（BigLake）、Snowflake（Polaris）
     均选择拥抱 Iceberg；"支持 Iceberg"是否已成为数据平台的
     必选项而非差异化能力；

**参考资料：**
- https://iceberg.apache.org/spec/（Format Specification）
- https://github.com/apache/iceberg/releases
- https://iceberg.apache.org/blogs/
- *Iceberg: A High-Performance Format for Huge Tables*（Netflix Tech Blog）
- *Apache Iceberg: The Definitive Guide*（O'Reilly，2024）
- Puffin Spec：https://iceberg.apache.org/puffin-spec/
- REST Catalog Spec：https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml

**输出格式：**
文章结构建议：
**Executive Summary
→ Format Spec 演进（v1/v2/v3 核心差异）
→ 元数据层深度解析（Manifest / Snapshot / Catalog）
→ 并发控制与事务模型
→ Row-level Deletes 三种实现的工程权衡
→ 表维护机制（Compaction / Expire / Statistics）
→ 多引擎集成深度对比
→ REST Catalog 生态与云原生集成
→ 竞品对比（Delta Lake v3 / Hudi / DuckLake）
→ 社区治理与商业化博弈
→ 总结与展望**