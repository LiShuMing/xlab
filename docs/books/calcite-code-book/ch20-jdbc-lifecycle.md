# 第20章：JDBC 集成与查询全流程

## 20.1 Calcite JDBC Driver

Calcite 实现了完整的 JDBC 接口，允许任何 JDBC 客户端直接连接 Calcite。

### 20.1.1 连接入口

```java
// jdbc/Driver.java
public class Driver extends UnregisteredDriver {
  static {
    DriverManager.registerDriver(new Driver());
  }

  @Override public Connection connect(String url, Properties info) {
    return new CalciteConnectionImpl(...);
  }
}
```

JDBC URL 格式：`jdbc:calcite:model=/path/to/model.json`

### 20.1.2 CalciteConnectionImpl

```java
// jdbc/CalciteConnectionImpl.java
public class CalciteConnectionImpl extends AvaticaConnection {
  private final CalciteSchema rootSchema;
  private final JavaTypeFactory typeFactory;

  // 创建 Statement
  @Override public Statement createStatement() {
    return new CalciteStatement(this);
  }

  // 创建 PreparedStatement
  @Override public PreparedStatement prepareStatement(String sql) {
    return new CalcitePreparedStatement(this, sql);
  }
}
```

## 20.2 查询全流程

一条 SQL 从输入到结果的完整旅程：

```
JDBC Client
  ↓ sql = "SELECT name FROM emp WHERE salary > 1000"
CalciteStatement.executeQuery(sql)
  ↓
CalcitePrepareImpl.prepare2_()
  ├─ 1. SqlParser.parseStmt()                    → SqlSelect
  ├─ 2. SqlValidator.validate(sqlNode)            → 验证后的 SqlNode
  ├─ 3. SqlToRelConverter.convertQuery()          → LogicalProject + LogicalFilter + LogicalTableScan
  ├─ 4. Programs.standard() 优化:
  │   ├─ 4a. SubQueryRemoveProgram               → 消除子查询
  │   ├─ 4b. DecorrelateProgram                   → 解关联
  │   ├─ 4c. TrimFieldsProgram                    → 字段裁剪
  │   ├─ 4d. VolcanoPlanner.findBestExp()         → 代价优化
  │   │   ├─ FilterIntoJoinRule                   → 过滤下推
  │   │   ├─ EnumerableCalcRule                   → Convention 转换
  │   │   └─ ...更多规则
  │   └─ 4e. CalcProgram                         → Calc 融合
  ├─ 5. Prepare.implement()                       → 生成可执行代码
  │   └─ EnumerableRelImplementor                 → Janino 编译
  └─ 6. 执行 Enumerable                          → 返回 ResultSet
```

### 20.2.1 Prepare 生命周期

```java
// prepare/Prepare.java
public abstract class Prepare {
  // 优化入口
  protected RelRoot optimize(RelRoot root, ...) {
    Program program = getProgram();  // Programs.standard()
    RelNode optimized = program.run(planner, root.rel, desiredTraits, ...);
    return root.withRel(optimized);
  }

  // 实现入口
  protected abstract PreparedResult implement(RelRoot root);
}
```

### 20.2.2 CalcitePreparingStmt

```java
// prepare/CalcitePrepareImpl.CalcitePreparingStmt
class CalcitePreparingStmt extends Prepare {
  @Override protected PreparedResult implement(RelRoot root) {
    // 将 EnumerableRel 编译为 Java 类
    // 返回可执行的 PreparedResult
  }
}
```

## 20.3 Frameworks 与 Planner API

`Frameworks` 是程序化使用 Calcite 的标准方式，不需要 JDBC：

```java
// tools/Frameworks.java
public class Frameworks {
  public static RelNode run(PrepareAction action) {
    return withPlanner(action::apply, ...);
  }
}

// 使用示例
RelNode optimized = Frameworks.run(new Frameworks.PrepareAction() {
  @Override public RelNode apply(RelOptPlanner planner, RelBuilder builder) {
    // 1. 构建查询
    RelNode rel = builder
        .scan("EMP")
        .filter(builder.call(GREATER_THAN, builder.field("SAL"), builder.literal(1000)))
        .project(builder.field("NAME"))
        .build();

    // 2. 设置规则
    planner.addRule(FilterJoinRule.FILTER_INTO_JOIN);
    planner.addRule(EnumerableCalcRule.INSTANCE);

    // 3. 设置根节点
    planner.setRoot(rel);

    // 4. 寻找最优计划
    return planner.findBestExp();
  }
});
```

## 20.4 一个 SELECT 查询的端到端源码追踪

以 `SELECT name FROM emp WHERE salary > 1000` 为例：

**阶段1：解析**（SqlParser）
```
"SELECT name FROM emp WHERE salary > 1000"
  → SqlSelect(selectList=[SqlIdentifier("name")],
              from=SqlIdentifier("emp"),
              where=SqlBasicCall(>, [SqlIdentifier("salary"), SqlLiteral(1000)]))
```

**阶段2：验证**（SqlValidator）
```
SqlSelect → 验证后:
  name → emp.name (VARCHAR(100))
  salary → emp.salary (DECIMAL(10,2))
  1000 → DECIMAL(10,2)
  > → BOOLEAN
```

**阶段3：转换**（SqlToRelConverter）
```
LogicalProject(name=[$1])
  LogicalFilter(condition=[$5 > 1000])
    LogicalTableScan(table=[emp])
```

**阶段4：优化**（VolcanoPlanner）
```
EnumerableCalc(program: condition=[$5 > 1000], projects=[$1])
  EnumerableTableScan(table=[emp])
```

**阶段5：实现**（EnumerableRelImplementor）
```
生成 Java 类:
  Enumerable<Object[]> enumerate() {
    return tableScan.enumerate()
        .where(row -> (BigDecimal) row[5].compareTo(new BigDecimal(1000)) > 0)
        .select(row -> new Object[]{row[1]});
  }
```

**阶段6：执行**
```
编译 → 加载 → 实例化 → enumerate() → 迭代器 → ResultSet
```

---

## 本章小结

Calcite 的 JDBC 集成从 SQL 字符串到 ResultSet 的完整流程经过六个阶段：解析→验证→转换→优化→实现→执行。Frameworks API 提供了程序化使用 Calcite 的标准方式。理解这个全流程是调试和扩展 Calcite 的基础。
