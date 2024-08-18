# 第1章：Calcite 的第一性原理

## 1.1 查询处理的本质问题

在所有数据库和查询引擎的核心，存在一个永恒的问题：**如何将用户声明式描述的意图，转化为高效执行的物理计划？**

这个鸿沟可以用一个简单的例子说明。当用户写下：

```sql
SELECT o.order_id, c.name
FROM orders o JOIN customers c ON o.cust_id = c.id
WHERE o.amount > 1000
```

这只是"想要什么"的声明。但引擎需要回答"怎么做"：

- orders 表有 10 亿行，customers 有 100 万行——用 Hash Join 还是 Sort-Merge Join？
- `o.amount > 1000` 能否下推到存储层，减少数据传输？
- 如果 orders 按 cust_id 分区，能否利用分区裁剪？
- 如果 customers 表在远程 MySQL，orders 在本地 Parquet，如何做联邦查询？

这些问题不是 SQL 语义的一部分，而是**查询优化**的核心。查询处理引擎的本质工作，就是在声明式语义和物理执行之间架起一座桥梁：

```
SQL Text → [Parse] → AST → [Validate] → Validated AST → [Convert] → Logical Plan → [Optimize] → Physical Plan → [Execute] → Results
```

这条管线中的每一步都是一个独立的、可替换的阶段。这正是 Calcite 的设计出发点。

## 1.2 Calcite 的核心定位：不是引擎，是查询处理框架

Apache Calcite 的官方定位是"数据管理和分析框架"。但更精确的说法是：**Calcite 是一个查询处理框架，它提供从 SQL 文本到优化后物理计划的完整管线，但不负责数据存储和执行。**

这个定位决定了 Calcite 的三个核心特征：

### 1.2.1 没有自己的存储层

Calcite 不存储数据。它通过 Schema/Adapter 机制连接外部数据源。这意味着：

- Calcite 不关心数据是存在 MySQL、HDFS、Kafka 还是一个 CSV 文件里
- 它通过 `ScannableTable`、`FilterableTable`、`TranslatableTable` 三种能力梯度来适配不同智能程度的数据源
- 每种数据源可以选择性地"接管"部分计算（谓词下推、投影下推），也可以全部委托 Calcite 执行

### 1.2.2 没有自己的执行引擎

Calcite 提供了两种执行模式，但都不是为高性能设计的：

- **Enumerable 代码生成**：通过 linq4j 表达式树生成 Java 代码，经 Janino 即时编译后执行。这是默认模式，但性能有限。
- **解释执行**：通过 `Interpreter` 直接遍历关系算子树执行，主要用于调试和原型。

真正的大规模执行（Spark、Flink、MaxCompute）由集成 Calcite 的引擎自己实现。Calcite 负责生成优化后的逻辑/物理计划，引擎负责将计划翻译为自己的执行算子。

### 1.2.3 可插拔的优化器

Calcite 提供了两种内置优化器：

- **VolcanoPlanner**：基于 Volcano/Cascades 模型的代价优化器，支持自顶向下搜索
- **HepPlanner**：启发式顺序优化器，按指定顺序应用规则

但优化器本身也是可替换的——StarRocks 用自己的 CBO，Spark 用自己的基于规则的优化器，但它们都在 SQL 解析和验证阶段复用了 Calcite。

### 谁在使用 Calcite？

| 项目 | 使用方式 |
|------|---------|
| Apache Hive | SQL 解析 + 验证 + 优化 |
| Apache Spark | SQL 解析 + 验证（部分优化） |
| Apache Flink | SQL 解析 + 验证 + 优化 |
| Apache Druid | SQL 解析 + 验证 + 优化 + 执行 |
| Apache Kylin | SQL 解析 + 验证 + 优化 |
| MaxCompute (ODPS) | SQL 解析 + 验证 + 部分优化 |
| StarRocks | SQL 解析 + 验证 |

注意这个梯度：从只用解析验证，到完整的查询处理。Calcite 的模块化设计让每个项目可以按需取用。

## 1.3 Volcano/Cascades 优化模型的前世今生

要理解 Calcite 优化器的设计，必须回到它的理论根源。

### 1.3.1 关系代数的等价性

关系代数有一组经典的等价变换规则：

```
Filter(Filter(R, p1), p2) ≡ Filter(R, p1 AND p2)
Project([a,b], Filter(R, p)) ≡ Filter(Project([a,b], R), p)   -- 当 p 只引用 a,b 时
Join(Filter(R, p), S) ≡ Filter(Join(R, S), p)                  -- 当 p 只引用 R 的列时
```

这些等价性意味着：**同一个查询逻辑可以有多种代数表示，它们语义等价但执行代价不同。**

### 1.3.2 Volcano 优化器的核心思想

1993年，Goetz Graefe 发表了 Volcano 优化器框架，核心思想有三个：

1. **等价类（Equivalence Class）**：逻辑等价的表达式归入同一等价类。在 Calcite 中，这就是 `RelSet`。
2. **记忆化（Memoization）**：已探索过的子计划不需要重复探索。在 Calcite 中，`RelSubset` 按 Trait 划分等价类的子集。
3. **自顶向下搜索**：从目标属性出发，向下搜索满足条件的物理计划。

### 1.3.3 Cascades 的演进

Graefe 在 1995 年提出 Cascades，对 Volcano 做了关键改进：

- **规则分为 Transform 和 Implement 两类**：对应 Calcite 的 `TransformationRule` 和 `ConverterRule`
- **全局唯一标识（Group）**：对应 Calcite 的 `RelSet`
- **指导式搜索**：通过 promise/cost 进行剪枝

### 1.3.4 Calcite 的实现选择

Calcite 的 VolcanoPlanner 是 Volcano/Cascades 的 Java 实现，但做了一些实用化的取舍：

- **两种搜索驱动**：`IterativeRuleDriver`（传统迭代式）和 `TopDownRuleDriver`（自顶向下，更接近 Cascades）
- **规则驱动的惰性探索**：不像 Cascades 那样从根节点主动发起搜索，而是注册规则后等待匹配触发
- **简化的代价模型**：`VolcanoCost` 只有 rows/CPU/IO 三个维度，没有 Cascades 的 promise 机制

源码位置：`core/src/main/java/org/apache/calcite/plan/volcano/`（17 文件）

## 1.4 从 Spark/StarRocks/MaxCompute 视角看 Calcite 的价值边界

作为一个有 Spark、StarRocks、MaxCompute 经验的工程师，理解 Calcite 的价值边界至关重要。

### 1.4.1 Calcite 做什么最好

1. **SQL 标准解析**：Calcite 的 Parser 支持 SQL:2003 标准的大部分语法，40+ 种方言。自己写一个完整的 SQL Parser 是巨大的工程。
2. **语义验证**：名称解析、类型检查、子查询合法性验证——这些逻辑琐碎且容易出错，Calcite 的 `SqlValidator` 已经非常成熟。
3. **关系代数变换规则库**：100+ 条优化规则（`CoreRules`），覆盖投影下推、过滤下推、聚合合并、Join 重排序等经典优化。
4. **元数据框架**：基于 Janino 运行时编译的元数据系统，可以高效计算选择率、行数估计等统计信息。

### 1.4.2 Calcite 做什么不够

1. **分布式执行**：Calcite 是单机模型，没有分区感知、shuffle 规划、容错机制
2. **代价模型**：默认代价模型过于简单，生产级系统需要基于统计信息的精细代价估计
3. **CBO 的搜索效率**：VolcanoPlanner 在复杂查询（10+ 表 Join）时可能指数级膨胀
4. **自适应执行**：Calcite 是静态优化，没有运行时反馈和计划调整能力

### 1.4.3 各引擎的取舍策略

| 引擎 | 取 | 舍 |
|------|---|---|
| Spark | Parser + Validator + 部分 Rules | 自研 Catalyst 优化器 + 自研代价模型 |
| StarRocks | Parser + Validator | 自研 CBO + 分布式执行 |
| MaxCompute | Parser + Validator + 部分 Rules | 自研优化器 + 分布式执行 |
| Flink | Parser + Validator + Planner | 自研流式执行 + 状态管理 |
| Druid | 完整使用 Calcite | 仅处理单节点查询 |

## 1.5 源码导览

### 1.5.1 项目结构

Calcite 1.42 的源码组织为 Gradle 多模块项目：

```
calcite/
├── core/              # 核心：1635 个 Java 文件，本书的重点
├── linq4j/            # LINQ4J 库：145 文件，表达式树与可枚举操作
├── babel/             # 多方言 SQL 解析扩展
├── server/            # HTTP/Avatica 服务端
├── testkit/           # 测试工具包
├── plus/              # 扩展功能（40 文件）
├── arrow/             # Apache Arrow 适配器
├── spark/             # Spark 适配器
├── cassandra/         # Cassandra 适配器
├── druid/             # Druid 适配器
├── elasticsearch/     # Elasticsearch 适配器
├── file/              # 文件系统适配器
├── geode/             # Geode 适配器
├── innodb/            # InnoDB 适配器
├── kafka/             # Kafka 适配器
├── mongodb/           # MongoDB 适配器
├── pig/               # Pig 适配器
├── piglet/            # Piglet 解析器
├── redis/             # Redis 适配器
├── splunk/            # Splunk 适配器
└── example/
    ├── csv/           # CSV 适配器（入门示例）
    └── function/      # 自定义函数示例
```

### 1.5.2 Core 包的全景图

core 模块是 Calcite 的灵魂，按功能分为 19 个顶层包：

| 包名 | 文件数 | 职责 |
|------|--------|------|
| `sql` | 492 | SQL 解析、验证、操作符、类型、方言 |
| `rel` | 392 | 关系算子、优化规则、元数据、类型 |
| `adapter` | 146 | Enumerable 代码生成、JDBC/Java 适配 |
| `util` | 144 | 工具类：图算法、映射、格式化 |
| `runtime` | 72 | 运行时：函数库、异常、Hook |
| `schema` | 65 | Schema/Table/Function 定义 |
| `rex` | 59 | 行表达式（RexNode）体系 |
| `plan` | 88 | 优化器框架：Volcano、Hep、Trait |
| `interpreter` | 34 | 解释执行引擎 |
| `linq4j` (独立模块) | 145 | LINQ 风格的可枚举操作与表达式树 |
| `materialize` | 23 | 物化视图与 Lattice |
| `sql2rel` | 24 | SQL AST → RelNode 转换 |
| `model` | 19 | JSON 模型定义 |
| `jdbc` | 25 | JDBC Driver 实现 |
| `tools` | 16 | Frameworks、RelBuilder、Planner API |
| `prepare` | 10 | 查询准备管线 |
| `config` | 8 | 配置项定义 |
| `profile` | 4 | 数据 Profiling |
| `statistic` | 4 | 统计信息 |

### 1.5.3 核心处理管线

一条 SQL 从输入到输出，经过以下阶段。我们在 `CalcitePrepareImpl.prepare2_()` 方法中可以清晰地看到这个管线：

```java
// CalcitePrepareImpl.java:560-675 (简化)
SqlParser parser = createParser(query.sql, parserConfig);
SqlNode sqlNode = parser.parseStmt();          // 1. 解析

SqlValidator validator = preparingStmt.createSqlValidator(catalogReader, ...);
preparedResult = preparingStmt.prepareSql(sqlNode, ...);  // 2-5. 验证→转换→优化→实现
```

而 `Prepare.optimize()` 方法揭示了优化阶段的内部结构：

```java
// Prepare.java:143-187 (简化)
protected RelRoot optimize(RelRoot root, ...) {
    final RelOptPlanner planner = root.rel.getCluster().getPlanner();
    planner.setExecutor(new RexExecutorImpl(dataContext));

    // 注册物化视图和 Lattice
    for (Materialization m : materializations) { ... }
    for (CalciteSchema.LatticeEntry l : lattices) { ... }

    // 设置目标 Trait（如 EnumerableConvention）
    final RelTraitSet desiredTraits = getDesiredRootTraitSet(root);

    // 执行优化 Program
    final Program program = getProgram();
    final RelNode rootRel4 = program.run(planner, root.rel, desiredTraits, ...);
    return root.withRel(rootRel4);
}
```

默认的优化 Program 是 `Programs.standard()`，它按顺序执行以下子程序：

```java
// Programs.java:321-344 (简化)
List<Program> programs = Lists.newArrayList(
    subQuery(metadataProvider),     // 1. 子查询消除
    new DecorrelateProgram(),       // 2. 解关联
    measure(metadataProvider),      // 3. MEASURE 处理
    new TrimFieldsProgram(),        // 4. 字段裁剪
    program1,                       // 5. 主优化（Volcano/Hep 搜索最优计划）
    calc(metadataProvider)          // 6. 第二遍优化（引入 EnumerableCalc）
);
```

### 1.5.4 关键类速查

以下是贯穿全书的核心类，读者应尽早建立印象：

| 类 | 包 | 职责 |
|----|-----|------|
| `SqlNode` | `sql` | SQL AST 的基类 |
| `SqlKind` | `sql` | 200+ 种 SQL 节点类型枚举 |
| `SqlParser` | `sql.parser` | SQL 解析器入口 |
| `SqlValidator` | `sql.validate` | SQL 验证器接口 |
| `SqlOperator` | `sql` | SQL 操作符/函数的基类 |
| `SqlStdOperatorTable` | `sql.fun` | 标准操作符注册表 |
| `RelNode` | `rel` | 关系算子的基类 |
| `RexNode` | `rex` | 行表达式的基类 |
| `RexBuilder` | `rex` | 表达式构造工厂 |
| `RexProgram` | `rex` | 表达式程序（Filter+Project 融合） |
| `RexSimplify` | `rex` | 表达式化简引擎 |
| `RelOptPlanner` | `plan` | 优化器接口 |
| `VolcanoPlanner` | `plan.volcano` | Volcano 优化器实现 |
| `HepPlanner` | `plan.hep` | Hep 优化器实现 |
| `RelOptRule` | `plan` | 优化规则基类 |
| `RelOptCluster` | `plan` | 优化上下文（planner + rexBuilder + metadata） |
| `RelTrait` / `Convention` | `plan` | 物理属性/约定 |
| `SqlToRelConverter` | `sql2rel` | SQL AST → RelNode 转换器 |
| `RelBuilder` | `tools` | 程序化构建关系表达式的 API |
| `Frameworks` | `tools` | 使用 Calcite 的标准入口 |
| `CalcitePrepareImpl` | `prepare` | 查询准备的完整实现 |
| `EnumerableConvention` | `adapter.enumerable` | Java 代码生成约定 |

### 1.5.5 阅读源码的方法论

基于本书的目标——从源码理解本质——我推荐以下阅读策略：

1. **自顶向下追踪**：从 `CalcitePrepareImpl.prepare2_()` 入口开始，跟踪一条简单 SQL 的完整处理路径。这是最快建立全局视图的方法。
2. **按层阅读**：先理解数据结构（SqlNode、RelNode、RexNode），再理解算法（验证、转换、优化）。
3. **测试驱动**：每个核心类都有对应的测试（如 `SqlValidatorTest`、`RelBuilderTest`、`HepPlannerTest`），测试用例是最好的文档。
4. **对比阅读**：将 Calcite 的实现与你熟悉的 Spark Catalyst / StarRocks 优化器对比，异同之处都是学习的抓手。

---

## 本章小结

Calcite 的第一性原理可以用一句话概括：**查询处理是声明式语义到物理执行的映射问题，而 Calcite 通过可组合的管线和可替换的组件，让每个阶段都可以独立理解、独立扩展、独立替换。**

这个模块化设计既是 Calcite 的最大优势（被几十个项目采用），也是其复杂性来源（理解全链路需要掌握每个阶段的内部机制）。后续章节将按管线顺序，逐层深入每个阶段的源码实现。
