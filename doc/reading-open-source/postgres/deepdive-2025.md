我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 PostgreSQL 的官方文档、官方 Release Notes、PostgreSQL Wiki、
Commitfest（补丁审查系统）、pgsql-hackers 邮件列表讨论、
以及 Crunchy Data / EDB / Supabase / Neon 等主要生态公司的技术博客
进行综合分析：

**注意**：PostgreSQL 是数据库领域的"基础设施"，本报告的核心价值在于
从**内核工程师视角**深挖其底层机制，而非泛泛介绍功能列表。

**分析维度要求如下：**

1. **重大 Feature 与场景支持**：总结近年来（重点聚焦 PG 15 → 16 → 17 → 18
   开发分支，2022–2025 年）最重要的内核演进：

   - **存储引擎演进**：PostgreSQL Heap 存储的历史债务——
     MVCC 实现导致的 Table Bloat（表膨胀）问题的根因
     （Dead Tuple 堆积、VACUUM 机制局限）；
     PG 17 的 VACUUM 增量处理改进；
     **Pluggable Storage API**（Table Access Method，PG 12 引入）
     的现状——TIDStore 优化（PG 17，VACUUM 效率提升）；
     Zedstore（列存 TAM）/ Orioledb（B-Tree TAM）
     等替代存储引擎的成熟度与主线合并前景；
   - **并行查询演进**：Parallel Query 从 PG 9.6 引入至今的
     能力扩展——Parallel Hash Join（PG 11）、
     Parallel Index Scan、Parallel Bitmap Heap Scan；
     Parallel Query 的 Worker 进程模型（背景 Worker）
     与 JVM 线程模型的本质差异；
     并行度上限的工程瓶颈（`max_parallel_workers_per_gather`
     与 CPU 核数的关系）；
   - **逻辑复制演进**：PG 16 的逻辑复制鉴权改进；
     PG 17 的 Logical Replication Slot Failover；
     逻辑复制在 Neon / Supabase 架构中的核心作用；
     与 MySQL binlog 复制的语义差异；
   - **PG 17 核心特性**：`MERGE` 语句的完善（`MERGE ... RETURNING`）；
     JSON 函数集（`JSON_TABLE` / `JSON_EXISTS` 等 SQL/JSON 标准）
     的实现；`COPY FROM ... ON_ERROR IGNORE` 容错导入；
     增量排序（Incremental Sort）的优化；
     异步 I/O 基础设施（AIO，PG 17 初步框架，PG 18 完善）；
   - **PG 18 开发分支**：异步 I/O（io_uring 支持）
     的架构设计与预期收益；
     OAuth 2.0 / OAUTHBEARER 认证支持；
     Virtual Generated Column 的实现；

2. **执行引擎与优化器深度**：

   - **查询优化器架构**：PG Optimizer 的 Genetic Query Optimizer
     （GEQO，大表 Join 时的启发式策略）与动态规划的切换阈值
     （`geqo_threshold`）；
     `enable_*` 系列 GUC 参数的底层含义
     （为什么 `enable_hashjoin=off` 能暴露 Optimizer Bug）；
     Cost Model 参数（`seq_page_cost` / `random_page_cost` /
     `cpu_tuple_cost`）与实际硬件（NVMe SSD vs HDD）的
     校准方法论；
     统计信息（`pg_statistic`）的 Histogram / MCV（Most Common
     Values）/ Correlation 的存储格式与采样策略；
   - **执行引擎**：Volcano（Iterator）模型的工程实现——
     每个算子的 `ExecProcNode` 函数指针调度；
     JIT 编译（LLVM，PG 11+）对表达式求值的加速原理
     与触发阈值（`jit_above_cost`）；
     为什么 PG 没有全算子向量化（技术债 + 社区保守策略）；
   - **WAL 机制深度**：WAL Record 的格式（Generic WAL vs
     Resource Manager WAL）；Full Page Write（FPW）
     对 WAL 体积的影响与 Checksum 的关系；
     WAL Compression（PG 15+）的实现；
     `wal_level` 各级别（minimal / replica / logical）
     对功能与性能的影响矩阵；
   - **Buffer Manager**：Clock-Sweep 替换算法的实现细节；
     Ring Buffer 策略（大表 Seq Scan 的 Buffer 保护）；
     Shared Buffer 与 OS Page Cache 的双重缓存问题
     （`direct I/O` 在 PG 中的讨论历史）；
     PG 17 的 Buffer Manager 锁竞争优化；

3. **扩展生态（Extension System）**：PostgreSQL 最强护城河：

   - **Extension 机制原理**：`pg_catalog` 系统表驱动的扩展注册；
     Hook 机制（`planner_hook` / `ExecutorRun_hook` 等）
     允许扩展介入执行路径的设计；
     Custom Scan API（`CustomScan` 接口）允许扩展提供
     自定义执行路径的机制（FDW / Columnar 存储的实现基础）；
   - **核心扩展深度**：
     `pg_partman`（分区管理）vs PG 原生分区的能力边界；
     `timescaledb`（时序数据）的 Chunk 架构与
     Continuous Aggregate 的实现；
     `pgvector`（向量检索）的 HNSW / IVFFlat 索引实现
     与 PG WAL 兼容的挑战；
     `pg_analytics` / `pg_duckdb`（DuckDB 嵌入 PG）
     的 FDW 架构与零拷贝数据交换；
     `Citus`（分布式 PG）的分片路由与分布式查询计划；
   - **FDW（Foreign Data Wrapper）**：FDW API V2 的
     Pushdown 能力（`deparseExpr` 系列函数）；
     `postgres_fdw` 的 Async Append 并行扫描（PG 14+）；
     为什么 FDW 的 Pushdown 能力天花板受限于 Optimizer
     的 RestrictInfo 传递机制；

4. **云原生 PostgreSQL 生态**：

   - **Neon（Serverless PG）**：存算分离架构——
     Pageserver（存储层，WAL 重放 + Page Cache）/
     Safekeeper（WAL 持久化 Quorum）/ Compute（无状态 PG 进程）
     三层架构的技术实现；
     Copy-on-Write Branch（数据库分支）的底层机制；
     与 Aurora PostgreSQL 的架构对比；
   - **Supabase**：基于 PG 的 BaaS 架构——
     PostgREST（RESTful API 自动生成）/
     pgvector（向量检索）/ Logical Replication（实时同步）
     的集成方式；RLS（Row Level Security）的工程实现；
   - **AlloyDB（Google）**：columnar engine 与 PG Heap 的
     混合存储架构；adaptive query routing 机制；

5. **技术综合洞察**：

   - **技术视角**：PG 进程模型（Process-per-Connection）的
     历史债务——为什么 PG 17 之前没有线程化；
     PG 17 后的线程化重构进展（`libpq` 线程安全改造）；
     与 MySQL InnoDB 引擎的 MVCC 实现对比
     （PG 的 Heap MVCC vs InnoDB 的 Undo Log MVCC）；
   - **作为兼容层基础设施**：为什么 CockroachDB / YugabyteDB /
     Neon / AlloyDB / Aurora 都选择 PG 协议兼容
     而非 MySQL 协议兼容（生态、扩展性、SQL 表达力）；
   - **性能边界**：PG 在哪些场景下输给 MySQL
     （高并发短事务 OLTP）；在哪些场景下输给
     专用 OLAP 系统（StarRocks / ClickHouse）；
     `pg_analytics` / `pg_duckdb` 是否能真正弥补 OLAP 差距；

**参考资料：**
- https://www.postgresql.org/docs/release/
- https://www.postgresql.org/about/featurematrix/
- https://wiki.postgresql.org/wiki/Roadmap
- pgsql-hackers 邮件列表存档
- *Architecture of a Database System*（Hellerstein et al., 2007）
- *The Internals of PostgreSQL*（http://www.interdb.jp/pg/）
- *PostgreSQL 14 Internals*（Egor Rogov，2023）

**输出格式要求：**
- 从内核源码视角切入，引用具体的源码文件/函数名
  （如 `src/backend/executor/nodeHashjoin.c`）和
  Commitfest 补丁链接支撑论点；
- 文章结构建议：
  **Executive Summary
  → 存储引擎：Heap MVCC 的设计债务与 Pluggable TAM 出路
  → Buffer Manager：Clock-Sweep + Ring Buffer + 双缓存问题
  → WAL 机制：FPW / Compression / logical 复制
  → 查询优化器：Cost Model 校准与统计信息精度
  → 执行引擎：Volcano 模型 + JIT + 向量化缺失的原因
  → 并行查询：Worker 进程模型的上限与未来
  → Extension 生态：Hook / FDW / CustomScan 机制
  → 云原生 PG 生态：Neon / Supabase / AlloyDB
  → 作为兼容层基础设施的战略地位
  → 总结与展望**；