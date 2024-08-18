# 第8章：优化器框架 — RelOptPlanner 的设计

## 8.1 优化器的本质：搜索问题与代价模型

查询优化的本质是一个**搜索问题**：在所有等价的关系表达式树中，找到代价最小的一个。这个搜索空间的大小是指数级的——N 个表的 Join 有 (2N-1)!! 种连接顺序，每个 Join 又有多种物理实现。

优化器需要解决三个核心问题：

1. **搜索策略**：如何在指数级空间中高效搜索？自顶向下还是自底向上？
2. **代价模型**：如何评估一个计划的代价？行数、CPU、IO 如何权衡？
3. **规则匹配**：如何高效地发现哪些规则可以应用于当前的计划子树？

Calcite 的优化器框架（`plan/` 包，88 文件）定义了这些问题的抽象接口，而 VolcanoPlanner 和 HepPlanner 提供了两种具体的搜索策略。

## 8.2 RelOptPlanner 接口

```java
// plan/RelOptPlanner.java
public interface RelOptPlanner {
  // 规则管理
  boolean addRule(RelOptRule rule);
  boolean removeRule(RelOptRule rule);
  List<RelOptRule> getRules();
  void clear();

  // 查询优化
  void setRoot(RelNode rel);
  RelNode findBestExp();
  RelNode changeTraits(RelNode rel, RelTraitSet traitSet);

  // 代价模型
  RelOptCostFactory getCostFactory();

  // 元数据
  RelMetadataQuery getMetadataQuery();

  // 物化视图与 Lattice
  void addMaterialization(RelOptMaterialization materialization);
  void addLattice(RelOptLattice lattice);

  // 选择委托
  RelOptPlanner chooseDelegate();
}
```

`chooseDelegate()` 是一个有趣的方法——它让优化器有机会在优化开始前选择一个"委托者"。VolcanoPlanner 返回自身（直接执行优化），而一些包装类可能返回不同的实现。

## 8.3 RelOptRule 体系

### 8.3.1 RelOptRule — 规则基类

```java
// plan/RelOptRule.java
public abstract class RelOptRule {
  protected final String description;                    // 规则描述
  public final List<RelOptRuleOperand> operands;         // 操作数匹配树

  // 核心：规则匹配后执行的动作
  public abstract void onMatch(RelOptRuleCall call);

  // 规则是否匹配（默认基于操作数树匹配，子类可覆盖添加额外条件）
  public boolean matches(RelOptRuleCall call) { return true; }
}
```

### 8.3.2 RelOptRuleOperand — 匹配树

每个规则通过一棵**操作数匹配树**声明它能匹配的 RelNode 子树模式：

```java
// plan/RelOptRuleOperand.java
public class RelOptRuleOperand {
  private final Class<? extends RelNode> clazz;     // 要匹配的 RelNode 类
  private final @Nullable RelTrait trait;           // 要求的 Trait
  private final Predicate<RelNode> predicate;       // 额外谓词
  private final ImmutableList<RelOptRuleOperand> children;  // 子操作数
  public final RelOptRuleOperandChildPolicy childPolicy;    // 子节点匹配策略
}
```

匹配策略 `RelOptRuleOperandChildPolicy`：

| 策略 | 含义 | 示例 |
|------|------|------|
| `ANY` | 子节点可以是任意顺序和数量 | 用于通配匹配 |
| `SOME` | 子节点必须按顺序精确匹配 | `Join(Filter, Any)` |
| `NONE` | 不关心子节点 | 叶子匹配 |
| `UNORDERED` | 子节点必须全部匹配，但顺序无关 | `Union(Filter, Filter)` |

### 8.3.3 匹配树示例

以 `FilterJoinRule.FilterIntoJoinRule` 为例，它将 Filter 下推到 Join 中：

```
匹配模式:
Filter
├── Join
│   ├── any (左输入)
│   └── any (右输入)

声明方式:
operand(Filter.class,
    some(operand(Join.class, any())))

含义: 匹配一个 Filter，其输入是 Join，Join 的两个输入任意
```

当优化器发现一个 `Filter` 算子的输入是 `Join` 时，这条规则被触发。`onMatch()` 方法中：

```java
@Override public void onMatch(RelOptRuleCall call) {
  Filter filter = call.rel(0);  // 匹配树第 0 个节点
  Join join = call.rel(1);       // 匹配树第 1 个节点
  // 将 filter 的条件下推到 join 中
  // ...
}
```

### 8.3.4 RelOptRuleCall — 规则调用上下文

当匹配成功时，优化器创建 `RelOptRuleCall`，携带匹配的 RelNode 数组和优化器引用：

```java
// plan/RelOptRuleCall.java
public abstract class RelOptRuleCall {
  public final RelOptRule rule;       // 触发的规则
  public final RelNode[] rels;        // 匹配的 RelNode 数组
  private final RelOptPlanner planner; // 优化器引用

  // 注册新生成的 RelNode（替代匹配的子树）
  public abstract void transformTo(RelNode rel, Map<RelNode, RelNode> equiv);

  // 便捷方法
  public <R extends RelNode> R rel(int pos) { return (R) rels[pos]; }
}
```

`transformTo()` 是规则与优化器的核心交互——规则生成新的 RelNode，通过此方法注册到优化器。优化器将新节点纳入等价类，继续搜索。

## 8.4 RelRule — 配置化规则

Calcite 1.22+ 引入了 `RelRule`，通过 Immutables 风格的 Config 接口定义规则，避免大量样板代码：

```java
// plan/RelRule.java
public abstract class RelRule<C extends RelRule.Config> extends RelOptRule {
  public final C config;

  public interface Config extends RelRule.Config {
    Config withOperandFor(Class<? extends RelNode>... operandClasses);
    RelOptRule toRule();
  }
}
```

对比传统方式和 RelRule 方式：

```java
// 传统方式：显式构建操作数树
public class MyFilterProjectRule extends RelOptRule {
  public static final MyFilterProjectRule INSTANCE = new MyFilterProjectRule();

  private MyFilterProjectRule() {
    super(operand(Filter.class, some(operand(Project.class, any()))));
  }

  @Override public void onMatch(RelOptRuleCall call) { ... }
}

// RelRule 方式：配置化
public class MyFilterProjectRule extends RelRule<MyFilterProjectRule.Config> {
  @Value.Immutable
  public interface Config extends RelRule.Config {
    @Override default MyFilterProjectRule toRule() { return new MyFilterProjectRule(this); }
  }

  protected MyFilterProjectRule(Config config) {
    super(config.withOperandFor(Filter.class, Project.class));
  }

  @Override public void onMatch(RelOptRuleCall call) { ... }
}
```

CoreRules 中所有新规则都使用 RelRule 风格。

## 8.5 规则的分类

Calcite 的规则按功能分为四类：

### 8.5.1 TransformationRule — 逻辑变换

最常见的规则类型，将一个逻辑计划变换为等价的另一个：

```java
// rel/rules/TransformationRule.java
public interface TransformationRule {
  // 标记接口，无方法
}
```

示例：
- `FilterProjectTransposeRule`：Filter 和 Project 交换位置
- `ProjectJoinTransposeRule`：Project 下推过 Join
- `AggregateMergeRule`：合并嵌套的 Aggregate

### 8.5.2 ConverterRule — Convention 转换

将 RelNode 从一种 Convention 转换为另一种：

```java
// rel/convert/ConverterRule.java
public abstract class ConverterRule extends RelRule<ConverterRule.Config> {
  public abstract RelNode convert(RelNode rel);

  public interface Config extends RelRule.Config {
    Convention inConvention();     // 源 Convention
    Convention outConvention();    // 目标 Convention
  }
}
```

示例：
- `EnumerableCalcRule`：`LogicalCalc` → `EnumerableCalc`
- `EnumerableHashJoinRule`：`LogicalJoin` → `EnumerableHashJoin`
- `EnumerableAggregateRule`：`LogicalAggregate` → `EnumerableAggregate`

### 8.5.3 SubstitutionRule — 物化视图替换

将查询子树替换为物化视图扫描：

```java
// rel/rules/SubstitutionRule.java
public interface SubstitutionRule {
  // 标记接口
  // 实现此接口的规则产出的 RelNode 被视为等价替换，而非新等价类
}
```

### 8.5.4 CoreRules — 规则注册中心

`CoreRules`（997 行）是 Calcite 内置规则的注册中心，包含 100+ 条预定义规则：

```
// 聚合规则族
AGGREGATE_PROJECT_MERGE, AGGREGATE_MERGE, AGGREGATE_REMOVE,
AGGREGATE_REDUCE_FUNCTIONS, AGGREGATE_FILTER_TRANSPOSE,
AGGREGATE_JOIN_TRANSPOSE, AGGREGATE_UNION_TRANSPOSE,
AGGREGATE_MIN_MAX_TO_LIMIT, ...

// Filter 规则族
FILTER_INTO_JOIN, FILTER_MERGE, FILTER_PROJECT_TRANSPOSE,
FILTER_AGGREGATE_TRANSPOSE, FILTER_SORT_TRANSPOSE,
FILTER_SET_OP_TRANSPOSE, FILTER_WINDOW_TRANSPOSE,
FILTER_SCAN, FILTER_CORRELATE, ...

// Project 规则族
PROJECT_MERGE, PROJECT_FILTER_TRANSPOSE,
PROJECT_JOIN_TRANSPOSE, PROJECT_CORRELATE_TRANSPOSE,
PROJECT_SET_OP_TRANSPOSE, PROJECT_WINDOW_TRANSPOSE,
PROJECT_REMOVE, PROJECT_TABLE_SCAN, ...

// Join 规则族
JOIN_PROJECT_BOTH_TRANSPOSE, JOIN_PROJECT_LEFT_TRANSPOSE,
JOIN_PROJECT_RIGHT_TRANSPOSE, JOIN_COMMUTE,
JOIN_LEFT_UNION_TRANSPOSE, JOIN_RIGHT_UNION_TRANSPOSE, ...

// Sort 规则族
SORT_JOIN_TRANSPOSE, SORT_PROJECT_TRANSPOSE,
SORT_UNION_TRANSPOSE, SORT_REMOVE,
SORT_REMOVE_CONSTANT_KEYS, SORT_REMOVE_REDUNDANT, ...

// Calc 规则族
CALC_MERGE, CALC_REMOVE, CALC_SPLIT, CALC_TO_WINDOW, ...

// 子查询规则
SUB_QUERY_REMOVE, ...

// Union/Intersect/Minus 规则族
UNION_MERGE, UNION_REMOVE, UNION_PULL_UP_CONSTANTS,
INTERSECT_MERGE, INTERSECT_REMOVE, INTERSECT_REORDER,
MINUS_MERGE, MINUS_REMOVE, ...
```

## 8.6 RelOptCost — 代价模型

### 8.6.1 RelOptCost 接口

```java
// plan/RelOptCost.java
public interface RelOptCost {
  double getRows();     // 结果行数
  double getCpu();      // CPU 开销
  double getIo();       // IO 开销

  boolean isInfinite();  // 是否无穷大
  boolean isZero();      // 是否为零
  boolean isLt(RelOptCost other);  // 是否小于 other
  boolean isLe(RelOptCost other);  // 是否小于等于

  RelOptCost plus(RelOptCost other);     // 相加
  RelOptCost minus(RelOptCost other);    // 相减
  RelOptCost multiplyBy(double factor);  // 乘以因子
  double divideBy(RelOptCost cost);      // 除以
}
```

### 8.6.2 VolcanoCost — 默认代价实现

```java
// plan/volcano/VolcanoCost.java
class VolcanoCost implements RelOptCost {
  final double cpu;
  final double io;
  final double rowCount;

  @Override public boolean isLt(RelOptCost other) {
    return cpu + io + rowCount < other.getCpu() + other.getIo() + other.getRows();
  }
}
```

默认代价模型非常简单——**三个维度直接求和比较**。这意味着行数、CPU 和 IO 的权重相同。生产级系统通常需要自定义代价模型，赋予不同权重或添加更多维度（如内存、网络）。

### 8.6.3 RelOptCostImpl — 简单代价

`RelOptCostImpl` 提供了一个基于行数的简单代价模型，主要用于 HepPlanner（启发式优化器不依赖代价比较）：

```java
// plan/RelOptCostImpl.java
public class RelOptCostImpl implements RelOptCost {
  private final double rowCount;
  // CPU 和 IO 始终为 0
}
```

## 8.7 RelOptCluster — 优化上下文

`RelOptCluster` 是优化过程的上下文对象，每个 RelNode 都持有一个引用：

```java
// plan/RelOptCluster.java
public class RelOptCluster {
  private final RelOptPlanner planner;        // 优化器
  private final RexBuilder rexBuilder;        // 表达式构建器
  private final RelDataTypeFactory typeFactory; // 类型工厂
  private RelMetadataQuery metadataQuery;     // 元数据查询

  // 全局唯一 ID 生成
  private int nextId;
}
```

RelOptCluster 是 RelNode 树的"胶水"——它确保树中的所有节点共享同一个优化器、类型工厂和元数据查询。

## 8.8 优化管线的完整流程

回顾 `Programs.standard()`，Calcite 默认的优化管线按顺序执行以下子程序：

```
1. subQuery(metadataProvider)   — 子查询消除
   - 将 RexSubQuery 替换为 SemiJoin/AntiJoin/Correlate

2. DecorrelateProgram()         — 解关联
   - 将关联子查询转换为非关联的 Join

3. measure(metadataProvider)    — MEASURE 处理
   - 处理 SQL:2023 的 MEASURE 类型

4. TrimFieldsProgram()          — 字段裁剪
   - 移除中间结果中不需要的字段

5. program1 (主优化)            — VolcanoPlanner.findBestExp()
   - 注册规则、设置根节点、搜索最优计划
   - 包含物化视图和 Lattice 注册

6. calc(metadataProvider)       — 第二遍优化
   - 引入 EnumerableCalc（Filter+Project 融合算子）
   - 基于 HepPlanner 的轻量级优化
```

两遍优化（第5步和第6步）是一个重要的设计决策：第一遍做主要的逻辑优化和物理选择，第二遍做轻量的物理调整（如 Calc 融合）。这样可以避免第一遍优化空间过大——Calc 融合在逻辑优化阶段是不必要的。

## 8.9 自定义代价模型

要自定义代价模型，需要三步：

1. 实现 `RelOptCost` 接口
2. 实现 `RelOptCostFactory` 接口
3. 在创建 Planner 时传入自定义 CostFactory

```java
// 自定义代价模型示例
public class MyCost implements RelOptCost {
  final double cpu;
  final double io;
  final double rowCount;
  final double memory;  // 新增维度：内存

  @Override public boolean isLt(RelOptCost other) {
    MyCost o = (MyCost) other;
    // 自定义权重：CPU 权重高，行数次之，IO 和内存较低
    return (cpu * 10 + rowCount * 5 + io * 2 + memory)
         < (o.cpu * 10 + o.rowCount * 5 + o.io * 2 + o.memory);
  }
}
```

## 8.10 优化器的选择策略

| 维度 | HepPlanner | VolcanoPlanner |
|------|-----------|----------------|
| 搜索方式 | 顺序应用规则 | 代价导向搜索 |
| 计划空间 | 单一计划 | 等价类（多个等价计划） |
| 代价模型 | 不依赖（只用规则顺序） | 依赖代价比较 |
| 搜索完整性 | 不保证最优 | 不保证最优（但更接近） |
| 适用场景 | 确定性优化、规则间有依赖 | 代价敏感的物理选择 |
| 复杂度 | O(rules × nodes) | 指数级（但有剪枝） |

**实践建议**：

1. 逻辑优化（如谓词下推、投影下推）用 HepPlanner 或在 VolcanoPlanner 的第一遍中处理
2. 物理选择（Join 算法选择、Convention 转换）必须用 VolcanoPlanner
3. 规则间有依赖关系时（规则A的输出是规则B的输入），用 HepPlanner 的有序程序
4. 需要全局最优时，用 VolcanoPlanner + 自定义代价模型

---

## 本章小结

Calcite 的优化器框架以 RelOptPlanner 为核心，RelOptRule 定义变换规则，RelOptRuleOperand 声明匹配模式，RelOptCost 评估计划代价。规则分为 TransformationRule（逻辑变换）、ConverterRule（Convention 转换）和 SubstitutionRule（物化视图替换）三类。CoreRules 注册了 100+ 条内置规则。默认优化管线通过 Programs.standard() 按顺序执行子查询消除、解关联、字段裁剪、主优化和 Calc 融合五个阶段。下一章将深入 VolcanoPlanner——Calcite 最精妙的搜索引擎。
