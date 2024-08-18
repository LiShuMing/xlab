# 第13章：Convention 与代码生成

## 13.1 Convention 接口与 ConventionTraitDef

Convention 是最重要的 RelTrait——它决定了 RelNode 如何产出数据给其消费者。

```java
// plan/Convention.java
public interface Convention extends RelTrait {
  Convention NONE = new Impl("NONE", RelNode.class);

  String getName();                     // 约定名称
  Class getInterface();                 // 算子必须实现的接口
  boolean canConvertConvention(Convention toConvention);  // 能否转换
}
```

Calcite 内置三种 Convention：

| Convention | 接口 | 产出方式 |
|-----------|------|---------|
| `NONE` | `RelNode.class` | 不可执行（逻辑算子） |
| `ENUMERABLE` | `EnumerableRel.class` | `Enumerable<Object>` 对象流 |
| `BINDABLE` | `BindableRel.class` | `Bindable`，绑定参数后执行 |
| `INTERPRETABLE` | `InterpretableRel.class` | 直接解释执行 |

ConventionTraitDef 管理 Convention 之间的转换关系：

```java
// plan/ConventionTraitDef.java
public class ConventionTraitDef extends RelTraitDef<Convention> {
  @Override public boolean canConvert(RelOptPlanner planner, Convention from, Convention to) {
    return from.canConvertConvention(to) || to.canConvertConvention(from);
  }
}
```

## 13.2 EnumerableConvention — Java 代码生成路径

EnumerableConvention 是 Calcite 默认的物理执行方式，通过 linq4j 表达式树生成 Java 代码，经 Janino 即时编译后执行。

### 13.2.1 EnumerableRel 接口

```java
// adapter/enumerable/EnumerableRel.java
public interface EnumerableRel extends PhysicalNode {
  Result implement(EnumerableRelImplementor implementor, Prefer prefer);
}
```

每个 Enumerable 算子必须实现 `implement()` 方法，返回代码生成的结果。

### 13.2.2 代码生成流程

```
EnumerableRel.implement()
  → 生成 linq4j 表达式树（BlockBuilder）
    → EnumerableRelImplementor.result()
      → 汇总所有算子的表达式树
        → 生成完整的 Java 类源码
          → Janino 编译为字节码
            → 类加载并实例化
              → 调用 enumerable() 获取 Enumerable 对象
```

### 13.2.3 EnumerableCalc 的代码生成

以 `EnumerableCalc`（Filter+Project 的融合算子）为例：

```java
// adapter/enumerable/EnumerableCalc.java
@Override public Result implement(EnumerableRelImplementor implementor, Prefer pref) {
  // 1. 生成子算子的代码
  Result childResult = implementor.visitChild(this, 0, child, pref);

  // 2. 创建物理类型（PhysType）
  PhysType physType = PhysTypeImpl.of(typeFactory, getRowType(), pref, ...);

  // 3. 生成 RexProgram 的执行代码
  BlockBuilder builder = new BlockBuilder();
  RexToLixTranslator translator = RexToLixTranslator.forProgram(
      program, childResult.physType, ...);

  // 4. 生成过滤条件的代码
  if (program.getCondition() != null) {
    Expression condition = translator.translate(program.getCondition());
    builder.add(Expressions.ifThen(Expressions.not(condition),
        Expressions.return_(null, ...)));
  }

  // 5. 生成投影表达式的代码
  List<Expression> projections = translator.translateList(program.getProjectList());

  // 6. 组装为 Enumerable 操作
  return implementor.result(physType, builder.toBlock());
}
```

生成的 Java 代码（概念）：

```java
// 生成的 EnumerableCalc 实现
public class GeneratedCalc extends EnumerableCalc {
  public Enumerable<Object> enumerate() {
    return child.enumerate()
        .where(row -> (int) row[5] > 1000)          // Filter
        .select(row -> new Object[]{row[1], row[5]}); // Project
  }
}
```

### 13.2.4 PhysType — 物理类型映射

`PhysType` 将 `RelDataType` 映射到 Java 类型：

```java
// adapter/enumerable/PhysTypeImpl.java
public class PhysTypeImpl implements PhysType {
  // RelDataType → Java Class 的映射
  // INTEGER → int.class / Integer.class
  // VARCHAR → String.class
  // DECIMAL → BigDecimal.class
  // DATE → Integer.class (days since epoch)
  // TIMESTAMP → Long.class (millis since epoch)
  // ROW → Object[].class
  // ARRAY → Object[].class
}
```

JavaRowFormat 决定行的表示方式：

| 格式 | 行表示 | 适用场景 |
|------|--------|---------|
| `ARRAY` | `Object[]` | 通用，灵活但有装箱开销 |
| `CUSTOM` | 用户自定义类 | 强类型，无装箱 |
| `SCALAR` | 单个值 | 单列结果 |

## 13.3 linq4j 表达式树

linq4j 的 `tree` 包提供了 Java 表达式树的完整建模，是代码生成的中间表示：

### 13.3.1 核心类

| 类 | Java 等价 |
|----|----------|
| `ConstantExpression` | 字面量：`42`, `"hello"` |
| `ParameterExpression` | 变量引用：`row`, `index` |
| `BinaryExpression` | 二元运算：`a + b`, `x > 0` |
| `ConditionalExpression` | 三元：`cond ? a : b` |
| `MethodCallExpression` | 方法调用：`list.add(x)` |
| `NewExpression` | 对象创建：`new Object[]{a, b}` |
| `BlockStatement` | 代码块：`{ stmt1; stmt2; }` |
| `DeclarationStatement` | 变量声明：`int x = 42;` |

### 13.3.2 BlockBuilder — 代码构建器

```java
BlockBuilder builder = new BlockBuilder();
ParameterExpression row = Expressions.parameter(Object[].class, "row");

// 生成: int salary = (Integer) row[5];
DeclarationStatement salaryDecl = builder.declare(int.class, "salary",
    Expressions.convert_(
        Expressions.arrayIndex(row, Expressions.constant(5)),
        Integer.class));

// 生成: if (salary > 1000) { return row; }
builder.add(Expressions.ifThen(
    Expressions.greaterThan(salaryDecl.parameter, Expressions.constant(1000)),
    Expressions.return_(null, row)));

BlockStatement block = builder.toBlock();
```

### 13.3.3 Expressions 工厂类

`Expressions` 是创建表达式节点的工厂：

```java
Expressions.constant(42)                          // 字面量
Expressions.parameter(int.class, "x")             // 参数
Expressions.add(a, b)                             // a + b
Expressions.greaterThan(a, b)                     // a > b
Expressions.call(list, "add", element)            // list.add(element)
Expressions.newArray(Object.class, 2)             // new Object[2]
Expressions.condition(test, ifTrue, ifFalse)       // test ? ifTrue : ifFalse
```

## 13.4 ConverterRule — Convention 转换的实现模式

每个 Enumerable 算子都有对应的 ConverterRule，将逻辑算子转换为物理算子：

| ConverterRule | 逻辑算子 | 物理算子 |
|--------------|---------|---------|
| `EnumerableCalcRule` | LogicalCalc | EnumerableCalc |
| `EnumerableFilterRule` | LogicalFilter | EnumerableFilter |
| `EnumerableProjectRule` | LogicalProject | EnumerableProject |
| `EnumerableHashJoinRule` | LogicalJoin | EnumerableHashJoin |
| `EnumerableMergeJoinRule` | LogicalJoin | EnumerableMergeJoin |
| `EnumerableNestedLoopJoinRule` | LogicalJoin | EnumerableNestedLoopJoin |
| `EnumerableAggregateRule` | LogicalAggregate | EnumerableAggregate |
| `EnumerableSortRule` | LogicalSort | EnumerableSort |
| `EnumerableTableScanRule` | LogicalTableScan | EnumerableTableScan |
| `EnumerableValuesRule` | LogicalValues | EnumerableValues |
| `EnumerableWindowRule` | LogicalWindow | EnumerableWindow |

ConverterRule 的典型实现：

```java
// EnumerableCalcRule.java
class EnumerableCalcRule extends ConverterRule {
  EnumerableCalcRule(Config config) {
    super(config.withInConvention(Convention.NONE)
               .withOutConvention(EnumerableConvention.INSTANCE));
  }

  @Override public RelNode convert(RelNode rel) {
    Calc calc = (Calc) rel;
    return new EnumerableCalc(
        calc.getCluster(),
        calc.getTraitSet().replace(EnumerableConvention.INSTANCE),
        convert(calc.getInput(), EnumerableConvention.INSTANCE),
        calc.getProgram());
  }
}
```

## 13.5 JaninoRexCompiler — Rex → Java 字节码

`JaninoRexCompiler` 将 RexNode 表达式编译为可执行的 Java 代码，用于常量折叠和分区裁剪：

```java
// interpreter/JaninoRexCompiler.java
public class JaninoRexCompiler implements RexExecutor {
  @Override public void compile(RexProgram program, List<RexNode> results) {
    // 1. 将 RexProgram 转换为 Java 源码
    // 2. 用 Janino 编译为字节码
    // 3. 返回编译后的可执行表达式
  }
}
```

与 EnumerableRelImplementor 的区别：JaninoRexCompiler 编译单个表达式，而 EnumerableRelImplementor 编译整个查询计划。

## 13.6 BindableConvention 与 InterpretableConvention

### BindableConvention

`BindableConvention` 产出 `Bindable` 对象——绑定参数后返回 `Enumerable`：

```java
public interface BindableRel extends RelNode {
  Class getElementType();
  Enumerable bind(DataSet data);
}
```

Bindable 比 Enumerable 更轻量——不需要代码生成，适合简单查询。

### InterpretableConvention

`InterpretableConvention` 产出 `InterpretableRel`——直接解释执行：

```java
public interface InterpretableRel extends RelNode {
  Node implement(InterpreterImplementor implementor);
}
```

解释执行不生成 Java 代码，直接遍历算子树执行。适用于调试和原型，但性能最差。

---

## 本章小结

EnumerableConvention 通过 linq4j 表达式树生成 Java 代码，经 Janino 编译后执行。每个 Enumerable 算子实现 `implement()` 方法，使用 BlockBuilder 构建表达式树。PhysType 将 SQL 类型映射到 Java 类型。ConverterRule 将逻辑算子转换为物理算子。Bindable 和 Interpretable 是更轻量的执行方式。下一章将深入解释执行和运行时函数库。
