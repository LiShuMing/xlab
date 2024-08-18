# 第 18 章 · Table API & SQL 的架构全景

## 导读

- **一句话**：本章展示 Flink SQL 的编译流水线全貌——从一条 `SELECT` 到在 TaskManager 上运行的 JobGraph。
- **前置知识**：第 5 章 JobGraph/ExecutionGraph、基本的 SQL 引擎概念。
- **读完本章你能回答**：
  - Flink SQL 的编译流水线分哪几步
  - `flink-table-api-java`、`flink-table-common`、`flink-table-planner`、`flink-table-runtime` 的分工
  - Catalog 体系解决了什么问题
  - `DynamicTableSource` / `DynamicTableSink` 跟 DataStream API 的 Source/Sink 怎么桥接

---

## 18.1 — 设计动机：SQL 是声明式，需要翻译成命令式 DAG

```
用户: INSERT INTO sink_table SELECT a, SUM(b) FROM source_table GROUP BY a;

Flink 的转换链:
  SQL 字符串
  → SqlNode (Calcite AST)
  → RelNode (Logical Plan) 
  → Optimized Logical Plan
  → Physical Plan (FlinkPhysicalRel)
  → ExecNode Graph (ExecNode[])     ← 可序列化为 JSON 的执行计划
  → Transformation Graph (Transformation[])  ← 与 DataStream API 通用
  → StreamGraph → JobGraph → ExecutionGraph
```

### ExecNode：物理执行计划节点

`ExecNode` 是 Flink Table/SQL 物理执行计划的核心抽象（`flink-table-planner/.../plan/nodes/exec/ExecNode.java:54`）：

```java
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, include = JsonTypeInfo.As.EXISTING_PROPERTY, property = "type")
public interface ExecNode<T> extends ExecNodeTranslator<T>, FusionCodegenExecNode {
    int getId();                         // 唯一 ID
    String getTypeAsString();            // 类型字符串（如 "stream-exec-table-source-scan_2"）
    int getVersion();                    // 版本号（用于 CompiledPlan 兼容性）
    String getDescription();             // 描述
    LogicalType getOutputType();         // 输出类型
    List<InputProperty> getInputProperties(); // 输入属性（含 RequiredDistribution）
    List<ExecEdge> getEdges();           // 边列表
}
```

**关键设计**：`ExecNode` 带有 `@JsonTypeInfo` 注解——可以序列化为 JSON 格式的 CompiledPlan。这意味着 Flink SQL 的物理计划可以保存、加载、跨版本使用——这是 Flink 1.15+ 引入的 Plan Stability 特性的基础。

`InputProperty` 包含 `RequiredDistribution`——它决定上游数据的分区需求（如 HASH、SINGLE、ANY），这直接映射到 DataStream API 的 `Partitioner`。

物理层往下就跟 DataStream API 统一了——这正是"同一运行时"的体现。

---

## 18.2 — 四大模块的分工

| 模块 | 角色 | 关键内容 |
|------|------|---------|
| **flink-table-api-java** | 面向用户的编程接口 | `TableEnvironment`, `Table`, SQL 执行 |
| **flink-table-common** | 共享的Table类型、表达式、Connector SPI | `RowData`, `Schema`, `ConnectorDescriptor` |
| **flink-table-planner** | Calcite 集成和优化器 | `FlinkPlannerImpl`, `SqlToOperationConverter` |
| **flink-table-runtime** | 运行时算子实现 | `BinaryRowData`, `HashAggregate`, `SortMergeJoin` |

---

## 18.3 — SQL 编译流水线（关键步骤）

```
1. Parser (Calcite SQL Parser)
   → SqlNode tree

2. Validation (Calcite Validator) 
   → 类型校验、解析 schema/catalog

3. SqlToOperationConverter
   → 把 INSERT/SELECT 转换成 Planner Operation
   → 创建 QueryOperation + ModifyOperation

4. Planner: translate(operations)
   → RelNode tree (Logical Plan)

5. Optimizer: optimize(RelNode)
   → 应用 150+ 优化规则 (Volcano + HepPlanner)
   → 生成 Optimized Physical Plan

6. translateToExecNodeGraph()
   → ExecNode DAG (ExecNode[])

7. translateToPlan(Transformation[])
   → 与 DataStream API 统一的 Transformation Graph

8. StreamGraph → JobGraph → ExecutionGraph (同第5章)
```

源码入口：
- `flink-table/flink-table-planner/.../delegation/PlannerBase.java`
- `flink-table/flink-table-planner/.../operations/SqlToOperationConverter.java`

---

## 18.4 — Catalog 体系

Flink Catalog 类似 MySQL 的 `information_schema`——管理元数据（Database / Table / View / Function）。

```java
public interface Catalog {
    void open();
    void close();
    boolean databaseExists(String dbName);
    boolean tableExists(ObjectPath tablePath);
    CatalogBaseTable getTable(ObjectPath tablePath);
    // ...
}
```

Catalog 层解决了 Flink SQL 中最关键的问题：**"表在哪、长什么样"**。它可以对接：
- `GenericInMemoryCatalog`（纯内存）
- `HiveCatalog`（Hive Metastore 对接）
- `JdbcCatalog`（从 JDBC 源读 schema）
- `UserDefinedCatalog`（自定义元数据源）

源码入口：`flink-table/flink-table-common/.../catalog/Catalog.java`

---

## 18.5 — DynamicTableSource / Sink：统一的表连接器抽象

```
CatalogTable (元数据层) 
  → DynamicTableSourceFactory (工厂)
  → DynamicTableSource → ScanTableSource / LookupTableSource
        ↓ (在优化器中)
        被翻译成 Transformation

运行时：
  ScanTableSource → SourceOperator (DataStream Source)
  LookupTableSource → LookupJoinOperator (维表关联)
  DynamicTableSink → SinkOperator (DataStream Sink)
```

这是 FLIP-95 之后的新 Source API 与 SQL 层的桥接——用统一的 SPI 让 Table 环境下的"FROM Kafka"和 DataStream 环境下的 `env.fromSource()` 最终共享同一个 Source 实现。

源码入口：`flink-table/flink-table-common/.../connector/source/DynamicTableSource.java`

---

## 18.6 — 横向对比

### vs Spark SQL (Catalyst Optimizer)

Catalyst 类似 Calcite 的角色。但 Flink 多了一个 `ExecNode → Transformation → StreamGraph` 的中间层——因为需要同时支持流和批。Spark SQL 直接产出 RDD。

### vs StarRocks

StarRocks 的 FE（Frontend）跟 Flink SQL Planner 类似——都是优化器+协调器。区别是 StarRocks 直接在计划层指定每 Fragment 在物理节点的分发。Flink 将分发交给下层的调度器（ExecutionGraph）。

---

## 本章要点回顾

1. SQL 编译 = Parse → Validate → Optimize → ExecNode → Transformation → StreamGraph → JobGraph——与现实 DataStream API 统一。
2. 四模块各司其职：api-java（用户）、common（IR+SPI）、planner（优化）、runtime（算子）。
3. Catalog = 元数据管理器，对接 Hive/JDBC；DynamicTable = 通用表连接器 SPI。

## 源码导航

- SQL 入口：`flink-table-api-java/.../api/TableEnvironmentImpl.java`
- Planner 核心：`flink-table-planner/.../delegation/PlannerBase.java`
- SqlToOperation：`flink-table-planner/.../operations/SqlToOperationConverter.java`
- ExecNode Graph：`flink-table-planner/.../plan/nodes/exec/`
- Catalog SPI：`flink-table-common/.../catalog/Catalog.java`
