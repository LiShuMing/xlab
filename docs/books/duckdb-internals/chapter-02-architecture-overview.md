# 第2章：系统架构全景

> 在进入逐模块的源码细节之前，先在脑中建立一张完整的地图。本章的目标是让你能闭眼画出 DuckDB 从 SQL 文本到最终结果的全链路数据流图。

## 2.1 从一条 SQL 看全链路

我们从一条最简单的查询开始，追踪 DuckDB 如何处理它：

```sql
SELECT COUNT(*) FROM orders WHERE amount > 100;
```

这条 SQL 在 DuckDB 内部经历六次表示（Representation）变换：

```
SQL Text
  ├─[Parser]──► AST (SQLStatement Tree)
  ├─[Binder]──► BoundStatement (Typed & Resolved AST)
  ├─[Planner]──► LogicalOperator Tree
  ├─[Optimizer]──► Optimized LogicalOperator Tree
  ├─[Physical Plan Generator]──► PhysicalOperator Tree → Pipeline DAG
  └─[Executor]──► Result (MaterializedQueryResult)
```

### 阶段1：Parser — 文本到语法树

```
输入： "SELECT COUNT(*) FROM orders WHERE amount > 100"
输出： SelectStatement
        └── SelectNode
              ├── select_list: [FunctionExpression("count", StarExpression)]
              ├── from_table:  BaseTableRef("orders")
              └── where_clause: ComparisonExpression(GREATER_THAN,
                                      ColumnRef("amount"), Constant(100))
```

Parser 是做纯语法工作——检查 SQL 是否合法、构建语法树。它不关心 `orders` 表存不存在，也不管 `amount` 列的类型。DuckDB 使用手写递归下降解析器（`src/parser/`）而非 Yacc/Bison，这是为了零依赖和更好的错误消息。

### 阶段2：Binder — 语义分析与名字解析

```
输入： SelectStatement AST
输出： BoundSelectStatement
        ├── tables:   [TableCatalogEntry("orders", columns={order_id:INT, amount:DECIMAL, ...})]
        ├── aggregates: [BoundAggregateExpression("count_star")]
        └── where:    BoundComparisonExpression(GREATER_THAN,
                        ColumnBinding(table_idx=0, column_idx=2: "amount"),
                        Value(100:DECIMAL))
```

Binder 走进 Catalog 查找 `orders` 表，验证 `amount` 列的存在，把 `COUNT(*)` 解析为内置聚合函数。每一个 `ColumnRef` 变成附带表索引和列索引的 `ColumnBinding`。如果引用了不存在的表或列，错误在这里抛出——不是在执行阶段。

### 阶段3：Planner — 生成逻辑计划

```
输入： BoundSelectStatement
输出： LogicalOperator Tree
        LogicalAggregateAndGroupBy
          └── LogicalFilter (amount > 100)
                └── LogicalGet (orders)
```

Planner 从绑定后的语义树递归生成逻辑算子树。`LogicalGet` 代表从表读取，`LogicalFilter` 代表过滤，`LogicalAggregateAndGroupBy` 代表聚合。DuckDB 定义了 50+ 种逻辑算子类型（`LogicalOperatorType` 枚举）。这棵树就是关系代数的程序化表达。

### 阶段4：Optimizer — 重写与优化

```
输入： LogicalAggregateAndGroupBy
        └── LogicalFilter(amount > 100)
              └── LogicalGet(orders, columns=[order_id, amount, ...])

输出： LogicalAggregateAndGroupBy
        └── LogicalGet(orders, columns=[amount])
              └── filter pushdown: amount > 100 → Zone Map pruning
```

优化器做两件事：
1. **列裁剪**：`COUNT(*)` 不需要任何具体列——过滤条件只用 `amount`，于是 `order_id` 等其他列被移除（`RemoveUnusedColumns` 规则）
2. **谓词下推**：将 `amount > 100` 推到 Scan 算子，使得存储层可以利用 Zone Map（min/max 统计）跳过整个 RowGroup

### 阶段5：Physical Plan Generator — 逻辑到物理

```
输入： Optimized LogicalOperator Tree
输出： PhysicalOperator Tree
        PhysicalHashAggregate  ← Sink (Pipeline Breaker)
          └── PhysicalTableScan (orders, filter=amount > 100)
```

生成器将逻辑算子一对一或多对一地映射为物理算子。同时识别 Pipeline 边界——`PhysicalHashAggregate` 是一个 Sink 算子：它必须消费完所有输入数据，才能输出结果。这构成了 Pipeline 的断点。

### 阶段6：Executor — 执行

```
输入： PhysicalOperator Tree
执行过程：
  1. 构建 Pipeline DAG：Pipeline 1: PhysicalTableScan → PhysicalHashAggregate(Sink)
  2. 多线程执行 Pipeline 1：
     - 线程从 RowGroup 读 [amount] 列数据，构造 DataChunk（最多 2048 行）
     - 应用过滤：amount > 100
     - 传给 Sink：HashAggregate 累积计数
  3. 收集结果：MaterializedQueryResult → 返回给用户
```

Executor 把物理计划转化为 Pipeline，以 `DataChunk` 为单位在算子间传递数据。在 Pipeline 内，算子以 push-based 模式工作——上游算子产出 Chunk，推给下游。这是不同于 Volcano（pull-based）的关键设计。

## 2.2 核心抽象层

DuckDB 的顶层有四层概念构成了用户的"心智模型"：

### DuckDB → DatabaseInstance

```cpp
// src/include/duckdb/main/database.hpp:106-153
class DuckDB {
public:
    shared_ptr<DatabaseInstance> instance;  // 唯一的公开成员
    // ...
};
```

`DuckDB` 是用户持有的第一个对象。它可以被创建在栈上、堆上，或作为全局单例。它是薄壳——真正的工作在 `DatabaseInstance` 中。

```cpp
// src/include/duckdb/main/database.hpp:39-102
class DatabaseInstance : public enable_shared_from_this<DatabaseInstance> {
    DBConfig config;                                    // 配置对象（内存/线程/扩展）
    shared_ptr<BufferManager> buffer_manager;           // Buffer Pool + Block 管理
    unique_ptr<DatabaseManager> db_manager;             // 多数据库附加管理
    unique_ptr<TaskScheduler> scheduler;                // 全局线程池
    unique_ptr<ConnectionManager> connection_manager;   // 连接注册/管理
    unique_ptr<ExtensionManager> extension_manager;     // 扩展生命周期
    unique_ptr<ObjectCache> object_cache;               // 数据库对象缓存
    unique_ptr<ExternalFileCache> external_file_cache;  // 外部文件句柄缓存
    unique_ptr<ResultSetManager> result_set_manager;    // 结果集管理
    unique_ptr<LogManager> log_manager;                 // 日志系统
};
```

`DatabaseInstance` 是 DuckDB 运行时的"内核"——它持有所有子系统。一个 `DatabaseInstance` 对应一个数据库文件（或内存数据库），可以有多个 `ClientContext` 共享它。

### Connection → ClientContext

```cpp
// src/include/duckdb/main/client_context.hpp:70-97
class ClientContext : public enable_shared_from_this<ClientContext> {
    shared_ptr<DatabaseInstance> db;         // 所属的数据库实例
    atomic<ClientInterruptState> interrupt_state;  // 查询中断状态
    optional_idx query_deadline;             // 查询超时
    ClientConfig config;                     // 客户端配置
    unique_ptr<ClientData> client_data;      // 客户端数据（如 catalog cache）
    TransactionContext transaction;          // 事务上下文
};
```

`ClientContext` 不只是"连接"的概念——它是查询执行的**协调者**。所有 SQL 的执行从 `ClientContext::Query()` 进入：

```cpp
// 简化后的调用链
ClientContext::Query(sql)
  → ClientContext::CreatePreparedStatement(sql)
    → Parser::ParseStatement(sql)            // Stage 1
    → Planner::CreatePlan(statement)         // Stage 2 + 3
    → Optimizer::Optimize(plan)              // Stage 4
  → ClientContext::PendingStatement(prepared)
    → PhysicalPlanGenerator::CreatePlan(...) // Stage 5
    → Executor::Execute(...)                 // Stage 6
```

注意从 `ClientContext::Query` 开始的函数们都在同一个线程中执行——从解析到物理计划生成都是**同步函数调用**。这是嵌入式引擎的核心特征：没有网络边界、没有序列化、没有异步回调。只有到了 `Executor::Execute()` 阶段，才涉及多线程调度。

### 与传统数据库的概念对照

| DuckDB 概念 | 等价类比 | 本质差异 |
|------------|----------|----------|
| `DuckDB` | 数据库文件句柄 | 不是进程，是 C++ 对象 |
| `DatabaseInstance` | postmaster + 共享内存 | 不带监听 socket，没有 fork |
| `ClientContext` | 客户端 session 后端 | 同一个进程中的另一个对象，无序列化 |
| `Connection` | libpq 连接句柄 | 没有网络认证，只是一个智能指针包装 |

## 2.3 模块依赖图

DuckDB 的源码模块之间存在严格的层次关系：

```
                          main
                 (Connection, Database, ClientContext)
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
      parser             planner            function
    (SQL → AST)    (Binder + Logical Plan)  (Scalar/Aggregate/Table UDF)
         │                  │                  │
         ▼                  ▼                  │
      planner           optimizer              │
         │          (Rule-Based Rewrites)       │
         │                  │                  │
         └──────────┬───────┘                  │
                    ▼                          │
                execution ◄────────────────────┘
         (Physical Operators, Pipeline)        │
                    │                          │
                    ▼                          │
     ┌──────────┬───┴────┬──────────┐          │
     ▼          ▼        ▼          ▼          │
  storage  transaction  parallel   catalog
(Columnar   (MVCC,     (TaskSched, (Metadata
 Storage,    Undo,     Pipeline    Management)
 Compression WAL)      Executor)
     │          │        │          │          │
     └──────────┴────────┴──────────┴──────────┘
                         │
                         ▼
                      common
         (Types, Vector, DataChunk, FileSystem,
          Allocator, Serializer, Containers)
```

### 层级设计原则

**common 是唯一的无依赖层**。`types.hpp`, `vector.hpp`, `allocator.hpp` 等文件不依赖任何其他模块。所有上层模块依赖 common，但 common 不依赖任何上层。这种自底向上的依赖方向是大型 C++ 项目维持可维护性的关键。

**storage 和 transaction 是平行协作**。storage 管物理格式，transaction 管可见性。两者通过 MVCC 机制配合，但不存在编译依赖——各自通过 common 层的数据结构表达状态。

**execution 是集成点**。它同时依赖 parallel（调度）、function（函数仓库）、storage（数据访问），是系统中最"重"的模块。

**main 是协调者而非主导者**。`main/database.cpp` 和 `main/client_context.cpp` 编排子系统的方法调用，但不深入子系统内部的数据结构。

## 2.4 DuckDB 独有的设计取舍

数据库系统的任何架构选择都是一组权衡。DuckDB 的选择尤其值得审视，因为它们与你在 Spark/MaxCompute 中熟悉的模式截然不同。

### 线程模型：固定线程池

DuckDB 不做动态线程扩缩。`TaskScheduler` 在 `DatabaseInstance` 初始化时创建固定大小的线程池（默认 = CPU 核数），一直运行到 `DatabaseInstance` 析构。

```cpp
// src/include/duckdb/main/database.hpp:91
unique_ptr<TaskScheduler> scheduler;
// 只在 DatabaseInstance::Initialize 中创建一次
// 不会根据负载增减线程数
```

这个选择的前提假设是：DuckDB 独占这些核心。如果有其他进程需要 CPU，那是操作系统的调度问题，不是数据库的。相比之下，Spark Executor 的线程模型要复杂得多——Task 线程、Shuffle 线程、Heartbeat 线程，各管各的生命周期。

### 内存管理：按需分配而非预占

DuckDB 不预分配大片内存区域作为 Heap。它在两处使用不同的策略：

1. **通用分配**：直接用 C++ `new`/`malloc`，由标准分配器管理
2. **查询中间结果**：使用 `ArenaAllocator`——批量申请 Block（256KB），多次分配，一次性释放
3. **磁盘缓存**：`BufferManager` 管理 Buffer Pool，带 LRU 驱逐

这与 Spark 的 UnifiedMemoryManager（Execution Memory + Storage Memory 的争用管理）形成对比。DuckDB 的内存管理极简——对于嵌入式场景，"简单即正义"。

### 对于"不做什么"的清醒

DuckDB 明确不做以下事情（至少目前）：

- **不横向扩展**：单机是它的全部。MotherDuck（第 36 章）在云端补充了这方面的能力，但核心引擎不是分布式的
- **不做多用户并发写入**：MVCC 设计假设"一个写入者 + 多个读取者"（详见第 27 章）
- **不做查询级别的优先级调度**：多个 Connection 的查询由 TaskScheduler 统一调度，没有 QoS
- **不预编译或 JIT**：表达式计算使用解释执行的向量化方式，而非生成机器码

每一条"不做"背后都是一个自觉的架构决策。理解 DuckDB 的本质，很大程度就是理解它**主动放弃**了什么。

### Pipeline 执行模型：第三条路

DuckDB 的执行模型夹在两种经典方案之间：

| 方案 | 代表 | 核心思想 | 优势 | 劣势 |
|------|------|----------|------|------|
| Volcano (Iterator) | PostgreSQL | 每算子实现 `Next()`，逐行拉取 | 极简、易组合 | 虚函数调用每行一次，CPU 缓存差 |
| Whole-Stage CodeGen | Spark Tungsten, Hyper | 将算子链编译为单段机器码 | 零虚函数、高度优化 | 编译耗时、难调试 |
| **向量化 Pipeline** | **DuckDB** | 批量处理（2048 行/push），Pipeline 压缩算子链 | 靠近 CodeGen 效率，保留解释执行灵活性 | 仍有批次间函数调用开销 |

Pipeline 内的算子以 push-based 模式工作：`PhysicalTableScan` 读取一批数据 → 调用 `PhysicalFilter::Execute` → 调用下一个算子 → 直到 Sink（阻塞算子）。Pipeline 边界由 Sink 算子自然形成——这是 DuckDB 执行引擎最优雅的设计之一，将在第 13-14 章详细展开。

### 代码风格观察

翻 DuckDB 源码时注意这几个标志性模式：

1. **智能指针透明使用**：子节点用 `unique_ptr`，共享引用用 `shared_ptr`。在 C++ 数据库引擎中少见（多数用 Arena 池+裸指针），但 DuckDB 选择清晰的 RAII 语义
2. **`DUCKDB_API` 宏**：标记公共 API 的符号导出。几乎所有 `src/include/duckdb/` 中的公开类都带这个标记
3. **`idx_t` 类型**：DuckDB 自定义的索引类型（`uint64_t`），全库统一使用——你不会看到 `size_t`, `uint64_t`, `int64_t` 混用的现象
4. **友元泛滥但克制**：`Vector` 类有 16 个 friend 声明——这通常被视为 C++ 的设计异味，但在 DuckDB 中，这些友元（`FlatVector`, `ConstantVector`, `DataChunk` 等）恰恰是 Vector 的不同"视图"，它们共享内部结构是设计意图

---

## 本章小结

本章建立的全局架构心智模型：

1. **一条 SQL 的六阶段旅程**：Parse → Bind → Plan → Optimize → Physical → Execute
2. **四层核心抽象**：`DuckDB` → `DatabaseInstance` → `ClientContext` → `Connection`，所有层都是同一进程的 C++ 对象
3. **模块依赖的金字塔**：common 是底座，storage/transaction/execution 是引擎层，main 是协调层
4. **设计取舍清单**：固定线程池、按需内存、单写者 MVCC、Pipeline 向量化、不横向扩展、不 JIT

这张地图的价值在于：后续 34 章中讨论的任何模块，你都能立即定位它在全局中的位置——"这是 Parser 的输出，传给 Binder"；"这个优化规则修改的是 LogicalOperator 树"；"这个 Pipeline Breaker 是 HashAggregate Sink"。

下一章，我们从最底层的 common 模块开始——类型系统与数据表示，这是列式计算一切被构建的基石。
