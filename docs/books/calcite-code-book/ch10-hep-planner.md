# 第10章：Hep Planner — 启发式顺序优化器

## 10.1 HepPlanner 的设计哲学

HepPlanner 的设计哲学是**简单、确定、可预测**。与 VolcanoPlanner 的全局搜索不同，HepPlanner 按照用户指定的顺序逐条应用规则，维护一个单一的 RelNode 树——没有等价类，没有代价比较，没有搜索空间爆炸。

选择 HepPlanner 的理由：

1. **确定性**：相同的输入总是产生相同的输出，不像 Volcano 那样依赖匹配顺序
2. **高效**：线性扫描规则列表，不维护等价类
3. **可预测**：开发者明确知道规则的应用顺序
4. **规则依赖**：当规则 B 需要规则 A 先执行时，Hep 的有序性保证这一点

## 10.2 HepProgram 与 HepInstruction

`HepProgram` 是 HepPlanner 的"程序"——它定义了规则的应用序列。

```java
// plan/hep/HepProgram.java
public class HepProgram extends HepInstruction {
  // 由 HepProgramBuilder 构建
}
```

### 10.2.1 HepProgramBuilder — 构建规则序列

```java
// 构建 HepProgram
HepProgram program = HepProgramBuilder.create()
    .addMatchOrder(HepMatchOrder.BOTTOM_UP)
    .addRuleInstance(FilterProjectTransposeRule.INSTANCE)
    .addRuleInstance(ProjectFilterTransposeRule.INSTANCE)
    .addRuleInstance(FilterJoinRule.FILTER_INTO_JOIN)
    .addRuleCollection(ImmutableList.of(
        ProjectMergeRule.INSTANCE,
        FilterMergeRule.INSTANCE))
    .build();
```

HepInstruction 的类型：

| 指令 | 含义 |
|------|------|
| `addRuleInstance(rule)` | 添加一条规则，执行一次 |
| `addRuleCollection(rules)` | 添加一组规则，重复执行直到没有更多匹配 |
| `addMatchOrder(order)` | 设置后续规则的匹配顺序 |
| `addSubprogram(subProgram)` | 嵌套子程序 |
| `addBeginGroup()` / `addEndGroup()` | 将一组规则作为原子单元执行 |

### 10.2.2 子程序与原子组

**子程序**（Subprogram）允许在主程序中嵌套一组规则：

```java
HepProgram subProgram = HepProgramBuilder.create()
    .addRuleInstance(FilterJoinRule.FILTER_INTO_JOIN)
    .addRuleInstance(ProjectJoinTransposeRule.INSTANCE)
    .build();

HepProgram program = HepProgramBuilder.create()
    .addMatchOrder(HepMatchOrder.BOTTOM_UP)
    .addSubprogram(subProgram)  // 子程序内的规则作为一个整体执行
    .build();
```

**原子组**确保一组规则要么全部应用成功，要么全部回滚：

```java
HepProgramBuilder builder = HepProgramBuilder.create();
builder.addBeginGroup();
builder.addRuleInstance(RuleA.INSTANCE);
builder.addRuleInstance(RuleB.INSTANCE);
builder.addEndGroup();
// 如果 RuleA 匹配但 RuleB 不匹配，RuleA 的变换也会回滚
```

## 10.3 HepMatchOrder — 匹配顺序

```java
// plan/hep/HepMatchOrder.java
public enum HepMatchOrder {
  ARBITRARY,    // 任意顺序（最快，但不保证确定性）
  BOTTOM_UP,    // 自底向上（先处理叶子节点）
  TOP_DOWN,     // 自顶向下（先处理根节点）
  DEPTH_FIRST   // 深度优先（先处理左子树）
}
```

匹配顺序的影响：

```
原始树:
    Project
      Filter
        Join
          Scan(A)
          Scan(B)

BOTTOM_UP: Scan(A) → Scan(B) → Join → Filter → Project
TOP_DOWN:  Project → Filter → Join → Scan(A) → Scan(B)
DEPTH_FIRST: Project → Filter → Join → Scan(A) → Scan(B)
```

**BOTTOM_UP 最常用**——它保证先处理底层算子，这样上层规则看到的是已经优化过的子树。

## 10.4 HepPlanner 的工作流程

```java
// HepPlanner.findBestExp() 简化
public RelNode findBestExp() {
  for (HepInstruction instruction : program.instructions) {
    switch (instruction.type) {
      case RULE_INSTANCE:
        applyRule(instruction.rule, instruction.untilFixedPoint);
        break;
      case RULE_COLLECTION:
        applyRules(instruction.rules, instruction.untilFixedPoint);
        break;
      case MATCH_ORDER:
        currentMatchOrder = instruction.order;
        break;
      case SUBPROGRAM:
        executeSubprogram(instruction.subProgram);
        break;
    }
  }
  return root;
}
```

### 10.4.1 规则应用过程

```java
// HepPlanner.applyRule() 简化
private void applyRule(RelOptRule rule, boolean untilFixedPoint) {
  do {
    boolean matched = false;
    // 按 matchOrder 遍历树中的所有 RelNode
    for (RelNode rel : getAllNodes(root, currentMatchOrder)) {
      if (rule.matches(rel)) {
        // 创建规则调用并执行
        HepRuleCall call = new HepRuleCall(this, rule, rel);
        rule.onMatch(call);
        matched = true;
        break;  // 一次只应用一个匹配，然后重新遍历
      }
    }
    if (!matched || !untilFixedPoint) {
      break;  // 没有更多匹配或不需要迭代到不动点
    }
  } while (true);
}
```

关键行为：**每次规则应用后，整棵树被重新遍历**。这是因为规则可能改变了树的结构，之前的匹配可能不再有效。

### 10.4.2 HepRelVertex — 图中的顶点

HepPlanner 将 RelNode 树表示为一个有向无环图（DAG），每个节点用 `HepRelVertex` 包装：

```java
// plan/hep/HepRelVertex.java
class HepRelVertex extends AbstractRelNode {
  RelNode currentRel;  // 当前的关系表达式
}
```

`HepRelVertex` 是一个可变的包装器——当规则替换一个 RelNode 时，对应的 HepRelVertex 的 `currentRel` 被更新，而图的拓扑结构不变。这避免了重建整棵树的开销。

## 10.5 Hep vs Volcano：何时选择哪种优化器

| 场景 | 推荐优化器 | 理由 |
|------|-----------|------|
| 简单的谓词下推 | Hep | 规则少且确定，不需要代价比较 |
| 规则间有依赖 | Hep | Hep 的有序性保证依赖满足 |
| Join 重排序 | Volcano | 需要代价比较选择最优顺序 |
| Convention 转换 | Volcano | 需要等价类搜索多种物理实现 |
| 物化视图匹配 | Volcano | 需要等价替换和代价比较 |
| 快速原型 | Hep | 简单、可调试 |
| 生产级 CBO | Volcano + 自定义代价 | 全局最优性 |

**实际项目中的混合策略**：Spark、StarRocks 等项目通常先用 RBO（类似 Hep）做逻辑优化，再用 CBO（类似 Volcano）做物理选择。Calcite 的 `Programs.standard()` 也采用了类似策略——多遍优化，每遍使用不同的优化器。

---

## 本章小结

HepPlanner 是一个简单的顺序优化器，通过 HepProgram 定义规则应用序列。匹配顺序（BOTTOM_UP、TOP_DOWN、DEPTH_FIRST）控制遍历方向。子程序和原子组提供组合和回滚能力。Hep 适用于规则间有依赖、不需要代价比较的场景，而 Volcano 适用于需要全局搜索的物理选择。下一章将深入 Calcite 的 100+ 条内置优化规则。
