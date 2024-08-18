# 第9章：Volcano Planner — 自顶向下的搜索引擎

## 9.1 VolcanoPlanner 的核心数据结构

VolcanoPlanner 是 Calcite 最复杂的组件，它实现了 Volcano/Cascades 优化模型。理解它的关键是三个核心数据结构：

```
RelSet（等价类）
  → 语义等价的所有 RelNode
  → 按 Trait 划分为多个 RelSubset

RelSubset（等价子集）
  → RelSet 中具有相同 Trait 的 RelNode 子集
  → 记录此 Trait 下的最优计划和代价

VolcanoRuleMatch（规则匹配）
  → 一条规则与一组匹配的 RelNode 的绑定
  → 按重要性排序，决定触发顺序
```

### 9.1.1 RelSet — 等价类

```java
// plan/volcano/RelSet.java
class RelSet {
  final int id;
  final List<RelNode> rels = new ArrayList<>();          // 所有等价的 RelNode
  final List<RelSubset> subsets = new ArrayList<>();     // 按 Trait 划分的子集
  final List<RelNode> parents = new ArrayList<>();       // 引用此集合的父 RelNode
  @MonotonicNonNull RelSet equivalentSet;                // 合并后的等价集

  final Set<CorrelationId> variablesPropagated;          // 传播的关联变量
  final Set<CorrelationId> variablesUsed;                // 使用的关联变量
}
```

**RelSet 是什么？** 它是一组语义等价的 RelNode。例如：

```
RelSet#3:
  - LogicalProject(name=[$1])        ← 原始逻辑算子
  - EnumerableCalc(program=...)       ← Enumerable 物理算子
  - BindableProject(name=[$1])        ← Bindable 物理算子

这些算子都产出相同的结果，所以属于同一等价类。
```

当规则产出新的 RelNode 时，VolcanoPlanner 判断它与哪个已有 RelSet 等价，并将其加入该 RelSet。如果两个 RelSet 被发现等价，则合并（通过 `equivalentSet` 字段链接）。

### 9.1.2 RelSubset — 等价子集

```java
// plan/volcano/RelSubset.java
class RelSubset extends AbstractRelNode {
  RelSet set;                    // 所属的 RelSet
  RelTraitSet traitSet;          // 此子集的 Trait（Convention + Collation + Distribution）
  @Nullable RelOptCost bestCost; // 此 Trait 下的最优代价
  @Nullable RelNode best;        // 此 Trait 下的最优 RelNode
}
```

一个 RelSet 按 Trait 划分为多个 RelSubset：

```
RelSet#3:
  Subset[CONVENTION=NONE, COLLATION=[]]:
    - LogicalProject(name=[$1])
    best: LogicalProject, cost=1.0

  Subset[CONVENTION=ENUMERABLE, COLLATION=[]]:
    - EnumerableCalc(program=...)
    best: EnumerableCalc, cost=2.0

  Subset[CONVENTION=ENUMERABLE, COLLATION=[$1 ASC]]:
    - EnumerableSort(EnumerableCalc)
    best: EnumerableSort, cost=5.0
```

**RelSubset 本身也是一个 RelNode**——这意味着它可以作为其他 RelNode 的输入。这非常关键：优化器通过 RelSubset 引用等价类，而非具体的 RelNode，从而实现延迟绑定。

### 9.1.3 代价计算

```java
// RelSubset.computeBestCost()
private void computeBestCost(RelOptCluster cluster, RelOptPlanner planner) {
  bestCost = planner.getCostFactory().makeInfiniteCost();
  for (RelNode rel : getRels()) {
    RelOptCost cost = planner.getCost(rel, mq);
    if (cost != null && cost.isLt(bestCost)) {
      bestCost = cost;
      best = rel;
    }
  }
}
```

代价从下到上传播：叶子节点（TableScan）的代价由元数据估算，中间节点的代价 = 自身代价 + 所有输入的 bestCost。

## 9.2 两种搜索策略

### 9.2.1 IterativeRuleDriver — 传统迭代式

```java
// plan/volcano/IterativeRuleDriver.java
class IterativeRuleDriver implements RuleDriver {
  @Override public void drive() {
    while (true) {
      VolcanoRuleMatch match = ruleQueue.popMatch();  // 弹出优先级最高的匹配
      if (match == null) {
        return;  // 无更多匹配，优化完成
      }
      assert match.getRule().matches(match);
      match.onMatch();  // 执行规则
    }
  }
}
```

这是传统的 Volcano 搜索方式——基于重要性（Importance）的贪心调度：

1. 每当新 RelNode 注册时，计算所有可能触发的规则匹配
2. 将匹配按重要性排序放入 RuleQueue
3. 循环弹出最高优先级的匹配并执行
4. 执行可能产生新 RelNode，回到步骤1

**重要性计算**：一个匹配的重要性 = 规则的重要性 × 匹配节点所在 RelSubset 的重要性。越靠近根节点、代价越低的 RelSubset 重要性越高。

### 9.2.2 TopDownRuleDriver — 自顶向下

```java
// plan/volcano/TopDownRuleDriver.java
class TopDownRuleDriver implements RuleDriver {
  private final Stack<Task> tasks = new Stack<>();

  @Override public void drive() {
    // 从根节点的 OptimizeGroup 任务开始
    tasks.push(new OptimizeGroup(planner.root, planner.infCost));
    exploreMaterializationRoots();

    while (!tasks.isEmpty()) {
      Task task = tasks.pop();
      task.perform();  // 执行任务，可能调度新任务
    }
  }
}
```

TopDownRuleDriver 更接近 Cascades 模型，使用任务栈（Task Stack）驱动：

| 任务类型 | 职责 |
|---------|------|
| `OptimizeGroup` | 优化一个 RelSubset：找到最低代价的实现 |
| `OptimizeInput` | 优化某个 RelNode 的第 i 个输入 |
| `ExploreGroup` | 探索一个 RelSubset：应用 TransformationRule 产生逻辑等价 |
| `ApplyRule` | 应用一条规则，产生新 RelNode |
| `ComputeBestCost` | 计算 RelSubset 的最优代价 |

执行流程：

```
1. OptimizeGroup(root)
   → 遍历 root RelSubset 中的所有 RelNode
   → 对每个 RelNode，递归优化其输入（OptimizeInput）
   → 应用 ImplementationRule（ConverterRule）产生物理实现
   → 计算 bestCost

2. ExploreGroup(subset)
   → 对 subset 中的 RelNode 应用 TransformationRule
   → 新产生的 RelNode 注册到等价类
   → 可能触发新的 ExploreGroup

3. ApplyRule(match)
   → 执行规则的 onMatch()
   → 新 RelNode 通过 transformTo() 注册
```

### 9.2.3 两种策略的对比

| 维度 | IterativeRuleDriver | TopDownRuleDriver |
|------|---------------------|-------------------|
| 搜索方向 | 自底向上（由匹配驱动） | 自顶向下（从根开始） |
| 剪枝 | 基于重要性排序 | 基于代价阈值（更有力） |
| 探索范围 | 可能过度探索低价值等价类 | 按需探索（需要时才深入） |
| 实现复杂度 | 简单 | 复杂（任务栈管理） |
| 成熟度 | 成熟，默认使用 | 较新，通过 `topDownOpt` 配置开启 |

## 9.3 规则驱动循环：注册 → 匹配 → 触发 → 生成新算子

VolcanoPlanner 的核心循环可以用一张图概括：

```
注册 RelNode
  ↓
registerImpl(rel, set)
  ↓
判断等价 → 加入 RelSet → 划分 RelSubset
  ↓
发现新规则匹配 → 创建 VolcanoRuleMatch → 加入 RuleQueue
  ↓
popMatch() → onMatch()
  ↓
规则产出新 RelNode → transformTo()
  ↓
注册新 RelNode → 回到步骤1
```

### 9.3.1 注册过程

```java
// VolcanoPlanner.registerImpl() 简化
private RelSubset registerImpl(RelNode rel, @Nullable RelSet set) {
  // 1. 检查是否已注册
  if (isRegistered(rel)) { return getSubsetNonNull(rel); }

  // 2. 确定或创建 RelSet
  if (set == null) { set = new RelSet(nextSetId++, ...); }

  // 3. 确定或创建 RelSubset
  RelSubset subset = set.getSubset(rel.getTraitSet());
  if (subset == null) {
    subset = new RelSubset(cluster, set, rel.getTraitSet(), true);
    set.addSubset(subset);
  }

  // 4. 将 RelNode 加入 RelSet 和 RelSubset
  set.addRel(rel);
  subset.addRel(rel);

  // 5. 递归注册输入
  for (RelNode input : rel.getInputs()) {
    registerImpl(input, null);
  }

  // 6. 发现并注册新的规则匹配
  for (RelOptRule rule : allRules) {
    if (rule.matches(rel)) {
      ruleQueue.addMatch(new VolcanoRuleMatch(rule, rel));
    }
  }

  return subset;
}
```

### 9.3.2 匹配发现

规则匹配基于**操作数树**递归匹配。当新 RelNode 注册时，优化器检查所有规则的操作数树：

1. 新 RelNode 是否匹配某规则的根操作数？
2. 如果匹配，其子节点是否匹配子操作数？
3. 完全匹配则创建 VolcanoRuleMatch

### 9.3.3 transformTo — 注册新计划

规则的 `onMatch()` 方法通过 `transformTo()` 注册新 RelNode：

```java
// 在规则内部
@Override public void onMatch(RelOptRuleCall call) {
  Filter filter = call.rel(0);
  Project project = call.rel(1);

  // 交换 Filter 和 Project
  RelNode newFilter = LogicalFilter.create(project.getInput(), filter.getCondition());
  RelNode newProject = LogicalProject.create(newFilter, project.getProjects(), ...);

  call.transformTo(newProject);  // 注册新计划
}
```

`transformTo()` 内部调用 `planner.register()`，将新 RelNode 纳入等价类，触发新的规则匹配。

## 9.4 代价传播与剪枝

### 9.4.1 代价传播

代价从叶子节点向上传播：

```
TableScan(emp)        cost = {rows=1000, cpu=1000, io=100}
  ↓
Filter(sal > 1000)    cost = {rows=300, cpu=1300, io=100}  ← 自身 cpu=300 + 输入 cost
  ↓
Project(name, sal)    cost = {rows=300, cpu=1600, io=100}  ← 自身 cpu=300 + 输入 cost
```

`planner.getCost(rel, mq)` 的计算逻辑：

```java
// VolcanoPlanner.getCost() 简化
public RelOptCost getCost(RelNode rel, RelMetadataQuery mq) {
  // 1. 如果 RelNode 有自定义代价计算，使用之
  // 2. 否则：自身代价 + 所有输入的 bestCost
  RelOptCost selfCost = mq.getNonCumulativeCost(rel);
  RelOptCost inputCost = ... // 所有输入 RelSubset 的 bestCost 之和
  return selfCost.plus(inputCost);
}
```

### 9.4.2 剪枝

VolcanoPlanner 在两种情况下剪枝：

1. **IterativeRuleDriver**：通过重要性排序——低重要性的匹配可能永远不被弹出
2. **TopDownRuleDriver**：通过代价阈值——如果一个 RelSubset 的代价已经高于当前最优，不再深入优化其输入

TopDown 的剪枝更有效，因为它从根节点开始，可以利用已知的代价上界剪掉整棵子树。

## 9.5 Convention 转换机制

VolcanoPlanner 的一个核心功能是在不同 Convention 之间转换。这通过 `ConverterRule` 和 `AbstractConverter` 实现。

### 9.5.1 ensureRootConverters

```java
// VolcanoPlanner.java
void ensureRootConverters() {
  // 为根 RelSet 的每个 Subset 创建到根 Trait 的 Converter
  for (RelSubset subset : root.set.subsets) {
    if (root.getTraitSet().difference(subset.getTraitSet()).size() == 1) {
      register(new AbstractConverter(subset, ..., root.getTraitSet()), root);
    }
  }
}
```

这确保优化器会尝试将所有等价子集转换到根要求的 Trait——否则某些物理实现可能永远不会被发现。

### 9.5.2 ConverterRule 的匹配

ConverterRule 的操作数通常指定输入 Convention：

```java
// EnumerableCalcRule 匹配 Convention=NONE 的 Calc
operand(Calc.class, convention(Convention.NONE), any())
```

当匹配到 LogicalCalc 时，ConverterRule 产出 EnumerableCalc，它属于 Convention=ENUMERABLE 的子集。优化器随后可以比较两个 Subset 的代价。

## 9.6 物化视图匹配

VolcanoPlanner 通过 `SubstitutionVisitor` 和物化视图规则实现物化视图匹配：

```java
// VolcanoPlanner.registerMaterializations()
protected void registerMaterializations() {
  // 1. 注册物化视图的查询定义为额外的根
  for (RelOptMaterialization materialization : materializations) {
    // 注册物化视图表
    // 注册物化视图查询的 RelNode 树
  }

  // 2. 注册 Lattice
  for (RelOptLattice lattice : latticeByName.values()) {
    // 自动推荐和注册 Lattice 对应的物化视图
  }
}
```

物化视图匹配的核心算法在 `SubstitutionVisitor`（2438 行）中，它使用 `MutableRel` 框架比较查询子树和物化视图定义的结构相似性。

## 9.7 从源码跟踪一次 Volcano 优化过程

输入：`SELECT e.name FROM emp e WHERE e.sal > 1000`

初始逻辑计划：
```
LogicalProject(name=[$1])
  LogicalFilter(condition=[$5 > 1000])
    LogicalTableScan(table=[emp])
```

优化过程：

```
1. setRoot() → 注册三个 RelNode
   RelSet#0: [TableScan(emp)] → Subset[NONE]
   RelSet#1: [Filter($5 > 1000)] → Subset[NONE]
   RelSet#2: [Project($1)] → Subset[NONE]

2. 规则匹配：
   - EnumerableTableScanRule: TableScan → EnumerableTableScan
   - FilterToCalcRule: Filter → LogicalCalc
   - EnumerableCalcRule: LogicalCalc → EnumerableCalc
   - ProjectToCalcRule: Project → LogicalCalc
   - FilterProjectTransposeRule: Filter+Project → Project+Filter

3. IterativeRuleDriver 循环：
   a) EnumerableTableScanRule 触发
      → EnumerableTableScan 注册到 RelSet#0, Subset[ENUMERABLE]
   b) FilterToCalcRule 触发
      → LogicalCalc(filter=$5>1000) 注册到 RelSet#1
   c) EnumerableCalcRule 触发
      → EnumerableCalc(program=...) 注册到 RelSet#1, Subset[ENUMERABLE]
   d) ProjectToCalcRule 触发
      → LogicalCalc(project=$1) 注册到 RelSet#2
   e) EnumerableCalcRule 触发
      → EnumerableCalc(program=...) 注册到 RelSet#2, Subset[ENUMERABLE]

4. 代价计算（自底向上）：
   Subset[ENUMERABLE]#0: best=EnumerableTableScan, cost={1000,1000,100}
   Subset[ENUMERABLE]#1: best=EnumerableCalc(Filter), cost={300,1300,100}
   Subset[ENUMERABLE]#2: best=EnumerableCalc(Project+Filter), cost={300,1600,100}

5. findBestExp() → root.buildCheapestPlan()
   → EnumerableCalc(Project, program: {condition=$5>1000, projects=[$1]})
     EnumerableTableScan(table=[emp])
```

---

## 本章小结

VolcanoPlanner 通过 RelSet（等价类）和 RelSubset（按 Trait 划分的等价子集）组织搜索空间。IterativeRuleDriver 按重要性排序触发规则匹配，TopDownRuleDriver 从根节点自顶向下按需探索。规则驱动循环是"注册→匹配→触发→生成→注册"的闭循环。代价从叶子向上传播，TopDown 策略可以利用代价上界剪枝。Convention 转换通过 ConverterRule 和 AbstractConverter 机制实现。下一章将介绍更简单的 HepPlanner。
