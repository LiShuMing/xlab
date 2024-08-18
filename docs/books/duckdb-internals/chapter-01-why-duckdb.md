# 第1章：DuckDB 为什么存在

> 万物有来处。在深入一行行源码之前，先回答一个本质问题：DuckDB 解决的是什么问题？为什么这个世界需要一个全新的嵌入式 OLAP 数据库？

## 1.1 嵌入式数据库的历史脉络

### SQLite：嵌入式数据库的"标准答案"

如果你问一个工程师"进程内数据库用什么"，过去二十年的答案几乎只有一个：SQLite。

SQLite 创造了奇迹——它是世界上部署最广泛的数据库，存在于每一台智能手机、每一个浏览器、每一辆汽车中。它的设计哲学简洁而极致：

- **零配置**：没有服务器进程，没有端口监听，一个文件就是一个数据库
- **零依赖**：完整的 SQL 引擎压缩在约 600KB 的单个 C 文件中（amalgamation）
- **事务完整**：支持 ACID，采用读写锁的并发模型

但 SQLite 有一个结构性局限：它是为 OLTP 设计的。它的执行引擎采用经典的 Volcano（迭代器）模型——一次处理一行（row-at-a-time），这在事务型负载下足够高效，但在分析型负载下是灾难性的。一个 `SELECT COUNT(*)` 也需要遍历所有行，而无法利用列式布局和向量化计算。

### MonetDBLite：一次未竟的尝试

2015 年前后，CWI（荷兰数学与计算机科学中心）的研究人员看到了一个缺口：能否把成熟的列式分析引擎 MonetDB 做成嵌入式的？

MonetDB 是列式数据库的先驱之一，它的 BAT（Binary Association Table）代数算子已经证明了列式计算的威力。MonetDBLite 的尝试是将 MonetDB 的内核压缩成一个可嵌入的库，允许 Python/R 用户直接在进程中运行分析型 SQL。

然而，MonetDBLite 犯了方向性的错误：它不是重新设计一个嵌入式引擎，而是把一个全功能的服务器端引擎强行塞进库中。结果一头撞上了架构上的矛盾：

1. **MonetDB 假设独占机器**：它的内存管理、线程调度都假设它是唯一的"王者"，这与嵌入式中"进程内的客人"角色冲突
2. **优化器过于激进**：MonetDB 的优化策略是大规模物化中间结果，内存消耗巨大——这在嵌入式场景下不可接受
3. **依赖太重**：MonetDB 没有做到真正的零配置，它的 C 库依赖、内存映射假设都让它难以跨平台

MonetDBLite 在 2018 年左右停止维护，但它播下了种子：证明了嵌入式的分析型 SQL 是一个真实的、未被满足的需求。

> **线索**：DuckDB 源码中 `src/include/duckdb/original/` 目录暗示着对 MonetDB 代码中某些组件的直接继承或改写。这既是对前辈的致敬，也是对架构路线的清醒切割。

### DuckDB：重新思考嵌入式 OLAP

2018 年，MonetDB 团队的 Mark Raasveldt 和 Hannes Mühleisen 在 CWI 启动了新项目，后来被命名为 DuckDB——一个名字奇怪的选择（"Duck"既是对水鸟的喜爱，也暗含"小但强韧"的寓意）。

DuckDB 的起点是一个清醒的认识：

> 嵌入式 OLAP 不是服务器 OLAP 的简化版，而是一个全新的物种。

这意味着必须从第一性原理出发重新设计一切：解析器、优化器、执行引擎、存储格式、内存管理、并发模型。不能剪裁 MonetDB，也不能简单地把 PostgreSQL 的解析器和一个内存引擎拼在一起。

DuckDB 采用了一套完整的、自顶向下的设计：

| 层面 | 选择 | 设计理由 |
|------|------|----------|
| 解析器 | 手写递归下降 | 零依赖、可嵌入、语法方言扩展（如 PIVOT、List 推导） |
| 语义分析 | 自研 Binder | FROM/JOIN 优先的绑定顺序，处理嵌套类型和隐式类型转换 |
| 逻辑优化 | 规则重写 + 统计驱动 | 与 Cascades/Volcano 优化器框架形成区别——足够好但不追求最优 |
| 物理执行 | Pipeline + 向量化 | 介于 Volcano 和 Whole-Stage CodeGen 之间的第三条路 |
| 存储格式 | 自定义列式 + Parquet 扩展 | 进程内直接 mmap 或 read，零拷贝与 Arrow 互操作 |
| 事务 | OLAP-optimized MVCC | 多读单写，无锁数据结构，版本链而非 2PL |

## 1.2 DuckDB 的核心设计目标

DuckDB 的设计哲学可以凝练为四个词：**Embedded、Portable、Fast、Feature-Rich**。

### Embedded：不是"可嵌入"，而是"生而为嵌入"

这是 DuckDB 与一切其他分析型数据库的根本分界线。PostgreSQL、ClickHouse、Snowflake、Redshift——它们都是"在别处"的数据库。你需要连接、认证、序列化、反序列化、传输。

DuckDB 不存在"客户端-服务器"的边界。它不是去掉了网络协议的服务器引擎——它根本没有服务器的概念。`DatabaseInstance` 对象不是一个服务进程的句柄，它就是数据库本身。

```cpp
// duckdb.hpp —— 整个 DuckDB 对外的入口就是这四个头文件
#include "duckdb/main/connection.hpp"
#include "duckdb/main/database.hpp"
#include "duckdb/main/query_result.hpp"
#include "duckdb/main/appender.hpp"
```

没有 `DatabaseServer` 类，没有 `Listener`，没有 `AcceptLoop`。打开文件即打开数据库。

### Portable：零外部依赖（真的零）

DuckDB 的编译依赖极度克制。C++17 标准库 + 少量内置的第三方代码（RE2 的正则引擎、HyperLogLog、zstd/lz4 压缩库等），全部放在 `third_party/` 目录中并编译进单一可执行文件。

这意味着你可以：
- 在树莓派上运行
- 编译为 WASM 在浏览器中运行（DuckDB-Wasm）
- 在 iOS/Android 应用中嵌入
- 在 Cloudflare Workers 等边缘计算平台运行

在 CMakeLists.txt 中，`find_package(Threads REQUIRED)` 几乎是唯一的外部依赖声明。这是一项令人难以置信的工程纪律。

### Fast：向量化执行的工程极致

"快"不是一个玄学目标。DuckDB 的快来自于三层叠加：

1. **列式存储**：只读需要的列，减少 I/O
2. **向量化执行**：每次处理 2048 行（`STANDARD_VECTOR_SIZE`），用紧凑循环替代函数调用开销
3. **Pipeline 并行**：打破 Volcano 模型的算子间函数调用链，将可线性执行的算子链串联为 Pipeline

与 Spark 的对比很有意思：Spark 的核心优势是横向扩展（scale-out），但单个 Task 的执行效率并不高——Java 的 GC 压力、行式 Shuffle、序列化开销都是结构性的效率损耗。DuckDB 的单机效率往往是 Spark 单节点的 10-100 倍，这意味着很多"大数据"问题其实根本不是大数据问题——它们只是被低效的执行引擎放大了。

### Feature-Rich：不是"SQL 的子集"

许多嵌入式数据库选择提供 SQL 的子集——"够用就好"。DuckDB 走了相反的路：它追求完整地实现 SQL 标准 + 扩展分析功能。

- 完整的 Window 函数（`ROW_NUMBER()`, `RANK()`, `LEAD/LAG`, 窗口聚合）
- PIVOT / UNPIVOT 语法糖
- 嵌套类型的完整查询支持（`list_filter()`, `struct.*` 展开）
- 友元语法（Friendly SQL）：如 `SELECT * EXCLUDE (col)`、`COLUMNS()` 正则匹配
- 完整的 CTE、子查询、相关子查询
- ASOF Join（`SELECT * FROM a ASOF JOIN b ON a.ts >= b.ts`）

这种"小而全"的选择是 DuckDB 的重要哲学，将在第 6-8 章深入展开。

## 1.3 与 Spark/Hive/MaxCompute 的范式差异

作为有大规模分布式计算背景的读者，理解 DuckDB 最容易的方式是对比：

### 核心范式的错位

```
Spark/Hive/MaxCompute 范式：
  数据 >> 单机内存 → 必须分布式
  计算移动到数据（bring compute to data）

DuckDB 范式：
  单机内存 >> 数据 → 不需要分布式
  数据移动到计算（bring data to compute）
```

过去十年，大数据生态基于一个核心假设：数据量总是超过单机处理能力。这个假设驱动了 Hadoop、Spark、Hive、Presto 的诞生。但一个悖论逐渐浮现：

- 在 AWS、阿里云上，一台 r6i.8xlarge（256GB RAM）月租约 $2000
- 大多数组织的"大数据"其实远远小于 256GB
- 真正需要分布式处理的场景（PB 级）中，成本瓶颈其实不是计算而是人的等待时间

DuckDB 不做分布式，不是"不能做"，而是它从另一个角度解构了问题：**如果你的单机处理能力提升 100 倍，还有多少场景需要分布式？**

### 一条 SQL 的执行路径对比

**Spark SQL**:
```
SQL → Parser(Antlr) → Analyzer(Catalog Lookup) → Optimizer(Catalyst) →
Physical Plan → RDD DAG → Task → Executor(JVM) → Shuffle → ...
```

**DuckDB**:
```
SQL → Parser(Recursive Descent) → Transformer → Binder → Logical Plan →
Optimizer(Rule-based + Statistics) → Physical Plan → Pipeline → Executor(Native) → Result
```

路径长度大致相当，但关键差异在于：
1. **DuckDB 没有网络层**：每一步都是函数调用的单机边界内的操作
2. **没有序列化**：Plan 到 Executor 间传递的都是内存指针，不是 protobuf/thrift 消息
3. **没有 Shuffle 的物理开销**：Pipeline 的并行通过 Partition 划分在内存中完成，不经过磁盘和网络

### 计算与存储的关系

Spark 处理数据的方式：
```
HDFS/S3 → Spark Executor 读 → 内存处理 → 写回 HDFS/S3
```

DuckDB 处理数据的方式：
```
本地文件/S3 Parquet → DuckDB mmap/HTTP Range Read → 内存处理 → 本地文件/S3 Parquet
```

DuckDB 的 S3 支持（通过 httpfs extension）是纯 HTTP Range Request 的方式实现：它按需拉取文件中的 Block 范围(Parquet 文件的 Row Group)，而不是先下载再处理。这契合了云对象存储的访问模式。

> **本质追问**：分布式系统的基石是"数据不动计算动"，但当一个进程在 3ms 内可以访问本机 256GB 内存中的任何字节，而跨网络访问最快也要 50μs（RDMA）到 500μs（TCP），这个基石是否应该被重新审视？

## 1.4 源码仓库全貌

打开 DuckDB 的源码根目录，首先映入眼帘的不是一个庞大的 Monorepo，而是一个高度自洽的模块结构。

### 目录结构速览

```
duckdb/
├── src/                    # 核心引擎源码（本书主要讨论对象）
│   ├── include/duckdb/     # 公共头文件——模块间的契约
│   ├── parser/             # SQL 解析器
│   ├── planner/            # 语义分析与逻辑计划
│   ├── optimizer/          # 查询优化器
│   ├── execution/          # 物理执行引擎
│   ├── storage/            # 存储引擎（列式格式、压缩、WAL）
│   ├── transaction/        # 事务管理
│   ├── common/             # 基础类型、容器、算法
│   ├── function/           # 内置函数（标量、聚合、窗口、表函数）
│   ├── catalog/            # 元数据管理
│   ├── main/               # 客户端 API、数据库生命周期
│   ├── parallel/           # 并行执行框架
│   └── verification/       # 验证框架（用于测试）
├── extension/              # 内置扩展（Parquet、JSON、ICU、TPCH 等）
├── third_party/            # 第三方依赖（零外部依赖的秘密）
├── test/                   # 回归测试
├── benchmark/              # 性能测试（micro/macro/ClickBench/TPC-H）
├── tools/                  # 辅助工具（如 SQLite3 shell wrapper）
├── examples/               # 使用示例
└── scripts/                # CI/构建/Python 格式检查脚本
```

### 模块职责速查

| 模块 | 一句话职责 | 关键文件 |
|------|-----------|----------|
| **common** | 类型系统、Vector、DataChunk、文件系统抽象 | `types.hpp`, `vector.hpp`, `types/vector.hpp` |
| **parser** | SQL 文本 → AST | `transformer.hpp`, `parser.cpp` |
| **planner** | AST → Logical Plan（含语义分析） | `binder.hpp`, `logical_operator.hpp` |
| **optimizer** | Logical Plan → Optimized Logical Plan | `optimizer.cpp` (33KB+ 的规则编排器) |
| **execution** | Physical Plan → Pipeline → 执行 | `physical_operator.hpp`, `pipeline.hpp` |
| **storage** | 列式数据持久化、压缩、WAL | `data_table.hpp`, `buffer_manager.hpp` |
| **transaction** | MVCC 管理 | `transaction_manager.cpp` |
| **function** | 内置函数注册与分派 | `scalar_function.hpp`, `aggregate_function.hpp` |
| **catalog** | Schema、Table、Function 的元数据管理 | `catalog.hpp`, `catalog_entry/` |
| **parallel** | 任务调度、Pipeline 执行器 | `task_scheduler.hpp`, `pipeline_executor.hpp` |
| **main** | 对外 API（Database、Connection、Appender） | `database.hpp`, `client_context.hpp` |

### 代码规模

DuckDB 源码（不含 extension 和 third_party）的规模并不"微型"：

- `.cpp` 文件约数百个（`src/` 目录下各模块）
- `.hpp` 文件匹配数量相当
- 其中 single file 最巨的是 `optimizer.cpp`——整个优化器的编排逻辑集中在一个文件，体现了工程偏好
- 执行引擎中最大的一块是 `execution/operator/`——每种物理算子的实现分布在此

这不是一个"玩具"级别的项目，而是一个工业强度的数据库。但它通过清晰的模块边界和头文件契约，维持了相当的可读性——这对本书的源码解析方法至关重要。

## 1.5 开发者工作流

### 构建系统

DuckDB 使用 CMake + Ninja 作为构建工具链。构建命令由 `Makefile` 统一封装：

```bash
# Gen --help 输出（部分）
make debug     # 带断言的调试构建
make release   # 优化构建（默认）
make unittest  # 运行所有单元测试
make benchmark # 运行所有 benchmark
```

关键配置项：
- `BUILD_EXTENSIONS`：控制内置扩展的编译
- `ENABLE_SANITIZER`：启用 Address/Thread/UB Sanitizer
- `FORCE_32_BIT=1`：强制 32 位模式（用于测试小系统兼容性）

### 调试方法

```bash
# 在 LLDB 中调试 DuckDB
make debug
lldb build/debug/duckdb
(lldb) b DatabaseInstance::DatabaseInstance
(lldb) run
```

由于 DuckDB 是单进程架构，调试就是调试一个普通的 C++ 程序——没有服务器进程的附加、没有远程调试的连接配置。这对内核研究是一大福音。

### 测试框架

DuckDB 的测试分为三层：

1. **SQL 回归测试** (`test/sql/`)：以 `.test` 文件格式书写，测试框架解析 SQL 输入和预期输出，逐行比较。这是 DuckDB 最核心的测试方式。

   ```sql
   # test/sql/aggregate/test_count.test 示例格式
   statement ok
   CREATE TABLE t (a INTEGER)

   statement ok
   INSERT INTO t VALUES (1), (2), (3)

   query I
   SELECT COUNT(*) FROM t
   ----
   3
   ```

2. **单元测试** (`test/unittest.cpp`)：C++ Catch2 框架的单元测试，测试内部 API。

3. **Benchmark** (`benchmark/`)：性能回归测试，覆盖 micro（微型算子）、macro（标准负载）、ClickBench、TPC-H、TPC-DS 等。

### Benchmark 体系

```bash
# 运行单个 benchmark
build/release/benchmark/benchmark_runner micro/aggregate/sum.benchmark

# 运行所有 micro benchmark
build/release/benchmark/benchmark_runner 'micro/*'
```

Benchmark 文件格式（以 `micro/aggregate/sum.benchmark` 为例）：
```
# name: benchmark/micro/aggregate/sum.benchmark
# group: [aggregate]
# 定义测试 SQL、数据生成规则、性能度量方法
```

这套体系让 DuckDB 团队可以在每次提交后自动检测性能退化，维护"快"的承诺。

---

## 本章小结

本章以"为什么"而非"是什么"出发，审视了 DuckDB 存在的理由：

1. **历史必然性**：SQLite 代表嵌入式的 OLTP，MonetDBLite 是失败但种子性的尝试，DuckDB 填补了嵌入式 OLAP 的真空
2. **核心设计目标**：Embedded、Portable、Fast、Feature-Rich——四个词定义了一个新物种
3. **范式差异**：DuckDB 与分布式大数据引擎（Spark/MaxCompute）在前提假设上是对立的——它在单机维度上极致优化，重新定义了"大数据"的边界
4. **源码全貌**：模块边界清晰、代码组织合理，是理解一个工业级数据库内核实现的绝佳样本
5. **开发者工作流**：单进程架构让调试极其便利，分层测试体系保证了代码质量

下一章，我们将画出一笔，从整体架构上理解 DuckDB 如何将一条 SQL 转化为最终结果——这是贯穿全书 36 章的骨架。
