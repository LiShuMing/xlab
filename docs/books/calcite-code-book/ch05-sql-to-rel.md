# 第5章：SqlToRelConverter — 跨越两个世界的桥梁

## 5.1 转换的本质

SQL 验证器产出一棵验证后的 SqlNode AST——它仍然是 SQL 世界的表示，每个节点是 `SqlSelect`、`SqlCall`、`SqlIdentifier` 这样的 SQL 构造。而优化器需要的是关系代数世界的表示——`LogicalTableScan`、`LogicalFilter`、`LogicalProject`、`LogicalJoin` 这样的关系算子。

SqlToRelConverter 就是连接这两个世界的桥梁：

```
SqlNode AST (SQL 世界)         RelNode 树 (关系代数世界)
─────────────────────         ──────────────────────
SqlSelect                  →  LogicalProject + LogicalFilter + LogicalTableScan
SqlJoin                    →  LogicalJoin
SqlBasicCall(+)            →  RexCall(+)   (注意：仍在 RexNode 层)
SqlIdentifier("e.name")    →  RexInputRef($2)
SqlLiteral(42)             →  RexLiteral(42)
SqlOrderBy                 →  LogicalSort
GROUP BY + SUM()           →  LogicalAggregate
OVER (PARTITION BY ...)    →  LogicalWindow
```

源码位置：`core/src/main/java/org/apache/calcite/sql2rel/`（24 文件）

## 5.2 SqlToRelConverter 架构

### 5.2.1 核心类关系

```
SqlToRelConverter (主转换器)
├── Blackboard (转换工作区，内部类)
├── AggConverter (聚合转换器，内部类)
├── SubQueryConverter (子查询转换器接口)
└── SqlRexConvertlet / StandardConvertletTable (表达式转换分发)

SqlNodeToRexConverter (SQL 节点 → RexNode 转换)
├── SqlNodeToRexConverterImpl (实现)
```

### 5.2.2 convertQuery — 转换入口

```java
// SqlToRelConverter.java:622
public RelRoot convertQuery(SqlNode query, boolean needsValidation, boolean top) {
  // 1. 如果需要，先验证
  if (needsValidation) {
    query = validator().validate(query);
  }

  // 2. 递归转换
  RelNode result = convertQueryRecursive(query, top, null).rel;

  // 3. 后处理
  if (top) {
    result = unwrapMeasures(result);  // 处理 MEASURE 类型
    if (isStream(query)) {
      result = new LogicalDelta(cluster, result.getTraitSet(), result);  // 流式查询
    }
  }

  // 4. 提取排序信息
  RelCollation collation = RelCollations.EMPTY;
  if (!query.isA(SqlKind.DML) && isOrdered(query)) {
    collation = requiredCollation(result);
  }

  // 5. 处理 Hints
  List<RelHint> hints = ...;

  return RelRoot.of(result, validatedRowType, query.getKind())
      .withCollation(collation)
      .withHints(hints);
}
```

`RelRoot` 是转换的最终结果，包含了 RelNode 树、验证后的行类型、SQL 语句类型和排序信息。

## 5.3 Blackboard — 转换的工作区

Blackboard 是 SqlToRelConverter 最核心的内部类。它维护了转换过程中的所有中间状态：

```java
// SqlToRelConverter.Blackboard (内部类)
protected class Blackboard implements SqlRexContext, SqlVisitor<RexNode>,
    InitializerContext {
  public final SqlValidatorScope scope;     // 当前作用域
  public @Nullable RelNode root;            // 当前构建的 RelNode 根
  private @Nullable List<RelNode> inputs;   // 输入 RelNode 列表

  private final Map<CorrelationId, RexFieldAccess> mapCorrelateToRex;  // 关联变量映射
  private final List<SubQuery> subQueryList;     // 待处理的子查询
  private @Nullable AggConverter agg;            // 聚合转换工作区
  private @Nullable SqlWindow window;            // 窗口定义

  // 将 SqlNode 表达式转换为 RexNode
  public RexNode convertExpression(SqlNode node) {
    return node.accept(this);  // 使用 Visitor 模式
  }
}
```

Blackboard 的核心设计是 **累积式构建**：随着 SELECT 各子句的转换，`root` 字段不断被更新，形成一个自底向上的 RelNode 树：

```
初始:  root = LogicalTableScan(emp)
WHERE: root = LogicalFilter(root, condition)
GROUP: root = LogicalAggregate(root, ...)
HAVING: root = LogicalFilter(root, havingCondition)
SELECT: root = LogicalProject(root, projections)
ORDER: root = LogicalSort(root, collation)
```

## 5.4 SELECT 语句的转换

### 5.4.1 convertSelect — SELECT 的完整转换流程

```java
// SqlToRelConverter.java:754
protected void convertSelectImpl(Blackboard bb, Blackboard measureBb, SqlSelect select) {
  // 1. 转换 FROM 子句
  convertFrom(bb, select.getFrom());
  // bb.root = LogicalTableScan / LogicalJoin / ...

  // 2. 转换 WHERE 子句
  convertWhere(bb, select.getWhere());
  // bb.root = LogicalFilter(root, whereCondition)

  // 3. 收集 ORDER BY 表达式
  gatherOrderExprs(bb, select, select.getOrderList(), orderExprList, collationList);

  // 4. 转换 SELECT 列表（含 GROUP BY / HAVING / 聚合）
  convertSelectList(bb, measureBb, select, orderExprList, ImmutableList.of(), select.getQualify());

  // 5. 处理 DISTINCT
  if (select.isDistinct()) {
    distinctify(bb, true);
  }

  // 6. 转换 ORDER BY / OFFSET / FETCH
  convertOrder(select, bb, collation, orderExprList, select.getOffset(), select.getFetch());

  // 7. 附加 Hints
  // ...
}
```

### 5.4.2 FROM 子句的转换

`convertFrom()` 方法按 FROM 子句的类型分发：

```java
// SqlToRelConverter.java:2518
protected void convertFrom(Blackboard bb, @Nullable SqlNode from, ...) {
  if (from == null) {
    bb.setRoot(LogicalValues.createOneRow(cluster), false);  // 无 FROM → 单行
    return;
  }

  switch (from.getKind()) {
    case AS:          // 别名: emp AS e
      convertFrom(bb, from.operand(0), fieldNameList);
      return;
    case IDENTIFIER:  // 表名: emp
      convertIdentifier(bb, (SqlIdentifier) from, ...);
      return;
    case JOIN:        // JOIN: emp JOIN dept ON ...
      convertFrom(bb, from.left);   // 左表
      RelNode left = bb.root;
      convertFrom(bb, from.right);  // 右表
      RelNode right = bb.root;
      // 创建 LogicalJoin
      bb.setRoot(LogicalJoin.create(left, right, condition, ...), true);
      return;
    case SELECT:      // 子查询: (SELECT ...)
      SubQuery subQuery = ...;
      RelNode subRel = convertQueryRecursive(from, false, null).rel;
      bb.setRoot(subRel, true);
      return;
    case UNION:       // 集合运算
    case INTERSECT:
    case MINUS:
      // 递归转换两侧，创建对应的 Logical 算子
      return;
    case PIVOT:       convertPivot(bb, (SqlPivot) from);     return;
    case UNPIVOT:     convertUnpivot(bb, (SqlUnpivot) from); return;
    case MATCH_RECOGNIZE: convertMatchRecognize(bb, ...);     return;
    case TABLESAMPLE: ...                                     return;
    case SNAPSHOT:    ...                                     return;
    // ...
  }
}
```

关键观察：**FROM 子句的转换先于 WHERE 和 SELECT**，因为它确定了数据源——后续所有操作都基于 FROM 产出的行类型。

### 5.4.3 WHERE 子句的转换

```java
// SqlToRelConverter.java:1226
private void convertWhere(Blackboard bb, @Nullable SqlNode where) {
  if (where == null) return;

  // 1. 下推 NOT（用于 IN 子查询）
  SqlNode newWhere = pushDownNotForIn(bb.scope, where);

  // 2. 替换子查询（IN → SemiJoin，EXISTS → SemiJoin，标量子查询 → Aggregate）
  replaceSubQueries(bb, newWhere, RelOptUtil.Logic.UNKNOWN_AS_FALSE);

  // 3. 转换条件表达式
  RexNode convertedWhere = bb.convertExpression(newWhere);

  // 4. 简化谓词
  RexNode convertedWhere2 = simplifyPredicate(convertedWhere);

  // 5. 创建 LogicalFilter
  if (!convertedWhere2.isAlwaysTrue()) {
    RelNode filter = LogicalFilter.create(bb.root(), convertedWhere2, ...);
    bb.setRoot(filter, false);
  }
}
```

子查询替换是 WHERE 转换中最复杂的部分。`replaceSubQueries()` 遍历 WHERE 条件中的所有子查询节点，将其替换为对应的 RelNode：

- `IN (SELECT ...)` → `SemiJoin` 或 `AntiJoin`
- `EXISTS (SELECT ...)` → `SemiJoin`
- `NOT EXISTS (SELECT ...)` → `AntiJoin`
- 标量子查询 → `Aggregate` + `Correlate`（如果关联）

## 5.5 SqlRexContext 与 ConvertletTable

### 5.5.1 表达式转换的分发机制

SQL 表达式（SqlNode）到 Rex 表达式（RexNode）的转换通过 **Convertlet** 模式实现——类似访问者模式，但更灵活：

```java
// sql2rel/SqlRexConvertlet.java
public interface SqlRexConvertlet {
  RexNode convertCall(SqlRexContext cx, SqlCall call);
}
```

`SqlRexContext` 是转换上下文接口，`Blackboard` 实现了此接口。

### 5.5.2 StandardConvertletTable

`StandardConvertletTable`（2569 行）注册了 75 种操作符的转换规则：

```java
// StandardConvertletTable.java (部分)
registerOp(CAST, this::convertCast);
registerOp(PLUS, this::convertPlus);
registerOp(MINUS, this::convertMinus);
registerOp(IS_DISTINCT_FROM, this::convertIsDistinctFrom);
registerOp(IS_NOT_DISTINCT_FROM, this::convertIsDistinctFrom);
registerOp(DATE, this::convertDatetime);
registerOp(DATETIME_TRUNC, this::convertDatetime);
registerOp(LTRIM, this::convertTrim);
registerOp(RTRIM, this::convertTrim);
registerOp(GREATEST, new GreatestConvertlet());
registerOp(LEAST, new GreatestConvertlet());
registerOp(SUBSTR_BIG_QUERY, this::convertSubstring);
registerOp(SUBSTR_MYSQL, this::convertSubstring);
registerOp(SUBSTR_ORACLE, this::convertSubstring);
// ... 共 75 条注册
```

未注册的操作符走默认转换逻辑：递归转换所有操作数，然后用 `RexBuilder.makeCall()` 创建 `RexCall`。

## 5.6 SELECT 列表的转换

### 5.6.1 convertSelectList

SELECT 列表的转换是整个转换过程中最复杂的部分，因为它需要同时处理：

- 普通表达式 → `LogicalProject`
- 聚合函数 + GROUP BY → `LogicalAggregate`
- 窗口函数 → `LogicalWindow`
- DISTINCT → `LogicalAggregate`（去重）

转换策略是分层处理：

1. 如果有聚合函数或 GROUP BY，先创建 `LogicalAggregate`
2. 在聚合之上创建 `LogicalProject`（映射 SELECT 列表中的表达式）
3. 如果有窗口函数，创建 `LogicalWindow`
4. 如果有 DISTINCT，添加去重的 `LogicalAggregate`

### 5.6.2 星号展开

`SELECT *` 和 `SELECT t.*` 需要在转换时展开为具体的列：

```sql
SELECT * FROM emp
-- 展开为
SELECT empno, ename, job, mgr, hiredate, sal, comm, deptno FROM emp
```

展开基于 FROM 子句产出的行类型，考虑别名映射。

### 5.6.3 聚合转换 — AggConverter

`AggConverter` 是 SqlToRelConverter 的内部类，负责将 SQL 聚合转换为 `LogicalAggregate`：

```sql
SELECT deptno, COUNT(*), AVG(sal)
FROM emp
GROUP BY deptno
```

转换过程：

```
1. 识别 GROUP BY 列表: [deptno]  → groupSet = {0}
2. 识别聚合调用:
   COUNT(*) → AggregateCall(COUNT, args=[], distinct=false)
   AVG(sal) → AggregateCall(AVG, args=[5], distinct=false)
3. 创建 LogicalAggregate:
   input = LogicalTableScan(emp)
   groupSet = {0}
   aggCalls = [COUNT(*), AVG($5)]
4. 创建 LogicalProject:
   将 SELECT 列表映射到聚合输出的列引用
```

### 5.6.4 窗口函数转换 — convertOver

```java
// SqlToRelConverter.java:2385
private RexNode convertOver(Blackboard bb, SqlNode node) {
  // 1. 解析窗口定义
  SqlWindow window = validator().resolveWindow(windowOrRef, bb.scope);

  // 2. 转换 PARTITION BY
  for (SqlNode partition : partitionList) {
    partitionKeys.add(bb.convertExpression(partition));
  }

  // 3. 转换 ORDER BY（窗口内排序）
  // 4. 转换窗口边界
  RexNode lowerBound = bb.convertExpression(sqlLowerBound);
  RexNode upperBound = bb.convertExpression(sqlUpperBound);

  // 5. 转换聚合函数调用
  RexNode aggRex = bb.convertExpression(aggCall);

  // 6. 创建 RexOver（窗口表达式的 RexNode 表示）
  return rexBuilder.makeOver(
      returnType, aggOperator, aggArgs,
      partitionKeys, orderKeys,
      lowerBound, upperBound,
      rows, ...);
}
```

窗口函数的转换产出 `RexOver`，后续会被 `ProjectToWindowRule` 转换为 `LogicalWindow` 算子。

## 5.7 FROM 子句的深度转换

### 5.7.1 JOIN 的转换

ANSI JOIN 的转换逻辑：

```sql
SELECT e.name, d.dept_name
FROM emp e
LEFT JOIN dept d ON e.dept_id = d.id
WHERE e.salary > 1000
```

转换过程：

```
1. convertFrom(emp AS e)
   → LogicalTableScan(emp)

2. convertFrom(dept AS d)
   → LogicalTableScan(dept)

3. 转换 ON 条件
   e.dept_id = d.id → RexCall(=, [RexInputRef($7), RexInputRef($9)])

4. 创建 LogicalJoin
   LogicalJoin(
     left = LogicalTableScan(emp),
     right = LogicalTableScan(dept),
     condition = =($7, $9),
     joinType = LEFT)
```

### 5.7.2 子查询的转换

FROM 子句中的子查询直接递归调用 `convertQueryRecursive`：

```sql
SELECT * FROM (SELECT name FROM emp WHERE sal > 1000) AS high_earners
```

转换过程：

```
1. convertFrom 内检测到 SELECT → 递归转换
2. convertQueryRecursive(子 SELECT)
   → LogicalProject(name)
     LogicalFilter(sal > 1000)
       LogicalTableScan(emp)
3. 将子查询结果设为 bb.root
```

### 5.7.3 MATCH_RECOGNIZE 的转换

`MATCH_RECOGNIZE` 是 SQL:2016 的模式匹配语法：

```sql
SELECT *
FROM ticker
MATCH_RECOGNIZE (
  PARTITION BY symbol
  ORDER BY tstamp
  MEASURES ...
  PATTERN (A+ B+)
  DEFINE A AS price < 100, B AS price >= 100
)
```

`convertMatchRecognize()` 将其转换为 `LogicalMatch` 算子。

## 5.8 子查询处理

子查询转换是 SqlToRelConverter 中最复杂的逻辑之一。

### 5.8.1 子查询分类

| 类型 | SQL 示例 | 转换目标 |
|------|---------|---------|
| FROM 子查询 | `SELECT * FROM (SELECT ...)` | 直接递归转换 |
| EXISTS | `WHERE EXISTS (SELECT ...)` | SemiJoin |
| NOT EXISTS | `WHERE NOT EXISTS (SELECT ...)` | AntiJoin |
| IN (子查询) | `WHERE x IN (SELECT ...)` | SemiJoin |
| NOT IN | `WHERE x NOT IN (SELECT ...)` | AntiJoin |
| 标量子查询 | `WHERE x > (SELECT ...)` | Correlate + Aggregate |
| 集合构造 | `ARRAY(SELECT ...)` | 保留为子查询 |

### 5.8.2 子查询替换流程

`replaceSubQueries()` → `substituteSubQuery()` 的处理流程：

1. **遍历条件表达式**，收集所有子查询节点（`SubQuery`）
2. **按类型替换**：
   - `IN` / `EXISTS` → 调用 `convertExists()` 生成 SemiJoin/AntiJoin
   - 标量子查询 → 调用 `convertQueryOrInList()` 生成 Aggregate
   - 关联子查询 → 生成 Correlate
3. **将子查询节点替换为 RexSubQuery**（在表达式层面引用子查询的 RelNode）

### 5.8.3 非关联子查询的提前求值

如果子查询是非关联的（不引用外层列），SqlToRelConverter 可以提前求值：

```java
// SqlToRelConverter.java:1762
private boolean convertNonCorrelatedSubQuery(SubQuery subQuery, ...) {
  // 如果子查询不关联外层列，且可以提前求值
  if (!subQuery.isCorrelated() && canEvaluate(subQuery)) {
    // 直接执行子查询，将结果作为常量替换
    // 例如: WHERE x IN (1, 2, 3) → WHERE x = 1 OR x = 2 OR x = 3
    return true;
  }
  return false;
}
```

## 5.9 MATCH_RECOGNIZE 的转换路径

`convertMatchRecognize()` 将 `MATCH_RECOGNIZE` 子句转换为 `LogicalMatch`：

```java
// SqlToRelConverter.java:2703
protected void convertMatchRecognize(Blackboard bb, SqlMatchRecognize mr) {
  // 1. 转换输入关系
  convertFrom(bb, mr.getTableRef());

  // 2. 转换 PARTITION BY
  List<RexNode> partitionKeys = ...;

  // 3. 转换 ORDER BY
  RelCollation orderKeys = ...;

  // 4. 转换 PATTERN
  // 5. 转换 MEASURES
  // 6. 转换 DEFINE

  // 7. 创建 LogicalMatch
  LogicalMatch match = LogicalMatch.create(root, ...);
  bb.setRoot(match, true);
}
```

---

## 本章小结

SqlToRelConverter 通过 Blackboard 工作区维护转换状态，按 FROM → WHERE → SELECT → ORDER 的顺序将 SqlNode AST 转换为 RelNode 树。ConvertletTable 提供了表达式转换的灵活分发机制。子查询处理是转换中最复杂的逻辑——EXISTS/IN 转换为 SemiJoin/AntiJoin，标量子查询转换为 Aggregate+Correlate。窗口函数产出 RexOver，后续由优化规则转换为 LogicalWindow。下一章将深入 RexNode 体系——关系代数的表达式语言。
