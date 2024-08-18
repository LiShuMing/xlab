# 第15章：Schema 体系 — 元数据的组织与管理

## 15.1 Schema 接口层次

Schema 是 Calcite 元数据组织的核心抽象——它描述了数据源的命名空间。

```java
// schema/Schema.java
public interface Schema {
  Table getTable(String name);                        // 按名获取表
  Set<String> getTableNames();                        // 所有表名
  Schema getSubSchema(String name);                   // 子 Schema
  Set<String> getSubSchemaNames();                    // 子 Schema 名
  Function getFunction(String name);                  // 按名获取函数
  Set<String> getFunctionNames();                     // 所有函数名
  RelDataType getType(String name);                   // 自定义类型
  Set<String> getTypeNames();                         // 类型名
  boolean isMutable();                                // 是否可变
  Schema snapshot(SchemaVersion version);              // 快照
}
```

`SchemaPlus` 扩展了 Schema，添加了可写能力：

```java
// schema/SchemaPlus.java
public interface SchemaPlus extends Schema {
  SchemaPlus add(String name, Schema schema);         // 添加子 Schema
  void add(String name, Table table);                 // 添加表
  void add(String name, Function function);           // 添加函数
  boolean removeTable(String name);                   // 移除表
  void setPath(ImmutableList<String> path);           // 设置搜索路径
  void setCacheEnabled(boolean enable);               // 启用缓存
}
```

### Schema 的实现类

| 类 | 用途 |
|----|------|
| `AbstractSchema` | 基础实现，返回空表/函数集合 |
| `DelegatingSchema` | 委托给另一个 Schema |
| `CalciteSchema` | Calcite 内部的 Schema 包装 |
| `CachingCalciteSchema` | 带缓存的 Schema |
| `SimpleCalciteSchema` | 简单实现 |
| `CalciteRootSchema` | 根 Schema |

## 15.2 Table 接口族

Table 接口定义了表的基本属性，并通过子接口声明表的能力梯度：

```
Table (基础接口)
├── getRowType()          — 行类型
├── getStatistic()        — 统计信息
└── getJdbcTableType()   — JDBC 表类型

能力梯度（由弱到强）：
ScannableTable           — 全表扫描
FilterableTable          — 支持谓词下推
ProjectableFilterableTable — 支持投影+谓词下推
QueryableTable           — 支持表达式查询
TranslatableTable        — 支持转换为 RelNode
```

### 15.2.1 ScannableTable — 最弱的能力

```java
// schema/ScannableTable.java
public interface ScannableTable extends Table {
  Enumerable<Object[]> scan(DataSet root);  // 返回全表数据的 Enumerable
}
```

全表扫描，无法下推任何操作。Calcite 会在 Scan 之上添加 Filter、Project 等算子。

### 15.2.2 FilterableTable — 谓词下推

```java
// schema/FilterableTable.java
public interface FilterableTable extends Table {
  Enumerable<Object[]> scan(DataSet root, List<RexNode> filters);
}
```

表可以接受部分过滤条件。**如果表不能接受某个条件，可以从 filters 列表中移除并返回，Calcite 会添加额外的 Filter 算子**。

### 15.2.3 TranslatableTable — 转换为 RelNode

```java
// schema/TranslatableTable.java
public interface TranslatableTable extends Table {
  RelNode toRel(RelOptTable.ToRelContext context, RelOptTable relOptTable);
}
```

表可以自定义其逻辑计划表示——例如将表扫描转换为特定的算子树（如 Elasticsearch 的查询 DSL）。

## 15.3 函数注册

### 15.3.1 函数类型

| 接口 | 用途 | 示例 |
|------|------|------|
| `ScalarFunction` | 标量函数 | `UPPER(s)`, `ABS(x)` |
| `AggregateFunction` | 聚合函数 | `MY_SUM(x)` |
| `TableFunction` | 表函数 | `GENERATE_SERIES(1, 10)` |
| `TableMacro` | 表宏（参数化视图） | `VIEW(dept_id)` |

### 15.3.2 反射式函数注册

Calcite 通过反射发现函数的参数和返回类型：

```java
// schema/impl/ScalarFunctionImpl.java
public class ScalarFunctionImpl implements ScalarFunction {
  // 从一个 Java 方法创建标量函数
  public static ScalarFunction create(Class<?> clazz, String methodName) {
    Method method = clazz.getMethod(methodName, ...);
    return new ScalarFunctionImpl(method);
  }
}

// 使用示例
SchemaPlus schema = ...
schema.add("MY_UPPER",
    ScalarFunctionImpl.create(MyFunctions.class, "myUpper"));

public class MyFunctions {
  public static String myUpper(String s) { return s.toUpperCase(); }
}
```

### 15.3.3 TableMacro — 参数化视图

TableMacro 是最强大的函数类型——它返回一个 Table，可以用于参数化视图：

```java
// schema/TableMacro.java
public interface TableMacro extends Function {
  Table apply(List<? extends Object> arguments);
}
```

## 15.4 CalciteSchema — 内部 Schema 管理

Calcite 内部使用 `CalciteSchema` 而非 `Schema` 直接：

```java
// jdbc/CalciteSchema.java
public abstract class CalciteSchema {
  final Schema schema;
  final String name;
  final Map<String, CalciteSchema> subSchemas;
  final Map<String, TableEntry> tables;
  final Map<String, FunctionEntry> functions;
  final Map<String, LatticeEntry> lattices;
  final Map<String, MaterializationEntry> materializations;
}
```

`CalciteSchema` 添加了缓存、类型包装和 Schema 搜索路径支持。

## 15.5 Schema 搜索路径

Calcite 支持 SQL 标准的 Schema 搜索路径：

```java
// 连接配置中设置搜索路径
Properties info = new Properties();
info.setProperty("schema", "sales,hr");  // 先搜索 sales，再搜索 hr
Connection conn = DriverManager.getConnection(url, info);
```

搜索路径影响名称解析——未限定的表名 `emp` 会依次在 `sales` 和 `hr` Schema 中查找。

---

## 本章小结

Schema 体系通过能力梯度（ScannableTable → FilterableTable → ProjectableFilterableTable → TranslatableTable）渐进式地支持数据源的智能程度。函数注册通过反射机制自动推导参数和返回类型。CalciteSchema 是内部的 Schema 包装，提供缓存和搜索路径支持。下一章将深入适配器架构。
