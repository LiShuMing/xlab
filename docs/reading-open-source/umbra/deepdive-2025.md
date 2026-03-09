我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Umbra 的官方网站（umbra-db.com）、TUM 数据库组发表的学术论文
（VLDB/SIGMOD/CIDR）、Thomas Neumann 及其团队的技术演讲（VLDB Keynotes、
CMU Database Talks）、以及 Umbra 相关的公开基准测试报告进行综合分析。

**特别说明**：Umbra 是学术系统，**核心引擎未开源，无公开 Release Notes**。
因此本报告的主要信息来源是学术论文与公开演讲。对于论文未覆盖的实现细节，
应明确标注"论文未披露"或"推测"，严禁凭空捏造技术细节。
本报告的核心价值在于**系统梳理 Umbra 所代表的前沿数据库内核技术**，
为工业界系统（StarRocks/DuckDB/ClickHouse）的技术演进提供参照。

**分析维度要求如下：**

1. **Umbra 的系统定位与设计哲学**：

  - **HyPer 的继承与超越**：Umbra 是 Thomas Neumann 团队
     在 HyPer 之后的下一代系统——
     HyPer 的核心贡献（LLVM JIT 编译 + HTAP + MVCC）
     与 Umbra 的核心创新点（Buffer Management 重构 +
     Morph 算子 + 更激进的编译策略）的具体差异；
     为什么 HyPer 的某些设计在 Umbra 中被推翻；
  - **设计目标**：Umbra 对标的工作负载类型
     （TPC-H / TPC-DS / JOB——Join Order Benchmark）；
     在学术 benchmark 上的极限性能数字
     （与 DuckDB / MonetDB / Hyrise 的对比数据）；
     Umbra 作为"研究平台"的定位——
     哪些前沿技术在 Umbra 中验证后影响了工业界系统；

2. **Buffer Management：Umbra 最重要的创新之一**：

  - **论文**：*Rethinking Logging, Checkpoints, and Recovery
     for High-Performance Storage Engines*（VLDB 2020）
     及相关工作；
  - **传统 Buffer Manager 的问题**：
     固定 Page Size（通常 4KB/8KB/16KB）导致的
     内部碎片与跨 Page 数据结构的复杂性；
     Buffer Pool 的 Pin/Unpin 协议开销；
     随机 I/O 与 Page 边界对齐的摩擦；
  - **Umbra 的 Variable-Size Buffer Management**：
     支持可变大小内存区域（而非固定 Page）的
     Buffer Manager 设计——
     如何在可变大小 Region 上实现 Eviction 策略；
     与操作系统虚拟内存管理（mmap）的关系
     （Umbra 是否使用 mmap 及其原因）；
     与 DuckDB Buffer Manager（固定 256KB Block）
     的设计对比；
     对索引结构（B-Tree / ART）存储的影响；
  - **String Handling**：Umbra 对变长字符串的特殊处理——
     *Umbra: A Disk-Based System with In-Memory Performance*
     （CIDR 2020）中描述的 String Interning 与
     inline short string 优化；
     与 DuckDB / Velox 的 StringView（German String）
     设计的关系（Umbra String 是否是 German String 的
     原始出处）；

3. **编译执行引擎：超越 HyPer LLVM JIT 的下一代**：

  - **HyPer 的 LLVM Pipeline 回顾**：
     *Efficiently Compiling Efficient Query Plans for
     Modern Hardware*（VLDB 2011，Thomas Neumann）
     中 "Produce/Consume" 代码生成模型；
     为什么 LLVM JIT 编译在 HyPer 中取得巨大成功；
     LLVM JIT 的工程代价（编译延迟、内存占用）；
  - **Umbra 的 Machine Code Specialization**：
     Umbra 是否继续使用 LLVM，或转向更轻量的
     代码生成方案（Template Specialization /
     Custom Bytecode / WASM）；
     *Tidy Tuples and Flying Start: Fast Compilation
     and Fast Execution of Relational Queries in
     Umbra*（VLDB 2021）的核心贡献——
     "Flying Start" 机制（部分编译 + 解释执行混合，
     消除冷启动编译延迟）的具体实现；
     Adaptive Execution（在解释执行积累 Profile 信息
     后触发 JIT 编译）的切换阈值与实现；
  - **Pipeline Breaker 处理**：
     编译执行中 Blocking Operator（Hash Join Build /
     Sort / Aggregation）如何与 Pipeline 编译协同；
     Morph 算子（自适应切换执行策略的算子）
     的设计——*Morsel-Driven Parallelism: A NUMA-Aware
     Query Evaluation Framework for the Many-Core Age*
     （SIGMOD 2014）与 Umbra 编译执行的结合；

4. **查询优化器：学术界最先进的 CBO**：

  - **Join Order Optimization**：
     *Dynamic Programming Strikes Back*
     （VLDB 2008，Guido Moerkotte & Thomas Neumann）
     的 DPccp / DPhyp 算法——
     与传统 System-R 动态规划的区别
     （Connected Subgraph 枚举 vs 子集枚举）；
     *Linearized Chain Join Enumeration*（相关后续工作）；
     在 JOB（Join Order Benchmark，IMDB 数据集）
     上的 cardinality estimation 误差分析；
  - **Cardinality Estimation**：
     *Towards a Learning Optimizer for Shared Clouds*
     / *Flow-Loss: Learning Cardinality Estimates Is Not
     Enough*（相关 ML-based CE 论文）；
     Umbra 是否集成了 ML-based Cardinality Estimation；
     与传统 Histogram + MCV 方案的对比；
  - **Unnesting Correlated Subqueries**：
     *Unnesting Arbitrary Queries*
     （BTW 2015，Thomas Neumann & Alfons Kemper）
     的 General Unnesting 算法——
     为什么这是比 SQL:1999 标准描述的
     unnesting 更通用的方案；
     在 TPC-DS 复杂 Correlated Subquery 场景的
     实际收益；

5. **并发控制与 MVCC**：

  - **HyPer 的 MVCC 设计**：
     *Fast Serializable Multi-Version Concurrency Control
     for Main-Memory Database Systems*
     （SIGMOD 2015）——
     HyPer 的 MVCC 使用 Undo Buffer（而非 Delta Store）
     的设计选择；
     Serializable Snapshot Isolation（SSI）的实现；
     与 PostgreSQL Heap MVCC 的根本差异
     （In-place Update + Undo vs Append-only Heap）；
  - **Umbra 的 MVCC 演进**：
     是否继承 HyPer 的 MVCC 设计；
     针对 OLAP 工作负载的 MVCC 简化
     （只读事务的快速路径）；
  - **Logging & Recovery**：
     *Rethinking Logging, Checkpoints, and Recovery*
     中的创新点——
     与 ARIES 协议的差异；
     针对 NVM（非易失性内存）的 Recovery 优化；

6. **与工业界系统的技术影响链**：

  - **Umbra → DuckDB**：
     Thomas Neumann 是 DuckDB 的学术导师之一；
     DuckDB 明确引用了哪些 Umbra/HyPer 的技术
     （Morsel-Driven Parallelism / German String /
     Unnesting Algorithm / Push-based Execution）；
     DuckDB 在哪些地方与 Umbra 设计不同（工程务实 vs
     研究追求极限）；
  - **Umbra → Velox / Photon**：
     Velox（Meta）和 Photon（Databricks）借鉴了
     哪些 Umbra/HyPer 的执行引擎技术；
  - **Umbra → StarRocks**：
     StarRocks 的 CBO 优化器引用了
     Thomas Neumann 的哪些论文（Join Reorder /
     Subquery Unnesting）；
     StarRocks 的向量化引擎与 Umbra 编译执行
     在性能哲学上的差异（向量化 vs 编译）；

7. **学术影响力与技术前沿**：

  - **近年 TUM 数据库组的前沿工作**：
     *Photon: A Fast Query Engine for Lakehouse Systems*
     之外，TUM 在 Umbra 平台上发表的最新研究方向
     （Learned Index / GPU Execution /
     Disaggregated Memory / Serverless Query Processing）；
  - **Umbra 在学术 Benchmark 的地位**：
     在 TPC-H / JOB / TPC-DS 上与
     DuckDB / MonetDB / Hyrise / Velox 的
     最新性能对比数据；

**参考资料（核心论文清单，按重要性排序）：**
- *Umbra: A Disk-Based System with In-Memory Performance*
  （CIDR 2020，Neumann & Freitag）
- *Tidy Tuples and Flying Start: Fast Compilation and Fast
  Execution of Relational Queries in Umbra*（VLDB 2021）
- *Efficiently Compiling Efficient Query Plans for Modern
  Hardware*（VLDB 2011，HyPer JIT 编译奠基论文）
- *Morsel-Driven Parallelism: A NUMA-Aware Query Evaluation
  Framework for the Many-Core Age*（SIGMOD 2014）
- *Fast Serializable Multi-Version Concurrency Control for
  Main-Memory Database Systems*（SIGMOD 2015）
- *Dynamic Programming Strikes Back*（VLDB 2008）
- *Unnesting Arbitrary Queries*（BTW 2015）
- *Rethinking Logging, Checkpoints, and Recovery for
  High-Performance Storage Engines*（VLDB 2020）
- https://umbra-db.com/

**输出格式要求：**
- **每个技术论点必须标注来源论文**（作者、会议、年份）；
- 对于论文未覆盖的实现细节，**明确标注"论文未披露"**；
- 重点分析 Umbra 技术对工业界系统的**影响链**
  （哪些技术被 DuckDB / Velox / StarRocks 采用）；
- 文章结构建议：
  **Executive Summary
  → HyPer → Umbra：设计哲学的演进与突破
  → Variable-Size Buffer Management：固定 Page 的终结
  → German String / Umbra String：变长字符串的极致优化
  → 编译执行引擎：Flying Start + Adaptive Execution
  → Join Order Optimization：DPccp / DPhyp 算法深度解析
  → Cardinality Estimation：ML-based CE 的学术前沿
  → Correlated Subquery Unnesting：General Unnesting 算法
  → MVCC 与并发控制：Serializable SI 实现
  → 技术影响链：Umbra → DuckDB / Velox / StarRocks
  → TUM 数据库组前沿研究方向
  → 总结：学术极限与工程务实的张力**；


  # Umbra 数据库内核技术深度分析报告

### 学术极限与工程务实的张力——写给工业界内核工程师的技术参照

---

## Executive Summary

Umbra 是 TUM（慕尼黑工业大学）Thomas Neumann 团队在 HyPer 之后的下一代关系数据库研究系统，定位为"磁盘系统，内存性能"（*Disk-Based System with In-Memory Performance*，CIDR 2020，Neumann & Freitag）。它并非 HyPer 的简单演进，而是在存储架构上进行了根本性重构：以可变大小页（Variable-Size Pages）替换传统固定页，同时继承并超越了 HyPer 的 LLVM JIT 编译执行引擎。

Umbra 的学术地位在于：它是一个**活的研究平台**，众多已被工业界采纳的核心技术——German String、DPhyp 连接枚举、Unnesting 算法、Morsel-Driven 并行、Serializable MVCC——均在此平台上验证或发源。2024 年，TUM 团队将 Umbra 商业化，成立了 **CedarDB**。

**核心技术影响链**：Umbra/HyPer → DuckDB（优化器、MVCC、ART Index、German String）→ Velox/Apache Arrow（StringView）→ StarRocks（Cascades 优化器框架、子查询消除思路）。

---

## 一、HyPer → Umbra：设计哲学的演进与突破

### 1.1 HyPer 的核心贡献

HyPer（2011 年由 TUM 推出，后被 Tableau/Salesforce 收购）奠定了以下技术基础：

**LLVM JIT 编译执行（VLDB 2011，Thomas Neumann）**：论文 *Efficiently Compiling Efficient Query Plans for Modern Hardware* 提出了"数据中心代码生成"（Data-Centric Code Generation）模型。与 Volcano/Iterator 模型相比，HyPer 采用 Produce/Consume 模式，将整个查询 Pipeline 编译为单一连续函数，彻底消除了虚函数调用开销和 tuple-at-a-time 的控制流跳转，充分利用 CPU 寄存器和 L1/L2 缓存。这一设计在 TPC-H 等基准上展现了远超解释执行引擎的性能。

**HTAP + MVCC**：HyPer 利用 OS 的 fork() Copy-on-Write 机制实现了 HTAP——OLTP 事务在主进程运行，OLAP 查询在 fork 出的只读快照子进程运行，互不干扰。这一机制极具创意，但在磁盘化场景下面临根本挑战。

**Morsel-Driven Parallelism（SIGMOD 2014，Leis 等人）**：将查询执行分解为 Morsel（小批量数据块），由工作线程动态竞争处理，实现了 NUMA-aware 的细粒度并行调度。

### 1.2 为什么 HyPer 的某些设计在 Umbra 中被推翻

HyPer 是**纯内存系统**（pure in-memory），假设所有数据常驻内存。当数据规模超过 DRAM 时，HyPer 无法优雅降级。CIDR 2020 论文指出：DRAM 价格高企且增长放缓，而 SSD 价格持续下降、带宽已达 GB/s 量级，这使得"大内存缓冲区 + 高速 SSD"的架构具有极高性价比。

Umbra 的核心改变：
- **抛弃纯内存假设**：引入 Buffer Manager，支持超内存工作集
- **重构存储层**：以可变大小页替换 HyPer 的行存结构
- **编译执行升级**：引入 Flying Start，解决 LLVM 冷启动延迟问题
- **HyPer fork() HTAP 机制被放弃**（推测：与 Buffer Manager 协作的复杂性，论文未披露完整原因）

### 1.3 设计目标与 Benchmark 定位

Umbra 面向以下工作负载：
- **TPC-H / TPC-DS**：经典 OLAP 分析基准
- **JOB（Join Order Benchmark，IMDB 数据集）**：专门测试连接顺序优化能力，含大量复杂多表连接

VLDBJ 2021 论文（Tidy Tuples and Flying Start）中的实验数据：在小数据集上，Umbra 的查询延迟甚至快于 DuckDB 和 PostgreSQL 等解释型引擎；在大数据集吞吐量上与 HyPer 持平。这一"低延迟 + 高吞吐"的双重目标，正是 Flying Start 机制的设计动机。

---

## 二、Variable-Size Buffer Management：固定 Page 的终结

**核心论文**：*Umbra: A Disk-Based System with In-Memory Performance*（CIDR 2020，Neumann & Freitag）；*LeanStore: In-Memory Data Management beyond Main Memory*（ICDE 2018，Leis 等人）

### 2.1 传统 Buffer Manager 的问题

传统 Buffer Manager（如 PostgreSQL 的 8KB 固定页、InnoDB 的 16KB 页）存在以下问题：
1. **内部碎片**：可变长数据（如大字符串、B-Tree 节点）被迫跨多个固定大小页存储，需要额外的间接层
2. **Pin/Unpin 协议开销**：每次访问页面需要通过中心化 Page Table 查找，即使数据在内存中也有多次内存间接访问
3. **随机 I/O 与页边界对齐的摩擦**：固定页大小对大对象（如 B-Tree 根节点频繁访问的大页）不友好

### 2.2 LeanStore：Umbra Buffer Manager 的基础

LeanStore（ICDE 2018）引入了**指针置换**（Pointer Swizzling）技术：Buffer Frame 中存储的不是 Page ID，而是直接的内存指针（已置换状态，Swizzled）或 Page ID（未置换状态，Unswizzled）。通过指针标记位区分两种状态，在 In-Memory 路径上实现了**零额外间接层**——访问内存中的页面只需一次指针解引用，与纯内存系统性能相当。

### 2.3 Umbra 的可变大小页设计

Umbra 在 LeanStore 基础上扩展了**可变大小页（Variable-Size Pages）**支持，这是目前已知（CIDR 2020 论文声称）继 ADABAS 系统之后唯一支持可变页大小的 Buffer Manager，且远比 ADABAS 的双页大小方案灵活。

**核心设计**（来源：CIDR 2020 论文，dbdb.io 记录）：
- 页大小按**2 的幂次**组织成 Size Class，最小页 64 KiB，最大理论上可达整个 Buffer Pool
- 同一 Size Class 的所有页在虚拟地址空间中**连续分配**：每个 Size Class 预留一段等于整个 Buffer Pool 大小的虚拟地址区间，通过 `mmap()` 创建私有匿名映射（**不预分配物理内存**）
- 读取时通过 `pread()` 将磁盘数据加载到对应虚拟地址，由内核建立物理映射；驱逐时通过 `pwrite()` 写回，再用 `madvise()` 释放物理内存

**关于 mmap 的使用**：Umbra **使用了 mmap**，但仅用于虚拟地址空间预留，并非用 mmap 来做 I/O（避免了 OS mmap 的 Page Fault 不可控问题）。实际 I/O 通过 `pread/pwrite` 完成，这是一种精心设计的折中。

**Eviction 策略**（论文未披露具体算法细节，推测继承 LeanStore 的 CLOCK 类算法）：LeanStore 使用基于随机采样的 Cooling Stage 机制，Umbra 的扩展论文未单独披露可变页 Eviction 的完整实现。

### 2.4 与 DuckDB Buffer Manager 的对比

| 维度 | Umbra | DuckDB |
|------|-------|--------|
| 页大小 | 可变（64KiB 起，2 的幂次） | 固定 256KiB Block |
| 间接层 | 零（Pointer Swizzling） | 传统 Block Handle |
| I/O 机制 | pread/pwrite + mmap（虚拟地址预留） | 异步 I/O |
| 工程复杂度 | 极高（指针置换渗透整个系统） | 相对简单 |
| 大对象支持 | 原生（可变页天然适配） | 需要 overflow pages |

### 2.5 对索引结构的影响

可变页大小对 B-Tree / ART（Adaptive Radix Tree）索引的存储有重要意义：B-Tree 的根节点和靠近根的内部节点访问频率远高于叶节点，可以存储在更大的页中以减少 I/O 次数；叶节点可使用小页。Umbra 的 B²-Tree（BTW 2021，Schmeißer 等人）即利用了可变页特性，在 B+-Tree 页内嵌入基于 Trie 的搜索树，提升了字符串索引的缓存效率。

---

## 三、German String / Umbra String：变长字符串的极致优化

**核心来源**：*Umbra: A Disk-Based System with In-Memory Performance*（CIDR 2020）中的字符串表示描述；CedarDB 官方博客 *Why German Strings are Everywhere*

### 3.1 设计原理

Umbra 为数据处理场景设计了一种特殊的**16 字节定长字符串结构体**（128-bit struct），包含以下两种表示：

**短字符串（≤ 12 字节）**：
```json
[4B length | 12B inline content]
```
全部内容内联存储，无需任何指针解引用，直接通过寄存器传递。

**长字符串（> 12 字节）**：
```json
[4B length | 4B prefix | 4B buffer_id | 4B offset]
```
存储 4 字节前缀（用于快速比较/过滤）和指向实际数据的间接引用（buffer_id + offset，而非裸指针，便于跨 Buffer 管理）。

**关键性能收益**：
- 等值比较可先比较 4 字节前缀，大量情况无需访问实际字符串数据
- 短字符串零拷贝、零解引用，极大提升缓存局部性
- 16 字节大小可通过两个寄存器传参（而非 std::string 的 24 字节需要入栈）
- e6data 基准测试报告过滤和连接场景等值比较快 3–3.5 倍；Apache DataFusion 集成后字符串密集查询端到端提升达 20%–200%

### 3.2 German String 的名称由来与影响链

这一设计被 Andy Pavlo（CMU）在其高级数据库课程中戏称为 "German-style Strings"（德式字符串），以致敬其来自德国 TUM 的学术血统，后简称 "German Strings"，名称沿用至今。CedarDB 团队表示，他们最初并未预料到这个设计会被如此广泛采用。

**技术影响链**：
- **DuckDB**：原生使用 German String 格式，用于向量化执行中的字符串列
- **Meta Velox**：内部使用类似的 StringView 表示（16 字节，含前缀内联），与 Umbra 格式高度一致
- **Apache Arrow（v15.0.0）**：新增 `StringView` 类型（Arrow 15，2024 年），与 Velox 合作推动标准化，正式承认"与 Umbra 和 DuckDB 采用类似方案"
- **Apache DataFusion / Polars**：通过 Arrow StringView 间接采用
- **CedarDB**：Umbra 的商业化版本，直接延续

---

## 四、编译执行引擎：Flying Start + Adaptive Execution

**核心论文**：*Tidy Tuples and Flying Start: Fast Compilation and Fast Execution of Relational Queries in Umbra*（VLDBJ 2021，Kersten、Leis、Neumann）；*Adaptive Execution of Compiled Queries*（ICDE 2018，Kohn、Leis、Neumann）

### 4.1 HyPer LLVM Pipeline 回顾

HyPer（VLDB 2011）的 "Produce/Consume" 模型将整个 Pipeline 编译为紧凑的 LLVM IR，再通过 LLVM 后端生成机器码。这一方案的工程代价显而易见：

- **编译延迟**：即使是中等复杂度查询，LLVM 优化编译也需要**数百毫秒**
- 对于 Interactive Ad-hoc 查询（数据集较小），编译时间远超实际执行时间
- HyPer 的应对方案是 Adaptive Execution（ICDE 2018）：引入 LLVM Bytecode Interpreter（快速启动但执行慢）和 LLVM 编译后端（启动慢但执行快）两条路径，运行时动态切换

**HyPer 的困境**：Bytecode Interpreter 执行速度太慢（无法有效消除解释开销），而关闭大部分优化的 LLVM 编译虽然快一些，但仍有较高开销。两条路径各有明显短板，形成"性能缺口"（performance gap）。

### 4.2 Umbra 的突破：Umbra IR + Flying Start

Umbra 的核心创新是引入**三层架构**（VLDBJ 2021）：

**① Tidy Tuples（代码生成框架）**
- 所有 Pipeline 的代码生成通过单趟（single pass）完成，避免多轮 IR 转换开销
- 为代码生成建立清晰的抽象层（Abstraction），管理 NULL 处理、类型系统等复杂性
- 采用 SQLValue 抽象统一处理不同数据类型的代码生成

**② Umbra IR（自定义中间表示）**
- 语义上类似 LLVM IR，但**专为查询编译场景设计**：放弃了 LLVM IR 支持任意变换（instruction reordering/replacement/deletion）的通用性，换取写入和读取速度
- 所有指令存储在连续动态数组中（内存局部性好），指令间互引用使用 4 字节偏移而非指针（节省内存）
- 代码生成时直接写入 Umbra IR，无需构建 AST 再转换

**③ Flying Start（默认编译后端）**
- **核心思路**：绕过 Bytecode Interpreter，直接将 Umbra IR 一趟翻译为 x86 机器码，同时在翻译过程中应用轻量级优化（地址计算合并、比较-分支融合等）
- **编译速度**：达到与 Bytecode Interpreter 相当的编译速度，但生成的是原生机器码，无解释开销
- **寄存器分配**：使用近似 Live Interval（线性扫描变体），在线性时间内完成，避免复杂数据流分析

**Adaptive Execution 的完整三路径**：
1. **Flying Start**（默认，低延迟启动）：毫秒级编译 + 较快执行
2. **LLVM 优化编译**（大数据集，长查询）：百毫秒级编译 + 最快执行
3. 在运行时动态切换——甚至可以在一个查询**执行一半时**切换后端

**切换阈值**（论文未完整披露具体数值）：系统会在 Flying Start 积累一定执行量后，判断是否值得触发 LLVM 优化编译。

**实验结论**（VLDBJ 2021）：在 TPC-H Query 2（SF=1，4 线程）上，Umbra 的新引擎"组合编译延迟 + 执行时间"在所有已知选项中最优。在小数据集上甚至比解释执行的 DuckDB 和 PostgreSQL 更快。

### 4.3 Pipeline Breaker 与并行执行的协同

Blocking Operator（Hash Join Build Phase、Sort、Aggregation）是编译执行的"Pipeline Breaker"。Umbra 的处理方式（基于 Morsel-Driven Parallelism，SIGMOD 2014）：
- Pipeline 执行以 Morsel 为单位，工作线程动态从 Source 竞争数据块
- Hash Join 的 Build Phase 完成后，才启动 Probe Phase 的下一个 Pipeline
- Aggregation 采用线程本地哈希表 + 合并的策略，减少争用

### 4.4 多架构支持：FireARM for AArch64

VLDB 2023 论文 *Bringing Compiling Databases to RISC Architectures*（Gruber 等人）展示了 Umbra 团队为 AArch64 开发 FireARM 代码生成后端的工作——这验证了 Flying Start 框架的可移植性，也反映了 ARM 服务器（AWS Graviton）对学术系统的影响。

---

## 五、Join Order Optimization：DPccp / DPhyp 算法深度解析

**核心论文**：*Dynamic Programming Strikes Back*（VLDB/SIGMOD 2008，Moerkotte & Neumann）；*Adaptive Optimization of Very Large Join Queries*（SIGMOD 2018，Neumann & Radke）

### 5.1 传统 System-R 动态规划的局限

System-R（1979）的连接枚举算法基于**子集枚举**：枚举所有 2^n 个关系子集，对每个子集寻找最优计划。这种方案：
- 只能处理二元（Binary）等值连接谓词
- 不支持非内连接（Outer Join）等复杂连接类型
- 对 Cross Product 的处理会导致搜索空间爆炸

### 5.2 DPccp：基于连通子图的枚举

DPccp（Dynamic Programming on Connected Complement Pairs）将连接图建模为**无向图**，仅枚举图的**连通子图（Connected Subgraph）**，避免产生 Cross Product。对于稀疏连接图（OLAP 查询的典型情况），这大幅减少了搜索空间。

### 5.3 DPhyp：超图 + 非内连接支持

DPhyp（Dynamic Programming on Hypergraphs）是 DPccp 的重要扩展（VLDB 2008，Moerkotte & Neumann）：
- 将查询图建模为**超图（Hypergraph）**：超边（Hyperedge）可连接 2 个以上关系，表达复杂谓词（如 R.a + S.b = T.c）
- 引入了处理 Outer Join、Anti Join 等非内连接的框架
- 实验表明，对于含复杂谓词的查询，与传统算法相比优化时间可提升**数量级**

**DPhyp 是 DuckDB 今日使用的连接枚举算法**（DuckDB 论文明确引用 Moerkotte & Neumann 2008）。

### 5.4 超大连接查询的自适应优化

SIGMOD 2018 论文（Neumann & Radke）处理了实际生产中出现的极端情况：有些 BI 工具自动生成的查询可包含**数千个连接**。论文提出了自适应优化框架：
- 小型查询（≤ 某阈值）使用精确的 DPhyp 求最优解
- 大型查询切换为启发式算法（搜索空间线性化），保持接近最优
- 据报告，现实中最大的查询访问超过 4,000 个关系

---

## 六、Cardinality Estimation：学术前沿

**核心论文**：*Every Row Counts: Combining Sketches and Sampling for Accurate Group-By Result Estimates*（CIDR 2019，Freitag & Neumann）；*Concurrent online sampling for all, for free*（DaMoN 2020，Birler 等人）

### 6.1 Umbra 的统计与采样机制

Umbra 官网描述：采用 Sketches（素描统计）和 Sampling（采样）结合的方式估算结果大小和查询代价。具体包括：
- **Reservoir Sampling**（水库采样）：支持在实时插入过程中维持始终最新的随机样本（SIGMOD 2019、DaMoN 2020），无需周期性重建
- 在线并发采样，对插入吞吐量几乎**零开销**
- Group-By 结果大小的估算（CIDR 2019）：结合 Column Sketch + 随机样本，修正属性相关性偏差

**关于 ML-based Cardinality Estimation**：Umbra 官网和已发表论文（截至本报告知识截止日期）未明确宣称集成 ML-based CE 作为默认优化器组件。相关学术探索在 TUM 周边有进展（论文未披露 Umbra 是否直接集成）。

### 6.2 Aggregate Estimates（VLDB 2021）

论文 *A Practical Approach to Groupjoin and Nested Aggregates*（VLDB 2021，Fent & Neumann）提出了对 GROUP BY 后结果分布的统计估计方法，使优化器能对 Aggregation 结果上的谓词做出准确 Cardinality 估计——这对 TPC-H/TPC-DS 中常见的 Groupjoin 模式（约占 1/8 查询）尤为重要。

---

## 七、Correlated Subquery Unnesting：General Unnesting 算法

**核心论文**：*Unnesting Arbitrary Queries*（BTW 2015，Thomas Neumann & Alfons Kemper）

### 7.1 问题背景

相关子查询（Correlated Subquery）是 SQL 中最难优化的特性之一。SQL:1999 标准描述的 Unnesting 方法基于一系列手工规则，覆盖范围有限。对于 TPC-DS 中复杂的嵌套查询，传统系统往往退化为 Nested Loop 执行。

### 7.2 General Unnesting 的核心思想

Neumann & Kemper 2015 提出的算法基于**Dependent Join（依赖连接）**的代数框架：

1. 将相关子查询表达为带外部绑定集合 D 的依赖连接
2. 通过代数变换规则，将 D **向下推（push down）**，直到连接不再依赖外部参数
3. 转化为普通的 Groupjoin 或普通连接执行

**核心条件**：当子查询算子树中某个节点的自由变量集合 `F(T)` 与外部绑定集 `A(D)` 不相交时（`F(T) ∩ A(D) = ∅`），即可完成解嵌套。

这一框架**通用性远超 SQL:1999 规则**：可处理任意嵌套结构，包括多层嵌套、EXISTS/IN/量化子查询等，且能转化为高效的 Groupjoin，而非退化的 Nested Loop。

### 7.3 工业影响

DuckDB 官方文档明确列出 *Unnesting Arbitrary Queries*（Neumann & Kemper 2015）为其优化器子查询处理模块的直接参考。这使 DuckDB 在 TPC-DS 上能高效处理 99 条标准查询中大量包含相关子查询的语句。

---

## 八、MVCC 与并发控制

**核心论文**：*Fast Serializable Multi-Version Concurrency Control for Main-Memory Database Systems*（SIGMOD 2015，Neumann、Mühlbauer、Kemper）；*Memory-Optimized Multi-Version Concurrency Control for Disk-Based Database Systems*（VLDB 2022，Freitag、Kemper、Neumann）

### 8.1 HyPer 的 MVCC 设计

SIGMOD 2015 论文提出了一种**面向主内存的轻量级 MVCC 实现**，与 PostgreSQL MVCC 有根本差异：

| 维度 | HyPer MVCC（SIGMOD 2015） | PostgreSQL MVCC |
|------|---------------------------|-----------------|
| 版本存储位置 | **Undo Buffer**（独立的内存区域） | Heap 内（Append-only，旧版本留在数据页） |
| 更新方式 | **In-place Update + Undo** | Append-only（新 tuple 写入堆，旧 tuple 保留） |
| 读操作可见性判断 | 通过 Undo Buffer 回溯版本链 | 通过 xmin/xmax 判断 tuple 可见性 |
| 死元组清理 | Undo Buffer 周期性回收（基于高水位标记） | 需要 VACUUM 定期清理 |
| 隔离级别 | **完全可串行化（SSI）** | 默认 Read Committed，SSI 需额外机制 |
| 谓词锁 | 使用**谓词日志（Predicate Log）**记录读集，范围粒度 | 使用 SIREAD 锁（Predicate Locking） |

HyPer 的关键特性：与 Hekaton（SQL Server）和 PostgreSQL 不同，**不在索引结构中存储版本信息**——版本历史集中存储在 Undo Buffer 中，索引始终指向最新版本，大幅简化了索引管理。实验结果表明，即使在完全可串行化的条件下，开销相比单版本串行执行也极小，使"没有理由继续选择 SI 而非完整可串行化"成为可能。

### 8.2 Umbra 的 MVCC 演进

VLDB 2022 论文（Freitag 等人）专门针对**磁盘基（Disk-Based）场景**扩展了 MVCC：
- 关键创新：**绝大多数版本信息可完全在内存中维护，无需持久化到磁盘**
- 内存中维护版本的开销极低；对于极少数写事务（大规模批量写），通过轻量级 Fallback 机制处理（论文称此类事务"极为罕见"）
- 实验结果：事务吞吐量比同类磁盘系统高达**一个数量级**

### 8.3 与 ARIES 的差异

传统 ARIES 协议（Write-Ahead Logging）要求每次更新都写 Undo/Redo 日志到持久化存储。Umbra 的 MVCC 机制通过"版本信息主要维护在内存"的设计，**大幅减少了日志 I/O**——多数 MVCC 版本信息无需落盘，只有事务的 Redo 信息需要持久化（论文未完整披露 Redo 日志的全部实现细节，标注：论文部分未披露）。

---

## 九、技术影响链：Umbra → DuckDB / Velox / StarRocks

### 9.1 Umbra → DuckDB

DuckDB 的官方文档（Why DuckDB 页面）明确列出来自 TUM 的技术来源：

| DuckDB 模块 | 来源论文/系统 |
|------------|-------------|
| 优化器（Join Order） | *Dynamic Programming Strikes Back*（Moerkotte & Neumann 2008） |
| 子查询消除 | *Unnesting Arbitrary Queries*（Neumann & Kemper 2015） |
| MVCC | *Fast Serializable MVCC for Main-Memory DBMS*（Neumann 等 2015） |
| ART 索引 | *The Adaptive Radix Tree*（Leis、Kemper、Neumann） |
| Window Functions | Leis、Kemper、Neumann 相关论文 |
| 字符串表示 | German String（Umbra CIDR 2020） |
| 并行执行框架 | Morsel-Driven Parallelism（SIGMOD 2014） |

**DuckDB 与 Umbra 的关键差异**（工程务实 vs 研究极限）：
- DuckDB 使用**向量化解释执行**（Vectorized Execution），而非编译执行——降低工程复杂度，提升可移植性
- DuckDB 使用**固定 256KiB Block** Buffer Manager，而非 Umbra 的可变页设计
- DuckDB 面向单节点嵌入式场景，无分布式计划；Umbra 定位通用高性能 DBMS

### 9.2 Umbra → Velox / Photon

- **Meta Velox**：借鉴了 Morsel-Driven Parallelism 的并行执行思想，以及 StringView（German String 的同类设计）。Velox 与 Apache Arrow 合作将 StringView 纳入 Arrow 15.0 标准（2024 年），Meta 工程博客明确提及"与 Umbra 和 DuckDB 采用类似字符串表示"
- **Databricks Photon**（论文未具体列明 Umbra 引用，论文未披露直接引用关系）：作为编译执行引擎，Photon 在技术思路上与 HyPer/Umbra 路线高度一致，但具体实现细节未开源

### 9.3 Umbra → StarRocks

StarRocks 的 CBO 框架基于 **Cascades 框架**（非直接来自 Umbra，而是源自 Cascades/ORCA），但大量引用了 Neumann 团队的技术：

- **Join Reorder**：StarRocks 文档和工程博客描述的 Join Reorder 实现（动态规划 + 贪心算法混合策略）在思路上与 DPccp/DPhyp 系列工作一致（但具体实现论文未在 StarRocks 官方源码引用中明确标注直接来源，**标注：推测影响，非直接引用确认**）
- **子查询改写**：StarRocks 支持 Correlated Subquery 的 Unnesting/Rewriting，实现思路与 Neumann & Kemper 2015 工作高度一致
- **执行引擎对比**：StarRocks 采用**全向量化执行**（非 JIT 编译），这是与 Umbra 最根本的差异——向量化通过 SIMD 批处理获得性能，编译执行通过消除解释开销获得性能；两者在 Cache 敏感型工作负载（Umbra 优势）和大数据集扫描（向量化优势）上各有优劣（来自 VLDB 2018 对比论文 *Everything You Always Wanted To Know About Compiled and Vectorized Queries*，Kersten 等人）

---

## 十、TUM 数据库组前沿研究方向

基于 umbra-db.com 公开论文列表（截至 2024 年），TUM 数据库组在 Umbra 平台上的最新研究包括：

**① 云对象存储与分解存储**
- **AnyBlob**（VLDB 2023，Durner、Leis、Neumann）：面向云对象存储（AWS S3 等）的高性能下载管理器，基于 `io_uring` 实现异步 I/O，最大化吞吐同时最小化 CPU 占用。实验表明，Umbra + AnyBlob 在无本地缓存的情况下达到与缓存数据在本地 SSD 的云数仓相当的性能
- **Colibri**（VLDB 2024，Schmidt、Durner、Leis、Neumann）：面向云的 HTAP 混合列行存储引擎，支持超内存的混合事务分析处理

**② 鲁棒连接处理**
- **Diamond Hardened Joins**（VLDB 2024，Birler、Kemper、Neumann）：解决"菱形问题"（Diamond Problem）——当连接产生大量中间结果后又被消除时，传统二元连接效率极低。通过将 Join 算子拆分为 Lookup & Expand 两个子算子，允许优化器自由重排，在 CE benchmark 上某些查询提升高达 **500 倍**，在 TPC-H 和 JOB 上性能持平

**③ 高效哈希表**
- **Unchained Hash Table**（DaMoN 2024）：结合 Build 侧分区、邻接数组布局、流水线化 Probe、Bloom Filter 和软件 Write-Combine Buffer，在含倾斜的 N:M 连接上比 Open Addressing 快 2 倍，在图处理查询上快 20 倍

**④ 查询调度与流处理**
- **Self-Tuning Query Scheduling**（SIGMOD 2021）：无锁自调优步幅调度器，尾延迟比传统系统改善超 10 倍
- 关系型流处理集成（CDMS 2023）：在 DBMS 内部直接处理高速数据流

**⑤ 代码生成扩展**
- **RISC 架构适配**（VLDB 2023）：FireARM 后端将编译执行扩展到 AArch64/ARM 平台
- **Adaptive Query Processing**（ADMS 2022）：Dynamic Blocks 技术，在不重新编译的情况下支持运行时调整连接顺序和选择算子，性能提升超 2 倍

**⑥ 机器学习与数据库融合**
- GPU 上的 In-Database ML（SSDBM 2021）：通过自动微分和 GPU Kernel 在 SQL 中直接训练模型
- 在 Umbra 中集成 ArrayQL，直接支持矩阵代数

**商业化**：2024 年，Umbra 核心团队从 TUM 分拆，成立 **CedarDB**，将上述研究成果商业化。

---

## 十一、总结：学术极限与工程务实的张力

| 技术维度 | Umbra（学术极限） | DuckDB（工程务实） | StarRocks（工业分布式） |
|---------|-------------------|-------------------|----------------------|
| 执行引擎 | 编译执行（Flying Start + LLVM） | 向量化解释执行 | 全向量化（SIMD） |
| Buffer Manager | 可变页（64KiB 起，指针置换） | 固定 256KiB Block | 固定大小列块 |
| 字符串 | German String（原始出处） | German String（采用） | 标准字符串 + 低基数字典优化 |
| Join 优化 | DPhyp 超图枚举 | DPhyp（直接引用） | Cascades + 贪心混合 |
| 子查询 | General Unnesting（原始出处） | 直接引用 BTW 2015 | Unnesting + Rewrite |
| MVCC | Serializable SSI + Predicate Log | 受 HyPer SIGMOD 2015 启发 | 不涉及（OLAP 主导） |
| 部署形态 | 单节点研究系统 | 单节点嵌入式库 | 分布式 MPP |
| 开源程度 | Docker 镜像（核心不开源） | 完全开源 | 完全开源 |

**核心洞察**：Umbra 代表了当前学术界对"单节点 OLAP/HTAP 性能极限"最前沿的探索。它的价值不在于可以直接工程化移植，而在于**提供了技术可行性的证明**，以及一套完整的设计哲学：从 Buffer 管理到代码生成，每一层都在消除不必要的抽象开销。

对于 StarRocks 这样的工业系统而言，最有参考价值的技术演进方向是：

1. **Variable-Size Buffer Management 的思路**：StarRocks 的存储列块大小调优可借鉴可变页的灵活性设计
2. **Flying Start 类机制**：在 StarRocks 的 Pipeline 执行框架中，对于短 Query（低延迟场景）引入轻量级 JIT 或 Template Specialization 是可探索方向
3. **German String**：StarRocks 目前的字符串处理可评估引入前缀内联的收益，尤其在 JOIN 和 LIKE 过滤密集场景
4. **Diamond Hardened Joins**（VLDB 2024）：对于含大量 N:M 连接的图查询和复杂 OLAP 场景，Lookup & Expand 的分解思路值得关注
5. **Groupjoin + Nested Aggregates**（VLDB 2021/2022）：TPC-DS 中 1/8 查询含 Groupjoin 模式，引入专用算子可带来显著收益

---

## 参考文献

| 论文 | 会议/期刊 | 年份 |
|-----|-----------|------|
| *Umbra: A Disk-Based System with In-Memory Performance*，Neumann & Freitag | CIDR | 2020 |
| *Tidy Tuples and Flying Start: Fast Compilation and Fast Execution*，Kersten、Leis、Neumann | VLDBJ | 2021 |
| *Efficiently Compiling Efficient Query Plans for Modern Hardware*，Neumann | VLDB | 2011 |
| *Morsel-Driven Parallelism*，Leis 等 | SIGMOD | 2014 |
| *Fast Serializable MVCC for Main-Memory Database Systems*，Neumann 等 | SIGMOD | 2015 |
| *Memory-Optimized MVCC for Disk-Based Systems*，Freitag 等 | VLDB | 2022 |
| *Dynamic Programming Strikes Back*，Moerkotte & Neumann | VLDB | 2008 |
| *Unnesting Arbitrary Queries*，Neumann & Kemper | BTW | 2015 |
| *LeanStore: In-Memory Data Management beyond Main Memory*，Leis 等 | ICDE | 2018 |
| *Adaptive Execution of Compiled Queries*，Kohn、Leis、Neumann | ICDE | 2018 |
| *Exploiting Cloud Object Storage for High-Performance Analytics*，Durner 等 | VLDB | 2023 |
| *Robust Join Processing with Diamond Hardened Joins*，Birler 等 | VLDB | 2024 |
| *Two Birds With One Stone: Colibri HTAP Storage Engine*，Schmidt 等 | VLDB | 2024 |
| *Everything You Always Wanted to Know About Compiled and Vectorized Queries*，Kersten 等 | VLDB | 2018 |
| *A Practical Approach to Groupjoin and Nested Aggregates*，Fent & Neumann | VLDB | 2021 |
| *Adaptive Optimization of Very Large Join Queries*，Neumann & Radke | SIGMOD | 2018 |
| umbra-db.com（官方网站） | — | — |
| cedardb.com/blog/german_strings | — | — |

---

*本报告基于公开学术论文、官方网站及技术博客整理。核心引擎实现细节（如 Eviction 完整算法、Adaptive Execution 具体切换阈值等）如未在论文中明确披露，均已标注"论文未披露"或"推测"。*
