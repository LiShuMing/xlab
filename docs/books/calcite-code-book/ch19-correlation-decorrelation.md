# 第19章：关联子查询与解关联

## 19.1 关联子查询的问题

关联子查询引用外层查询的列，导致朴素执行时对外层每一行都执行一次子查询——时间复杂度为 O(N×M)。解关联的目标是将其转换为 Join，复杂度降为 O(N+M)。

```sql
-- 关联子查询（朴素执行: O(N×M)）
SELECT * FROM emp e
WHERE salary > (SELECT AVG(salary) FROM emp WHERE dept_id = e.dept_id)

-- 解关联后（Join 执行: O(N+M)）
SELECT e.*
FROM emp e
JOIN (SELECT dept_id, AVG(salary) AS avg_sal FROM emp GROUP BY dept_id) d
ON e.dept_id = d.dept_id
WHERE e.salary > d.avg_sal
```

## 19.2 关联变量的表示

```java
// rel/core/CorrelationId.java
public class CorrelationId {
  private final String id;  // 如 "$cor0"

  // 在 RexNode 中通过 RexCorrelVariable + RexFieldAccess 引用
  // $cor0.dept_id → RexFieldAccess(RexCorrelVariable($cor0), "dept_id")
}
```

## 19.3 Decorrelator 演进

### 19.3.1 RelDecorrelator

`RelDecorrelator`（`sql2rel/RelDecorrelator.java`）是传统的解关联器，基于规则的模式匹配：

```
1. 识别 Correlate 算子
2. 将关联条件转换为等值 Join 条件
3. 将关联变量替换为 Join 输出的列引用
4. 消除 Correlate 算子
```

### 19.3.2 TopDownGeneralDecorrelator

`TopDownGeneralDecorrelator`（`sql2rel/TopDownGeneralDecorrelator.java`）是 Calcite 新的解关联器，自顶向下处理，支持更复杂的关联模式：

- 支持多层嵌套的关联子查询
- 正确处理 `IN`/`EXISTS`/`NOT IN`/`NOT EXISTS` 语义
- 处理关联变量在聚合、窗口函数中的引用

### 19.3.3 Programs.standard 中的解关联

```java
// Programs.standard() 中的 DecorrelateProgram
new DecorrelateProgram()
```

解关联在子查询消除之后、主优化之前执行——这是因为解关联产出的 Join 可以被后续优化规则进一步优化。

## 19.4 Correlate 算子

`Correlate` 是关联子查询的关系代数表示：

```java
// rel/core/Correlate.java
public abstract class Correlate extends BiRel {
  protected final CorrelationId correlationId;        // 关联 ID
  protected final ImmutableBitSet requiredColumns;    // 关联变量引用的左表列
  protected final JoinRelType joinType;               // INNER/LEFT/SEMI/ANTI
}
```

### 19.4.1 Correlate 的执行语义

```
左输入的每一行:
  1. 设置关联变量的值 = 当前行
  2. 执行右输入（引用关联变量）
  3. 将左行和右行 Join

类似于 NestedLoopJoin，但右输入可以是任意关系表达式
```

### 19.4.2 ConditionalCorrelate

`ConditionalCorrelate` 是 Correlate 的优化变体——只在条件满足时才执行右输入：

```java
// rel/core/ConditionalCorrelate.java
// 当左行的某列非 NULL 时才关联右表
// 避免对不需要关联的行执行子查询
```

## 19.5 解关联的等价变换证明

核心变换：将 Correlate 转换为等值的 Aggregate + Join：

```
Correlate(left=L, right=R($cor), joinType=INNER)
  where $cor references columns [c1, c2] from L

等价于:

Aggregate(group=[c1, c2], ...)
  Join(L, R, on L.c1 = R.c1 AND L.c2 = R.c2, joinType=INNER)
```

关键条件：
1. 右输入 R 中的关联变量引用必须只出现在等值条件中
2. 右输入不能有关联变量在非等值条件、聚合、窗口函数中的引用（否则需要更复杂的变换）
3. 解关联后的语义必须与原始关联子查询一致（包括 NULL 语义）

---

## 本章小结

关联子查询是 SQL 最复杂的构造之一。Calcite 通过 RexCorrelVariable + Correlate 算子表示关联，再通过 RelDecorrelator 或 TopDownGeneralDecorrelator 将其解关联为 Join。解关联将 O(N×M) 的执行复杂度降为 O(N+M)，是查询优化中最有价值的变换之一。
