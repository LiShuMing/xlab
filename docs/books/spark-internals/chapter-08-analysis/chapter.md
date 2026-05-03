# 第 8 章：Analysis — 从 SQL 文本到解析计划

## 设计动机

SQL 是一种"declarative"（声明式）语言：用户说"我要什么"，而不是"怎么做"。这给了优化器最大的自由度，也给了 Analysis 阶段最大的负担：**把用户的自然意图映射到数据库实际的表、列、函数、类型上，而且要能在出错时告诉用户哪里错了。**

这个过程就是 Resolution（解析）。它回答以下问题：

- `FROM users` — `users` 是哪个表？哪个 catalog？哪个 database？
- `WHERE age > 18` — `age` 是哪一列？来自哪张表？类型是什么？
- `COUNT(*)` — 调用的函数 COUNT 是什么？它的返回类型是什么？
- `GROUP BY a` — 这个 `a` 是哪张表的哪一列？
- `SELECT *` — `*` 要展开为哪些列？

这些问题对用户来说似乎很简单，但 SQL 的规则远比任何人想象的复杂——LATERAL COLUMN ALIAS、NATURAL JOIN、WITH 子查询、Type Coercion（隐式类型转换）、VARIANT/JSON 结构……这份复杂性在 `Analyzer.scala` 中压缩成了超过 4000 行代码和约 60 条规则。

## 核心原理

### 8.1 从 Unresolved 到 Resolved：Analysis 的输入和输出

Analysis 的"原材料"是 **Unresolved Logical Plan**——一个经过 ANTLR 语法解析后产生的树，包含各种 Unresolved* 节点：

```
'Project ['*]
+- 'Filter ('customers.id = 1)
   +- 'UnresolvedRelation [customers], [], false
```

这是 `df.select("*").filter("customers.id = 1")` 的未解析计划。注意：
- `UnresolvedRelation`：表 `customers` 还没有与实际 catalog 中的表对应
- `'customers.id`：这是一个 **UnresolvedAttribute**，Catalog 不知道 `customers` 是哪张表，也就不知道它的列有哪些

Analysis 的输出是 **Resolved Logical Plan**：

```
Project [id#0, name#1, email#2]
+- Filter (id#0 = 1)
   +- SubqueryAlias customers
      +- Relation spark_catalog.default.customers [id#0, name#1, email#2] parquet
```

每个列都已经与具体的 table 和 type 绑定，元数据完备。

### 8.2 ANTLR 语法解析

Spark SQL 的语法文件位于 `sql/api/src/main/antlr4/org/apache/spark/sql/catalyst/parser/SqlBase.g4`。

解析过程：

```
SQL 字符串 → SqlBaseLexer (词法分析) → tokens → SqlBaseParser (语法分析) → ParseTree → AstBuilder (AST 构建) → LogicalPlan
```

`AstBuilder` 访问 Antlr 生成的 ParseTree，逐节点转换为 Spark 的 LogicalPlan 节点：

```scala
// 简化版：AstBuilder 如何处理 SELECT * FROM t WHERE x > 1
override def visitQuerySpecification(ctx: QuerySpecificationContext): LogicalPlan = {
  val from = visitFromClause(ctx.fromClause)  // UnresolvedRelation for 't'
  val filter = ctx.whereClause.map(visitBooleanExpression)  // 'x > 1
  val select = visitSelectClause(ctx.selectClause)  // Project with '*'
  // 组合为: Filter(UnresolvedRelation(t), x > 1)
  withFilter(filter)(withProject(select, from))
}
```

关键的一点：**AstBuilder 产生的不是 Resolved Plan，而是精心标记的 Unresolved Plan**。ANALYZER 不会在解析后"重新发现"结构，而是利用 AstBuilder 已经构建好的树进行查找和替换。

### 8.3 Analyzer 的批次设计

`Analyzer` 继承 `RuleExecutor[LogicalPlan]`，通过 `batches` 方法定义了批次序列：

```scala
// Analyzer.scala:443
override def batches: Seq[Batch] = earlyBatches ++ Seq(
  Batch("Resolution", fixedPoint, ...),
  Batch("Remove TempResolvedColumn", Once, ...),
  Batch("Post-Hoc Resolution", Once, ...),
  Batch("Remove Unresolved Hints", Once, ...),
  Batch("Nondeterministic", Once, ...),
  Batch("ScalaUDF Null Handling", fixedPoint, ...),
  Batch("UDF", Once, ...),
  Batch("Subquery", Once, ...),
  Batch("Cleanup", fixedPoint, ...),
  Batch("HandleSpecialCommand", Once, ...),
  Batch("Remove watermark for batch query", Once, ...),
  Batch("ResolveUnresolvedHaving", Once, ...)
)
```

#### earlyBatches（预处理器）

在主力 Resolution 批次开始前，有几项预先操作：

```scala
// Analyzer.scala:419-441
private def earlyBatches: Seq[Batch] = Seq(
  Batch("Substitution", fixedPoint,
    OptimizeUpdateFields,    // 优化 UpdateFields 表达式链
    CTESubstitution,         // 替换 CTE 引用
    WindowsSubstitution,     // 替换 Window 表达式引用
    EliminateUnions,         // 消除空的 Union 节点
    EliminateLazyExpression), // 移除 LazyExpression 包装
  Batch("Apply Limit All", Once, ApplyLimitAll),
  Batch("Disable Hints", Once, ...),
  Batch("Hints", fixedPoint, ...),
  Batch("Simple Sanity Check", Once, LookupFunctions),
  Batch("Keep Legacy Outputs", Once, KeepLegacyOutputs)
)
```

`CTESubstitution` 是一个很好的例子：WITH 子句中的每个 CTE 在整个查询中的引用被内联展开为子树。这个操作必须在 Resolution 之前完成，因为 CTE 中的表也需要被解析。

#### Resolution（核心批次，FixedPoint）

这才是真正的重头戏。约 40 条规则按此顺序运行：

```scala
Batch("Resolution", fixedPoint,
  new ResolveCatalogs(catalogManager) ::  // 1. 解析 catalog/database 名
  ResolveInsertInto ::                     // 2. 解析 INSERT INTO 的目标表
  ResolveRelations ::                     // 3. 将 UnresolvedRelation → Resolved Table
  ResolvePartitionSpec ::                 // 4. 解析 PARTITION 说明
  ResolveFieldNameAndPosition ::          // 5. 解析列引用
  AddMetadataColumns ::                  // 6. 添加文件 metadata 列
  DeduplicateRelations ::                // 7. 去重相同关系（self-join 场景）
  ...
  ResolveReferences ::                   // 约第10位，解析列引用
  ResolveLateralColumnAliasReference ::  // LATERAL COLUMN ALIAS
  ResolveDeserializer ::                 // Dataset API 序列化
  ResolveUpCast ::                       // 向上转换类型
  ResolveGroupingAnalytics ::            // GROUPING SETS, ROLLUP, CUBE
  ResolvePivot ::                        // PIVOT 操作
  ResolveFunctions ::                    // 解析函数调用
  ResolveAliases ::                      // 别名解析
  ResolveSubquery ::                     // 子查询解析
  ResolveWindowOrder ::                  // Window ORDER BY
  ResolveWindowFrame ::                  // Window 边界
  ResolveNaturalAndUsingJoin ::          // NATURAL/USING JOIN
  ExtractWindowExpressions ::            // 提取 Window 表达式
  GlobalAggregates ::                    // 全局聚合
  ResolveAggregateFunctions ::           // 聚合函数
  TimeWindowing ::                       // 时间窗口
  ...)
```

这条规则链的设计思路是**分层递进**：

1. 最外层：解析表名、catalog 元数据（前 5 条）
2. 中间层：当表信息已知后，解析列引用和函数（第 6-25 条）
3. 内层：当所有引用已绑定后，进行聚合/窗口等语义解析（第 26-40 条）

这就是为什么需要 `FixedPoint`——列引用的解析无法在表解析之前进行，但解析更深的语义（如 window 边界中引用别名列）可能又需要一层一层递归覆盖。

### 8.4 关键解析规则

#### ResolveRelations — 表名解析

```scala
// Analyzer.scala 中该规则的核心
object ResolveRelations extends Rule[LogicalPlan] {
  def apply(plan: LogicalPlan): LogicalPlan = plan.resolveOperatorsUpWithPruning(
    _.containsPattern(UNRESOLVED_RELATION)) {
    case u: UnresolvedRelation =>
      // 尝试在 SessionCatalog 中查找
      val table = v1SessionCatalog.resolveRelation(u.multipartIdentifier)
      table match {
        case Some(table) => table  // 找到 V1 表
        case None =>
          // 尝试在 CatalogManager 的 V2 proxies 中查找
          resolveV2Relation(u.multipartIdentifier)
      }
    }
}
```

表名解析考虑 multi-part 标识符：`catalog.db.table` 和 `db.table` 和单独的 `table`。对于 `table` 形式，使用当前的 catalog 和 schema。

#### ResolveReferences — 列引用解析

这是 Analysis 中最具挑战性的规则，因为 SQL 的列引用可以来自：

1. 直接的表列引用：`SELECT a FROM t`
2. 带有表限定符的引用：`SELECT t.a FROM t`
3. 引用别名列：`SELECT a+1 AS x, x+1 FROM t`（LATERAL COLUMN ALIAS）
4. 隐式引用：`SELECT * FROM t`

对于 `UnresolvedAttribute`，解析路径是：

```scala
// 遍历 plan 的输出列，检查 name match
plan.resolve(nameParts, resolver)  // resolver 是 case-insensitive 或 case-sensitive
  .getOrElse(throw QueryCompilationErrors.unresolvedAttributeError(
    "UNRESOLVED_COLUMN", nameParts, plan.output))
```

当 resolve 失败时，产生的错误是 Spark SQL 用户最常见的错误消息之一："cannot resolve 'column_name' given input columns: [a, b, c]"

#### ResolveFunctions — 函数解析

SQL 函数存在三个来源：
- **Builtin 函数**（如 `count`, `sum`, `substring`, `concat`）：硬编码在 `FunctionRegistry.builtin` 中，包含类型签名
- **Temporary 函数**：用户通过 `CREATE TEMPORARY FUNCTION` 注册的
- **Permanent 函数**（V1 和 V2）：存储在 Catalog 中的持久化 UDF

解析通过链式查找：temp → builtin → catalog。这是按查找速度（和重载风险）排序的——最快的路径（temp）优先。

### 8.5 SessionCatalog：元数据的生命周期

`SessionCatalog` 是所有元数据的"哈希表"。一个 SparkSession 包含一个 SessionCatalog，维持：

- **表映射**：`name → CatalogTable`（包含 schema、location、format、partition info）
- **数据库/namespace 映射**：`name → db metadata`
- **函数 registry**：`name → FunctionDescription`
- **临时视图**：`name → LogicalPlan`

Catalog 的模式是**外部化的**——表的实际元数据存储在 Hive Metastore、AWS Glue 或其他 catalog 实现中。`SessionCatalog` 在需要时向外部服务发出 lookup（通常是缓存的，避免每次查询都 RPC 到 metastore）。

在 `Analyzer` 类中：

```scala
// Analyzer.scala:297
private val v1SessionCatalog: SessionCatalog = catalogManager.v1SessionCatalog
private val relationResolution = new RelationResolution(catalogManager, sharedRelationCache)
private val functionResolution = new FunctionResolution(catalogManager, relationResolution)
```

注意这三个协作者的分工：
- `sessionCatalog`：与 SQL 标准的 V1 表交互
- `relationResolution`：统一的表/命名空间解析，桥接 V1 和 V2
- `functionResolution`：统一的函数解析，桥接 V1 和 V2

### 8.6 Analysis 中的 Hybrid Analyzer（单趟解析器）

Spark 3.4+ 引入了 `HybridAnalyzer`——一个实验性的**单趟解析器**，旨在取代传统多趟迭代的 `Analyzer`。

传统 Analyzer 的问题：一个包含多个 CTE、嵌套子查询和复杂 LATERAL COLUMN ALIAS 的查询可能需要 10+ 次 FixedPoint 迭代才能完成解析。每次迭代意味着遍历整棵树。对于 deep query，这会成为编译时的瓶颈。

`HybridAnalyzer` 的设计是一次性地跟踪符号解析状态：

```scala
// Analyzer.scala:336
def executeAndCheck(plan: LogicalPlan, tracker: QueryPlanningTracker): LogicalPlan = {
  if (plan.analyzed) {
    plan
  } else {
    AnalysisHelper.markInAnalyzer {
      HybridAnalyzer.fromLegacyAnalyzer(legacyAnalyzer = this, tracker = tracker).apply(plan)
    }
  }
}
```

它维护一个 **`AnalyzerBridgeState`**，将符号（表、列、函数、类型）映射到已解析信息。在单次 DFS 遍历中逐步建立解析上下文，避免反复迭代。

引入单趟解析器的过程是渐进的，保留了对旧行为回退的能力（通过 `SQLConf.RESOLVER_DEFAULT_MODE` 控制）。

## 关键代码片段

### 示例：RESOLVE RELATIONS 的完整链路

```scala
// 1. 用户写: spark.table("db.table_name")
// 2. LogicalPlan 获得: UnresolvedRelation(Seq("db", "table_name"))

// 3. 在 Analyzer 的 Resolution batch 中
object ResolveRelations {
  def resolveV1Table(u: UnresolvedRelation): LogicalPlan = {
    val catalog = sessionCatalog  // 从 Analyzer 获得
    val tableIdent = u.multipartIdentifier  // Seq("db", "table_name")
    
    // 查找 catalog
    val table = catalog.lookupRelation(tableIdent)
    
    // 解析 nested columns - 如果用户写了 table_name.inner_field
    // 将其变换为正确的 nested field access patterns
    u.outputNames.view.zip(table.output).foreach { ... }
    
    table
  }
}
```

### 示例：Type Coercion — 何时及为何改变类型

```scala
// 在表达式 `WHERE salary > 100000.0` 中，
// 如果 salary 的类型是 INTEGER，比较 `INT > DOUBLE` 需要类型向上转换

// TypeCoercion 规则负责:
// INT 和 DOUBLE → 两者都转换为 DOUBLE
// DOUBLE 和 DECIMAL(10,2) → 两者都转换为 DECIMAL(10,2)
// DATE 和 TIMESTAMP → DATE 转换为 TIMESTAMP

// 这些规则是"静态"的：它们根据已知的类型体系产生确定性输出
```

## 硬件视角

分析阶段在 JVM 上产生大量的小对象——每个列引用是一个 `UnresolvedAttribute` case class，每个函数调用是一个 `UnresolvedFunction`。一个有 500 列 SELECT * 的查询在分析初始就创建了 500+ 个这样的对象。

这不是偶然的——它是 "不可变树" 模型的直接代价。但你注意过吗：**每次 transformDown（复制树时）产生了多少 GC 压力**？

如果一个分析用了 10 次 FixedPoint 迭代，每次迭代都需要创建新的树副本。在一个复杂的 join 查询中，这可能是 10 ×（1000 个 plan nodes + 5000 个 expression nodes）的对象分配。

`HybridAnalyzer` 的单趟方法的一个（未声明的）优势恰恰在这里：更少的迭代 → 更少的对象创建 → 更低的 GC 开销。这是一个有趣的例子，表明 **"正确的" 软件工程实践（不可变数据 + 定点迭代）与最佳硬件性能（更少的 GC）之间可能未必一致**。

## AI 时代反思

Analysis 阶段的本质是**符号到实体的映射**。这让人想到编程语言的 type checker 和 linker。也让人想到 LLM 的 RAG（Retrieval-Augmented Generation）：从自然语言问题中提取"符号"（实体名），检索知识库，将其映射到具体数据。

想象一下：如果有人构建了一个 "Natural Language → Spark 查询" 的系统，最重要的瓶颈不是 LLM 生成 SQL 的质量，而是 LLM 无法知道用户的表结构、列名、数据类型。这些恰恰是 SessionCatalog 的内容。

那么，SessionCatalog 作为 RAG 上下文，喂给 LLM，让它正确地生成 SQL，也是一种 `Analysis`，只是发生在 LLM 内部。

Spark Connect（我们将在第 26 章讨论）提供了这样一种分离：客户端将 Plan 序列化为 Protobuf，服务端持有 SessionCatalog 和查询执行。如果 LLM 是客户端，它只需要知道如何生成一个语法正确的 Plan——剩下的事，Analysis 引擎将替它完成。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/analysis/Analyzer.scala` | Analyzer 类，批次定义，所有解析规则 | 291 (类定义), 353 (fixedPoint), 419 (earlyBatches), 443 (batches) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/catalog/SessionCatalog.scala` | SessionCatalog 的表/函数/视图 registry |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/analysis/HybridAnalyzer.scala` | 单趟解析器实现 |
| `sql/api/src/main/antlr4/org/apache/spark/sql/catalyst/parser/SqlBase.g4` | ANTLR 语法文件，定义完整的 SQL 语法 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/parser/AstBuilder.scala` | ANTLR ParseTree → LogicalPlan 的转换 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/analysis/FunctionResolution.scala` | V1+V2 统一函数解析 |
