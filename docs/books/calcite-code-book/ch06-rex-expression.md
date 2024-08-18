# 第6章：Rex 表达式体系 — 关系代数的语言

## 6.1 RexNode — 行表达式基类

如果说 RelNode 是关系代数的"算子"（描述数据流如何变换），那么 RexNode 就是关系代数的"表达式"（描述每个数据行上的计算逻辑）。每个 RexNode 都有一个确定的类型（`RelDataType`），这是它和 SqlNode 的根本区别——SqlNode 在验证前没有类型。

```java
// rex/RexNode.java
public abstract class RexNode {
  protected @MonotonicNonNull String digest;  // 规范化字符串表示

  public abstract RelDataType getType();  // 表达式的类型
  public SqlKind getKind() { return SqlKind.OTHER; }

  public boolean isAlwaysTrue() { return false; }
  public boolean isAlwaysFalse() { return false; }

  // 接受访问者
  public abstract <R> R accept(RexVisitor<R> visitor);
}
```

所有 RexNode 子类都是**不可变的**——一旦创建就不能修改。需要变换时创建新对象。

## 6.2 RexNode 继承体系

```
RexNode (abstract)
├── RexLiteral          — 字面量常量
├── RexCall             — 函数/操作符调用（最核心的子类）
│   ├── RexOver         — 窗口函数调用
│   └── RexSubQuery     — 子查询表达式
├── RexVariable (abstract) — 变量
│   ├── RexSlot (abstract) — 位置引用
│   │   ├── RexInputRef   — 输入列引用（$0, $1, ...）
│   │   ├── RexLocalRef   — 局部引用（RexProgram 内部使用）
│   │   └── RexLambdaRef  — Lambda 参数引用
│   ├── RexCorrelVariable — 关联变量（$cor0）
│   └── RexDynamicParam   — 动态参数（?）
├── RexFieldAccess      — 字段访问（e.name）
├── RexRangeRef         — 范围引用
├── RexPattern          — 模式匹配变量
└── RexLambda           — Lambda 表达式（1.42 新增）
```

### 6.2.1 RexInputRef — 最常见的表达式

`RexInputRef` 是整个 Rex 体系中最频繁出现的类型——它表示"第 N 个输入列"：

```java
// rex/RexInputRef.java
public class RexInputRef extends RexSlot {
  private final int index;  // 列序号，从 0 开始

  // $0 表示第 0 列，$1 表示第 1 列
  public static RexInputRef of(int index, RelDataType type) { ... }
}
```

在 RelNode 树中，几乎所有列引用都是 RexInputRef。例如：

```sql
SELECT name, salary * 1.1 FROM emp WHERE dept_id = 10
```

转换为 Rex 表达式后：

```
Project: [$1, $5 * 1.1]     → RexInputRef($1), RexCall(*, [RexInputRef($5), RexLiteral(1.1)])
Filter:  [$7 = 10]          → RexCall(=, [RexInputRef($7), RexLiteral(10)])
TableScan: [empno, name, job, mgr, hiredate, salary, comm, dept_id]
             $0     $1    $2   $3    $4        $5     $6     $7
```

### 6.2.2 RexLiteral — 常量值

```java
// rex/RexLiteral.java
public class RexLiteral extends RexNode {
  private final @Nullable Comparable value;  // 值
  private final RelDataType type;            // 类型
  private final SqlTypeName typeName;        // SQL 类型名

  // 常见工厂方法
  public static RexLiteral createBoolean(boolean value) { ... }
  public static RexLiteral createExactNumeric(String value) { ... }
  public static RexLiteral createCharString(String value) { ... }
  public static RexLiteral createNull() { ... }
}
```

RexLiteral 的 `value` 是 `Comparable` 类型，具体类型取决于 `typeName`：

| typeName | value 类型 | 示例 |
|----------|-----------|------|
| BOOLEAN | Boolean | `true` |
| INTEGER | Integer | `42` |
| BIGINT | Long | `9999999999L` |
| DECIMAL | BigDecimal | `3.14` |
| CHAR/VARCHAR | NlsString | `'hello'` |
| DATE | Calendar | `DATE '2024-01-01'` |
| TIMESTAMP | Calendar | `TIMESTAMP '2024-01-01 12:00:00'` |
| NULL | null | `NULL` |

### 6.2.3 RexCall — 函数调用

`RexCall` 是最通用的表达式类型，表示任何操作符或函数的调用：

```java
// rex/RexCall.java
public class RexCall extends RexNode {
  private final SqlOperator operator;     // 操作符
  private final List<RexNode> operands;   // 操作数
  private final RelDataType type;         // 返回类型
}
```

RexCall 覆盖了从简单算术到复杂函数的所有情况：

```
a + b       → RexCall(PLUS, [RexInputRef($0), RexInputRef($1)])
CAST(x, INT) → RexCall(CAST, [RexInputRef($0)])
CASE WHEN   → RexCall(CASE, [condition1, result1, condition2, result2, elseValue])
COUNT(*)    → RexCall(COUNT, [])  — 但在聚合中由 AggregateCall 表示
```

**RexOver** 是 RexCall 的子类，专门表示窗口函数：

```java
// rex/RexOver.java
public class RexOver extends RexCall {
  private final RexWindow window;  // 窗口定义
  // 继承 operator, operands, type
}
```

**RexSubQuery** 也是 RexCall 的子类，表示子查询表达式：

```java
// rex/RexSubQuery.java
public class RexSubQuery extends RexCall {
  private final RelNode rel;  // 子查询的 RelNode
  // 支持 EXISTS, IN, SCALAR_QUERY 等类型
}
```

### 6.2.4 RexCorrelVariable — 关联变量

关联变量表示关联子查询中对上层数据的引用：

```java
// rex/RexCorrelVariable.java
public class RexCorrelVariable extends RexVariable {
  private final CorrelationId id;  // 关联 ID

  // 使用方式: $cor0.dept_id — 配合 RexFieldAccess
}
```

### 6.2.5 RexLambda — Lambda 表达式

Calcite 1.42 新增的 Lambda 表达式支持：

```java
// rex/RexLambda.java
public class RexLambda extends RexNode {
  private final List<RexLambdaRef> parameters;  // 参数
  private final RexNode expression;              // 表达式体
}
```

## 6.3 RexBuilder — 表达式构造工厂

RexBuilder 是创建 RexNode 的统一入口，保证类型推导和规范化：

```java
// rex/RexBuilder.java
public class RexBuilder {
  private final RelDataTypeFactory typeFactory;

  // 创建字面量
  public RexLiteral makeLiteral(boolean value) { ... }
  public RexLiteral makeLiteral(int value) { ... }
  public RexLiteral makeLiteral(String value) { ... }
  public RexLiteral makeNullLiteral(RelDataType type) { ... }

  // 创建输入引用
  public RexInputRef makeInputRef(RelDataType type, int index) { ... }
  public RexInputRef makeInputRef(RelDataType rowType, String fieldName) { ... }

  // 创建函数调用
  public RexNode makeCall(SqlOperator op, RexNode... exprs) { ... }
  public RexNode makeCall(SqlOperator op, List<RexNode> exprs) { ... }
  public RexNode makeCall(RelDataType type, SqlOperator op, List<RexNode> exprs) { ... }

  // 创建 CAST
  public RexNode makeCast(RelDataType type, RexNode expr) { ... }
  public RexNode makeAbstractCast(RelDataType type, RexNode expr) { ... }

  // 创建窗口函数
  public RexOver makeOver(RelDataType type, SqlOperator op, List<RexNode> args,
      List<RexNode> partitionKeys, List<RexFieldCollation> orderKeys,
      RexWindowBound lowerBound, RexWindowBound upperBound, ...) { ... }

  // 创建 IN 表达式
  public RexNode makeIn(RexNode arg, List<RexNode> ranges) { ... }
}
```

RexBuilder 的关键行为：

1. **类型推导**：`makeCall(op, exprs)` 自动推导返回类型
2. **规范化**：相同属性的表达式共享 digest
3. **常量折叠**：`makeCall(PLUS, [1, 2])` 可能直接返回 `RexLiteral(3)`
4. **简化**：`makeCall(AND, [TRUE, x])` 简化为 `x`

## 6.4 RexProgram — 表达式程序模型

`RexProgram` 是 Calcite 最精妙的设计之一——它将一个 Filter+Project 组合压缩为一个紧凑的"表达式程序"。

### 6.4.1 为什么需要 RexProgram

考虑一个典型的 Filter+Project：

```
LogicalProject(name=[$1], salary=[$5 * 1.1])
  LogicalFilter(condition=[$7 = 10])
    LogicalTableScan(emp)
```

这个组合可以用一个 RexProgram 表示：

```
RexProgram:
  inputRowType: [empno, name, job, mgr, hiredate, salary, comm, dept_id]
  exprs:
    $0: $7 = 10              (条件表达式)
    $1: $5 * 1.1             (salary * 1.1)
  condition: $0               (引用 exprs[0])
  projects: [$1, $1]          (name → 引用输入列 $1, salary*1.1 → 引用 exprs[1])
  outputRowType: [name VARCHAR, salary DECIMAL]
```

### 6.4.2 RexProgram 的结构

```java
// rex/RexProgram.java
public class RexProgram {
  private final List<RexNode> exprs;           // 公共子表达式列表
  private final List<RexLocalRef> projects;    // 投影引用
  private final @Nullable RexLocalRef condition; // 过滤条件引用
  private final RelDataType inputRowType;      // 输入行类型
  private final RelDataType outputRowType;     // 输出行类型
}
```

RexProgram 的执行模型是一个两阶段计算：

**阶段 1 — 计算公共子表达式**：
```
exprs[0] = $7 = 10        (计算条件)
exprs[1] = $5 * 1.1       (计算 salary 表达式)
```

**阶段 2 — 输出**：
```
condition = exprs[0]       (使用条件过滤)
projects = [$1, exprs[1]]  (输出 name 和计算后的 salary)
```

### 6.4.3 RexLocalRef — 局部引用

`RexLocalRef` 是 RexProgram 内部的引用机制——它引用 `exprs` 列表中的某个表达式：

```java
// rex/RexLocalRef.java
public class RexLocalRef extends RexSlot {
  private final int index;  // 在 exprs 列表中的索引
}
```

在 RexProgram 中，所有引用都通过 `RexLocalRef` 间接引用。这意味着：

- 输入列通过 `RexInputRef` 引用（引用输入行类型的列）
- 中间表达式通过 `RexLocalRef` 引用（引用 exprs 列表）
- projects 和 condition 都使用 `RexLocalRef`

### 6.4.4 RexProgramBuilder — 构建 RexProgram

```java
// 使用 RexProgramBuilder 构建程序
RexProgramBuilder builder = new RexProgramBuilder(inputRowType, rexBuilder);

// 添加条件
RexLocalRef conditionRef = builder.addExpr(condition);

// 添加投影
List<RexLocalRef> projectRefs = new ArrayList<>();
for (RexNode project : projects) {
  projectRefs.add(builder.addExpr(project));
}

// 构建程序
RexProgram program = builder.makeProgram(projectRefs, conditionRef);
```

### 6.4.5 RexProgram 的应用

RexProgram 在 Calcite 中被广泛使用：

1. **Calc 算子**：`LogicalCalc` / `EnumerableCalc` 内部持有一个 RexProgram，表示 Filter+Project 的融合
2. **常量折叠**：`ReduceExpressionsRule` 通过 RexProgram 发现和折叠常量
3. **代码生成**：Enumerable 代码生成器基于 RexProgram 生成 Java 代码

## 6.5 RexSimplify — 表达式化简引擎

`RexSimplify`（3650 行）是 Calcite 最复杂的工具类之一，它实现了各种表达式化简规则。

### 6.5.1 核心化简方法

```java
// rex/RexSimplify.java
public class RexSimplify {
  // 主入口
  public RexNode simplify(RexNode e) { ... }

  // 按类型分发
  private RexNode simplifyAnd(RexCall e, RexUnknownAs unknownAs) { ... }
  private RexNode simplifyOr(RexCall e, RexUnknownAs unknownAs) { ... }
  private RexNode simplifyNot(RexCall e, RexUnknownAs unknownAs) { ... }
  private RexNode simplifyCase(RexCall e, RexUnknownAs unknownAs) { ... }
  private RexNode simplifyCast(RexCall e) { ... }
  private RexNode simplifyIs(RexCall e, RexUnknownAs unknownAs) { ... }

  // 批量化简
  public RexNode simplifyAnds(Iterable<? extends RexNode> nodes) { ... }
}
```

### 6.5.2 化简规则示例

**布尔化简**：
```
TRUE AND x       → x
FALSE AND x      → FALSE
TRUE OR x        → TRUE
FALSE OR x       → x
NOT NOT x        → x
x AND NOT x      → FALSE（矛盾检测）
x OR NOT x       → TRUE（重言式检测）
```

**比较化简**：
```
x = x            → TRUE（如果 x 非 NULL）
x <> x           → FALSE
x > x            → FALSE
CAST(x, INT) IS NULL → FALSE（如果 x 已知非 NULL）
```

**CAST 化简**：
```
CAST(CAST(x, VARCHAR), INT) → CAST(x, INT)  — 消除冗余 CAST
CAST(42, INT)               → RexLiteral(42, INT)  — 常量折叠
CAST(x, INT) where x is INT → x  — 消除无意义 CAST
```

**CASE 化简**：
```
CASE WHEN TRUE THEN x ELSE y END  → x
CASE WHEN FALSE THEN x ELSE y END → y
CASE WHEN p THEN x WHEN p THEN y ELSE z END → CASE WHEN p THEN x ELSE z END
```

**范围推理**（基于 SARG）：
```
x > 10 AND x < 20 → SARG(10 < x < 20)
x > 10 AND x > 5  → x > 10（取更强条件）
x > 10 AND x < 5  → FALSE（矛盾检测）
```

### 6.5.3 RexUnknownAs — NULL 语义

SQL 中 NULL 的三值逻辑（TRUE/FALSE/UNKNOWN）使化简变得复杂。`RexUnknownAs` 参数控制 NULL 如何处理：

```java
public enum RexUnknownAs {
  UNKNOWN,     // 保留 UNKNOWN
  FALSE,       // UNKNOWN → FALSE（WHERE 语义）
  TRUE         // UNKNOWN → TRUE（CHECK 约束语义）
}
```

在 WHERE 子句中，`UNKNOWN` 等同于 `FALSE`，因此：
```
x > 10 AND NULL  → NULL → FALSE（在 WHERE 中）
```

## 6.6 RexShuttle 与 RexVisitor — 遍历与改写模式

### 6.6.1 RexVisitor

`RexVisitor` 是只读的访问者接口：

```java
// rex/RexVisitor.java
public interface RexVisitor<R> {
  R visitInputRef(RexInputRef inputRef);
  R visitLiteral(RexLiteral literal);
  R visitCall(RexCall call);
  R visitOver(RexOver over);
  R visitSubQuery(RexSubQuery subQuery);
  R visitCorrelVariable(RexCorrelVariable correlVariable);
  R visitDynamicParam(RexDynamicParam dynamicParam);
  R visitFieldAccess(RexFieldAccess fieldAccess);
  // ...
}
```

### 6.6.2 RexShuttle — 改写模式

`RexShuttle` 是最常用的 RexNode 变换工具——它遍历表达式树，对每个节点应用变换，返回新的表达式：

```java
// rex/RexShuttle.java
public class RexShuttle implements RexVisitor<RexNode> {
  @Override public RexNode visitCall(RexCall call) {
    // 1. 递归访问所有子节点
    List<RexNode> newOperands = visitList(call.operands, update);
    // 2. 如果子节点有变化，创建新 RexCall
    if (update[0]) {
      return call.clone(call.type, newOperands);
    }
    return call;
  }

  @Override public RexNode visitInputRef(RexInputRef inputRef) {
    return inputRef;  // 默认不修改
  }

  @Override public RexNode visitLiteral(RexLiteral literal) {
    return literal;  // 默认不修改
  }
}
```

典型用途——列号偏移：当两个 RelNode 做 Join 时，右表的列号需要偏移：

```java
RexShuttle offsetShuttle = new RexShuttle() {
  @Override public RexNode visitInputRef(RexInputRef ref) {
    return new RexInputRef(ref.getIndex() + leftFieldCount, ref.getType());
  }
};
RexNode newCondition = rightCondition.accept(offsetShuttle);
```

### 6.6.3 RexUtil — 工具方法集

`RexUtil` 提供了大量静态工具方法：

| 方法 | 功能 |
|------|------|
| `and(list)` | 合并 AND 列表（扁平化嵌套 AND） |
| `or(list)` | 合并 OR 列表 |
| `not(expr)` | 取反（双重否定消除） |
| `flatten(expr)` | 扁平化嵌套的 AND/OR |
| `isLiteral(node)` | 判断是否为字面量 |
| `findOperatorCall(op, node)` | 查找特定操作符 |
| `composeConjunction(list)` | 合并多个谓词为 AND |
| `composeDisjunction(list)` | 合并多个谓词为 OR |
| `swapTableReferences` | 交换 Join 的左右输入引用 |

## 6.7 RexExecutor — 表达式运行时求值

`RexExecutorImpl` 可以在优化阶段执行常量表达式：

```java
// rex/RexExecutorImpl.java
public class RexExecutorImpl implements RexExecutor {
  @Override public void execute(RexProgram program, List<RexNode> results) {
    // 通过 Janino 编译 RexProgram 为 Java 字节码并执行
    // 用于常量折叠、分区裁剪等场景
  }
}
```

使用场景：

1. **常量折叠**：`RexSimplify` 调用 executor 求 `1 + 2` = `3`
2. **分区裁剪**：求 `CAST('2024-01-01' AS DATE)` 确定分区值
3. **索引匹配**：求表达式值以匹配索引条件

## 6.8 从源码跟踪一次表达式化简

输入：`WHERE x > 10 AND x < 5 OR y = 'hello'`

```
1. simplify(RexCall(OR, [
     RexCall(AND, [RexCall(>, [$0, 10]), RexCall(<, [$0, 5])]),
     RexCall(=, [$1, 'hello'])
   ]))

2. simplifyOr:
   → simplify 左子节点: AND(x>10, x<5)
     → simplifyAnd:
       → 范围推理: x > 10 AND x < 5 → 空范围 → FALSE
   → simplify 右子节点: y = 'hello' → 无化简
   → OR(FALSE, y='hello') → y = 'hello'

3. 最终结果: y = 'hello'
```

---

## 本章小结

RexNode 是关系代数的表达式语言，RexInputRef（列引用）、RexLiteral（常量）和 RexCall（函数调用）构成了绝大多数表达式。RexProgram 是 Filter+Project 的紧凑表示，通过公共子表达式消除和局部引用机制优化执行。RexSimplify 实现了丰富的化简规则，包括布尔化简、CAST 消除、范围推理和矛盾检测。RexShuttle 是遍历改写表达式的标准工具。下一章将进入 RelNode 体系——关系代数的算子世界。
