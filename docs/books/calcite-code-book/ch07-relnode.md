# 第7章：RelNode 体系 — 关系代数的算子世界

## 7.1 RelNode — 关系算子的基类

RelNode 是关系代数算子的统一接口。如果说 RexNode 描述"行上的计算"，那么 RelNode 描述"数据集的变换"。每个 RelNode 接收零个或多个输入数据集，产出一个输出数据集。

```java
// rel/RelNode.java
public interface RelNode extends RelOptNode, Cloneable {
  Convention getConvention();        // 物理约定
  RelNode getInput(int i);           // 第 i 个输入
  RelDataType getRowType();          // 输出行类型
  List<RelNode> getInputs();         // 所有输入
  RelTraitSet getTraitSet();         // 物理属性集合
  double estimateRowCount(RelMetadataQuery mq);  // 行数估计
  Set<CorrelationId> getVariablesSet();  // 关联变量集合
  RelNode accept(RelShuttle shuttle);     // 访问者模式
  void register(RelOptPlanner planner);   // 注册优化规则
}
```

### 7.1.1 继承体系的三层架构

Calcite 的 RelNode 体系采用三层架构：

```
第一层：抽象基类（定义语义）
  AbstractRelNode → SingleRel → Filter, Project, Sort, Aggregate, ...
                    BiRel → Join, Correlate, ...
                    SetOp → Union, Intersect, Minus

第二层：逻辑实现（Logical 系列，Convention=NONE）
  LogicalFilter, LogicalProject, LogicalJoin, LogicalAggregate, ...

第三层：物理实现（Enumerable/Bindable 等，Convention=具体约定）
  EnumerableCalc, EnumerableHashJoin, EnumerableAggregate, ...
```

这种分层让同一逻辑语义可以有多种物理实现，优化器在它们之间搜索最优方案。

### 7.1.2 核心抽象类

```
AbstractRelNode (rel/AbstractRelNode.java)
├── SingleRel (单输入算子)
│   ├── Filter (过滤)
│   ├── Project (投影)
│   ├── Sort (排序)
│   ├── Aggregate (聚合)
│   ├── Calc (Filter+Project 融合)
│   ├── Window (窗口函数)
│   ├── Exchange (数据分布)
│   ├── Sample (采样)
│   ├── Snapshot (时态快照)
│   └── TableScan (表扫描，无输入)
├── BiRel (双输入算子)
│   ├── Join (连接)
│   └── Correlate (关联连接)
├── SetOp (集合运算)
│   ├── Union
│   ├── Intersect
│   └── Minus
└── 其他
    ├── TableModify (DML)
    ├── TableFunctionScan (表函数)
    ├── Values (常量行)
    ├── Match (模式匹配)
    ├── Spool (缓存)
    └── RepeatUnion (递归 UNION)
```

## 7.2 Logical 算子层

Logical 算子是 SqlToRelConverter 的直接输出，表示逻辑语义但不绑定任何物理实现。它们的 Convention 都是 `NONE`。

### 7.2.1 逻辑算子完整列表

| 算子 | 父类 | 关键属性 |
|------|------|---------|
| `LogicalTableScan` | TableScan | table（RelOptTable） |
| `LogicalFilter` | Filter | condition（RexNode） |
| `LogicalProject` | Project | projects（List<RexNode>）, excludedFields |
| `LogicalJoin` | Join | condition, joinType, variablesSet |
| `LogicalAggregate` | Aggregate | groupSet, aggCalls |
| `LogicalSort` | Sort | collation, offset, fetch |
| `LogicalCalc` | Calc | program（RexProgram） |
| `LogicalWindow` | Window | groups, constants |
| `LogicalCorrelate` | Correlate | correlationId, requiredColumns, joinType |
| `LogicalUnion` | Union | all（是否保留重复） |
| `LogicalIntersect` | Intersect | all |
| `LogicalMinus` | Minus | all |
| `LogicalValues` | Values | tuples（List<List<RexLiteral>>） |
| `LogicalExchange` | Exchange | distribution |
| `LogicalTableModify` | TableModify | table, operation, source |
| `LogicalMatch` | Match | pattern, measures, definitions |
| `LogicalSnapshot` | Snapshot | period |
| `LogicalRepeatUnion` | RepeatUnion | seed, iterative, all, iterationLimit |

### 7.2.2 逻辑算子的特点

1. **Convention = NONE**：不绑定任何物理实现
2. **不可直接执行**：需要经过优化器转换为物理算子
3. **可被规则替换**：所有优化规则在逻辑层操作
4. **携带完整语义**：不丢失任何查询信息

## 7.3 Core 算子层详解

Core 算子（`rel/core/`，36 文件）定义了各算子的语义接口。以最关键的几个为例：

### 7.3.1 TableScan — 数据源

```java
// rel/core/TableScan.java
public abstract class TableScan extends AbstractRelNode implements Hintable {
  protected final RelOptTable table;  // 表元数据

  // 关键：TableScan 是叶子节点，无输入
  @Override public List<RelNode> getInputs() { return ImmutableList.of(); }
}
```

TableScan 是唯一没有输入的算子——它是数据管线的起点。`RelOptTable` 接口提供了表的元信息（行类型、统计信息等）。

### 7.3.2 Filter — 过滤

```java
// rel/core/Filter.java
public abstract class Filter extends SingleRel implements Hintable {
  protected final RexNode condition;  // 过滤条件

  // 唯一的子类约束：条件必须是 BOOLEAN 类型
  public abstract Filter copy(RelTraitSet traitSet, RelNode input, RexNode condition);
}
```

### 7.3.3 Project — 投影

```java
// rel/core/Project.java
public abstract class Project extends SingleRel implements Hintable {
  protected final List<? extends RexNode> projects;  // 投影表达式列表
  // projects 中的每个 RexNode 对应输出行的一列
}
```

### 7.3.4 Join — 连接

```java
// rel/core/Join.java
public abstract class Join extends BiRel implements Hintable {
  protected final RexNode condition;           // 连接条件
  protected final Set<CorrelationId> variablesSet;  // 关联变量
  protected final JoinRelType joinType;        // 连接类型: INNER, LEFT, RIGHT, FULL, SEMI, ANTI, ASOF

  public JoinInfo analyzeCondition() {
    // 分析连接条件是否为等值连接
    // 返回 JoinInfo（包含等值列对和非等值剩余条件）
  }
}
```

`JoinRelType` 枚举：

| 类型 | 含义 |
|------|------|
| INNER | 内连接 |
| LEFT | 左外连接 |
| RIGHT | 右外连接 |
| FULL | 全外连接 |
| SEMI | 半连接（EXISTS） |
| ANTI | 反连接（NOT EXISTS） |
| ASOF | 时间对齐连接 |

### 7.3.5 Aggregate — 聚合

```java
// rel/core/Aggregate.java
public abstract class Aggregate extends SingleRel implements Hintable {
  protected final ImmutableBitSet groupSet;       // GROUP BY 列集合
  protected final List<ImmutableBitSet> groupSets; // GROUPING SETS
  protected final List<AggregateCall> aggCalls;   // 聚合调用列表
}
```

`AggregateCall` 表示一个聚合函数调用：

```java
// rel/core/AggregateCall.java
public class AggregateCall {
  SqlAggFunction aggFunction;  // 聚合函数（SUM, COUNT, AVG, ...）
  boolean distinct;             // 是否 DISTINCT
  List<Integer> argList;        // 参数列索引
  int filterArg;                // FILTER(WHERE ...) 的列索引，-1 表示无
  RelDataType type;             // 返回类型
}
```

### 7.3.6 Calc — Filter+Project 的融合

```java
// rel/core/Calc.java
public abstract class Calc extends SingleRel implements Hintable {
  protected final RexProgram program;  // 融合的 Filter+Project 程序
}
```

Calc 是 Calcite 最精妙的优化之一——它将 Filter + Project 两个算子融合为一个，通过 RexProgram 同时表达过滤和投影。在执行层面，一行数据只需经过一次遍历即可完成过滤和投影。

### 7.3.7 Exchange — 数据分布描述

```java
// rel/core/Exchange.java
public abstract class Exchange extends SingleRel {
  protected final RelDistribution distribution;  // 数据分布
}
```

`RelDistribution` 描述数据的物理分布方式：

| 类型 | 含义 |
|------|------|
| ANY | 任意分布 |
| HASH_DISTRIBUTED | 按 Hash 分布 |
| RANGE_DISTRIBUTED | 按范围分布 |
| BROADCAST_DISTRIBUTED | 广播分布 |
| RANDOM_DISTRIBUTED | 随机分布 |
| SINGLETON | 单节点 |

Exchange 不执行数据移动——它只描述"我希望数据按此分布"。实际的数据重分布在执行引擎中完成。

## 7.4 RelTrait 与 Convention — 物理属性体系

### 7.4.1 RelTrait — 物理属性接口

```java
// plan/RelTrait.java
public interface RelTrait {
  RelTraitDef getTraitDef();        // 属性定义
  boolean satisfies(RelTrait trait); // 是否满足目标属性
  void register(RelOptPlanner planner); // 注册到规划器
}
```

`satisfies()` 是核心方法——它定义了属性之间的兼容性。例如，`HASH_DISTRIBUTED([$0])` 满足 `ANY` 分布（更具体的满足更一般的），但反过来不成立。

### 7.4.2 Convention — 物理约定

Convention 是最重要的 RelTrait，它定义了算子的执行方式：

```java
// plan/Convention.java
public interface Convention extends RelTrait {
  Convention NONE = new Impl("NONE", RelNode.class);

  String getName();                    // 约定名称
  Class getInterface();                // 算子必须实现的接口
  boolean canConvertConvention(Convention toConvention);  // 能否转换
  boolean useAbstractConvertersForConversion(...);
}
```

Calcite 内置的 Convention：

| Convention | 含义 | 产出 |
|-----------|------|------|
| `NONE` | 逻辑约定（未实现） | 不可执行 |
| `ENUMERABLE` | Java 枚举式执行 | `Bindable` 对象 |
| `BINDABLE` | 绑定式执行 | `Enumerable` 对象 |
| `INTERPRETABLE` | 解释执行 | 直接遍历执行 |

### 7.4.3 RelTraitSet — 属性集合

每个 RelNode 都有一个 `RelTraitSet`，包含其所有物理属性：

```java
RelTraitSet traits = relNode.getTraitSet();
// 通常包含:
// - Convention (如 ENUMERABLE)
// - RelCollation (排序属性，如 [$0 ASC, $2 DESC])
// - RelDistribution (分布属性，如 HASH[$1])
```

### 7.4.4 ConverterRule — 属性转换的桥梁

`ConverterRule` 将算子从一种 Convention 转换为另一种：

```java
// rel/convert/ConverterRule.java
public abstract class ConverterRule extends RelRule<ConverterRule.Config> {
  public abstract RelNode convert(RelNode rel);

  // 示例：LogicalFilter → EnumerableFilter
  // EnumerableCalcRule 将 LogicalCalc 转换为 EnumerableCalc
}
```

优化器通过 ConverterRule 在不同 Convention 之间转换，找到满足目标 Convention 的物理计划。

## 7.5 RelBuilder — 程序化构建关系表达式

`RelBuilder` 提供了流畅的 API 来程序化构建 RelNode 树，无需直接操作 SqlParser 和 SqlValidator：

```java
// tools/RelBuilder.java
public class RelBuilder {
  // 数据源
  RelBuilder scan(String... tableNames);

  // 变换
  RelBuilder filter(RexNode... predicates);
  RelBuilder project(RexNode... nodes);
  RelBuilder join(JoinRelType joinType, RexNode condition);
  RelBuilder aggregate(GroupKey groupKey, AggCall... aggCalls);
  RelBuilder sort(RexNode... nodes);
  RelBuilder limit(int offset, int fetch);
  RelBuilder distinct();

  // 栈操作
  RelBuilder push(RelNode node);
  RelNode build();
  RelBuilder union(boolean all, int n);
}
```

使用示例：

```java
RelBuilder builder = RelBuilder.create(config);
RelNode rel = builder
    .scan("EMP")
    .filter(
        builder.call(SqlStdOperatorTable.GREATER_THAN,
            builder.field("SAL"),
            builder.literal(1000)))
    .project(
        builder.field("ENAME"),
        builder.call(SqlStdOperatorTable.PLUS,
            builder.field("SAL"),
            builder.literal(100)))
    .build();
// 等价于: SELECT ENAME, SAL + 100 FROM EMP WHERE SAL > 1000
```

RelBuilder 在优化规则中被广泛使用——规则通常通过 RelBuilder 构建新的 RelNode 树，而非直接实例化具体类。

## 7.6 MutableRel — 可变关系表达式的改写框架

优化规则需要遍历和改写 RelNode 树。但 RelNode 是不可变的——每次改写都需要创建新对象。`MutableRel`（`rel/mutable/`，31 文件）提供了一个可变的中间表示，用于高效的树改写：

```
MutableRel (abstract)
├── MutableFilter
├── MutableProject
├── MutableJoin
├── MutableAggregate
├── MutableSort
├── MutableCalc
├── ...
```

MutableRel 主要用于 `SubstitutionVisitor`（物化视图匹配）中，因为它需要频繁地修改树结构。

## 7.7 RelNode 的注册机制

每个 RelNode 子类可以通过 `register()` 方法向优化器注册默认规则：

```java
// AbstractRelNode.java
@Override public void register(RelOptPlanner planner) {
  // 默认实现：不做任何事
  // 子类可以覆盖，注册特定规则
}

// LogicalJoin 的注册（示例）
public static void register(RelOptPlanner planner) {
  planner.addRule(FilterJoinRule.FILTER_ON_JOIN);
  planner.addRule(ProjectJoinTransposeRule.INSTANCE);
  planner.addRule(JoinPushExpressionsRule.INSTANCE);
  // ...
}
```

## 7.8 从 RelNode 树理解查询计划

一个完整的 SQL 查询对应的 RelNode 树：

```sql
SELECT d.dept_name, AVG(e.salary)
FROM emp e JOIN dept d ON e.dept_id = d.id
WHERE e.salary > 1000
GROUP BY d.dept_name
HAVING AVG(e.salary) > 5000
ORDER BY d.dept_name
```

转换后的 RelNode 树（简化）：

```
LogicalSort(collation=[$0 ASC])
  LogicalProject(dept_name=[$0], avg_salary=[$1])
    LogicalFilter(condition=[$1 > 5000])
      LogicalAggregate(group=[{0}], aggCalls=[AVG($5)])
        LogicalProject(dept_name=[$8], salary=[$5])
          LogicalJoin(condition=[$7 = $9], joinType=INNER)
            LogicalTableScan(table=[emp])
            LogicalTableScan(table=[dept])
```

优化后（Enumerable Convention）：

```
EnumerableSort(collation=[$0 ASC])
  EnumerableCalc(program: ...HAVING + PROJECT)
    EnumerableAggregate(group=[{0}], aggCalls=[AVG($5)])
      EnumerableCalc(program: ...PROJECT)
        EnumerableHashJoin(condition=[$7 = $9], joinType=INNER)
          EnumerableCalc(program: ...FILTER salary > 1000)
            EnumerableTableScan(table=[emp])
          EnumerableTableScan(table=[dept])
```

---

## 本章小结

RelNode 体系采用三层架构：Core 层定义语义接口，Logical 层提供逻辑实现，Enumerable/Bindable 层提供物理实现。Convention 和 RelTrait 描述物理属性，ConverterRule 在不同 Convention 之间转换。Calc 算子通过 RexProgram 融合 Filter+Project。RelBuilder 提供流畅的 API 程序化构建 RelNode。理解这三层架构是理解 Calcite 优化器的基础——下一章将深入优化器框架。
