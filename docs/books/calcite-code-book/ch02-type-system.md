# 第2章：类型系统 — 查询引擎的元语言

## 2.1 为什么类型系统是整个框架最底层的基石

在查询引擎中，类型系统是所有上层建筑的根基：

- **解析器**需要知道哪些字面量是合法的（`DATE '2024-01-01'` 合法，`DATE 'hello'` 不合法）
- **验证器**需要检查操作符的参数类型是否匹配（`INTEGER + VARCHAR` 是否允许？隐式转换为哪种类型？）
- **优化器**需要基于类型信息推导等价变换（`CAST(x AS INT)` 在 x 已经是 INT 时可以消除）
- **代码生成器**需要知道每个表达式的 Java 类型以生成正确的字节码

Calcite 的类型系统横跨两个世界：**SQL 世界**（`SqlTypeName`、`BasicSqlType`）和**关系代数世界**（`RelDataType`、`RelRecordType`）。理解这两个世界之间的映射关系，是读懂 Calcite 源码的钥匙。

## 2.2 RelDataType 体系

`RelDataType` 是关系代数层的类型接口，定义在 `rel/type/RelDataType.java` 中。它是一个"胖接口"——用注释的话说，"不太优雅，但在 Java 泛型出现之前定义的，避免了大量类型转换"。

### 2.2.1 RelDataType 接口

```java
// rel/type/RelDataType.java
public interface RelDataType {
  int SCALE_NOT_SPECIFIED = Integer.MIN_VALUE;
  int PRECISION_NOT_SPECIFIED = -1;

  boolean isStruct();                        // 是否是结构化类型（有字段）
  List<RelDataTypeField> getFieldList();     // 字段列表
  List<String> getFieldNames();              // 字段名列表
  int getFieldCount();                       // 字段数
  StructKind getStructKind();                // 结构类型：如何解析字段
  RelDataTypeField getField(String fieldName, boolean caseSensitive, boolean elideRecord);
  boolean isNullable();                      // 是否可空
  RelDataType getComponentType();            // 集合元素类型（ARRAY/MULTISET）
  RelDataType getKeyType();                  // MAP 的键类型
  RelDataType getValueType();                // MAP 的值类型
  SqlTypeName getSqlTypeName();              // 对应的 SQL 类型名
  int getPrecision();                        // 精度
  int getScale();                            // 标度
  Charset getCharset();                      // 字符集（CHAR/VARCHAR）
  SqlCollation getCollation();               // 排序规则
  RelDataTypeFamily getFamily();             // 类型族
}
```

核心观察：**RelDataType 统一了标量类型和行类型**。一个 `INTEGER` 列的类型是 `RelDataType`（`isStruct()=false`），一行记录 `(id INT, name VARCHAR)` 也是 `RelDataType`（`isStruct()=true`）。

### 2.2.2 继承体系

```
RelDataType (接口)
├── RelDataTypeImpl (抽象类, rel/type/RelDataTypeImpl.java)
│   ├── RelRecordType (行记录类型, rel/type/RelRecordType.java)
│   ├── DynamicRecordTypeImpl (动态行类型, rel/type/DynamicRecordTypeImpl.java)
│   ├── RelCrossType (笛卡尔积类型, rel/type/RelCrossType.java)
│   └── SingleColumnAliasRelDataType (单列别名类型)
│
├── SqlType 体系 (sql/type/)
│   ├── AbstractSqlType
│   │   ├── BasicSqlType (基本类型: INT, VARCHAR, DATE...)
│   │   ├── ArraySqlType
│   │   ├── MapSqlType
│   │   ├── MultisetSqlType
│   │   ├── ObjectSqlType
│   │   ├── IntervalSqlType
│   │   └── MeasureSqlType (MEASURE 类型, 1.42 新增)
│   ├── ApplySqlType
│   │   └── MeasureSqlType
│   └── FunctionSqlType
```

### 2.2.3 RelRecordType — 行类型

`RelRecordType` 是最常见的情况——它表示一行记录的类型。每个字段由 `RelDataTypeField` 描述：

```java
// rel/type/RelDataTypeField.java
public interface RelDataTypeField {
  String getName();           // 字段名
  int getIndex();             // 字段序号（从 0 开始）
  RelDataType getType();      // 字段类型
}
```

行类型由 `RelDataTypeFactory.createStructType()` 创建：

```java
RelDataType rowType = typeFactory.builder()
    .add("id", SqlTypeName.INTEGER)
    .add("name", SqlTypeName.VARCHAR, 100)
    .add("amount", SqlTypeName.DECIMAL, 10, 2)
    .build();
// 结果: RecordType(INTEGER id, VARCHAR(100) name, DECIMAL(10, 2) amount)
```

### 2.2.4 StructKind — 字段解析策略

`StructKind` 枚举决定了如何按名称解析字段，这在嵌套结构中尤为关键：

| StructKind | 含义 | 示例 |
|------------|------|------|
| `NONE` | 非结构化类型 | `INTEGER` |
| `FULLY_QUALIFIED` | 必须全路径引用 | `row.id` |
| `PEEK_FIELDS` | 可穿透嵌套字段引用 | `id` 直接引用嵌套 record 的 `id` 字段 |
| `PEEK_FIELDS_DEFAULT` | 同上，但优先级更低 | 同上，优先级低于 PEEK_FIELDS |
| `PEEK_FIELDS_ONLY` | 只允许穿透引用 | 不允许 `row.id`，只允许 `id` |

PEEK 机制是 Calcite 处理嵌套 Schema 的独特设计——它允许在 SQL 中直接引用嵌套字段，而无需显式路径前缀。

## 2.3 SqlType 系统

SqlType 体系在 `sql/type/` 包中（62 文件），是 SQL 层的类型表示。它与 RelDataType 的关系是：**SqlType 是 SQL 世界的类型，RelDataType 是关系代数世界的类型；SqlTypeFactoryImpl 创建的 SqlType 对象同时也实现 RelDataType 接口。**

### 2.3.1 SqlTypeName — SQL 类型的枚举

`SqlTypeName` 枚举（`sql/type/SqlTypeName.java`）定义了 Calcite 支持的所有 SQL 类型：

```java
public enum SqlTypeName {
  // 布尔
  BOOLEAN(PrecScale.NO_NO, false, Types.BOOLEAN, SqlTypeFamily.BOOLEAN),

  // 精确数值
  TINYINT, SMALLINT, INTEGER, BIGINT,
  UTINYINT, USMALLINT, UINTEGER, UBIGINT,  // 无符号整数
  DECIMAL(PrecScale.YES_YES),               // 有精度和标度

  // 近似数值
  FLOAT, REAL, DOUBLE,

  // 字符串
  CHAR(PrecScale.YES_NO), VARCHAR(PrecScale.YES_NO),

  // 二进制
  BINARY(PrecScale.YES_NO), VARBINARY(PrecScale.YES_NO),

  // 日期时间
  DATE, TIME, TIME_WITH_LOCAL_TIME_ZONE, TIME_TZ,
  TIMESTAMP, TIMESTAMP_WITH_LOCAL_TIME_ZONE, TIMESTAMP_TZ,

  // 间隔
  INTERVAL_YEAR, INTERVAL_YEAR_MONTH, INTERVAL_MONTH,
  INTERVAL_DAY, INTERVAL_DAY_HOUR, ..., INTERVAL_SECOND,

  // 集合
  MULTISET, ARRAY, MAP,

  // 结构化
  ROW, DISTINCT, STRUCTURED,

  // 特殊
  CURSOR, NULL, UNKNOWN, ANY, DYNAMIC_STAR,
  MEASURE, SARG,  // 1.42 新增
  UUID, VARIANT,   // VARIANT 类似于 JSON 的动态类型
  COLUMN_LIST, SYMBOL, GEOMETRY;
}
```

每个 `SqlTypeName` 枚举值携带三个属性：

1. **PrecScale**：该类型是否支持精度/标度。例如 `INTEGER` 是 `NO_NO`（不支持），`DECIMAL` 是 `YES_YES`（都支持）
2. **isSpecial**：是否是特殊类型（如 `NULL`、`ANY`、`DYNAMIC_STAR`）
3. **SqlTypeFamily**：所属类型族

### 2.3.2 SqlTypeFamily — 类型族

`SqlTypeFamily` 是类型的粗粒度分类，用于操作符的类型检查：

| Family | 包含的类型 |
|--------|-----------|
| `NUMERIC` | TINYINT, SMALLINT, INTEGER, BIGINT, DECIMAL, FLOAT, REAL, DOUBLE |
| `EXACT_NUMERIC` | TINYINT, SMALLINT, INTEGER, BIGINT, DECIMAL |
| `APPROXIMATE_NUMERIC` | FLOAT, REAL, DOUBLE |
| `CHARACTER` | CHAR, VARCHAR |
| `BINARY` | BINARY, VARBINARY |
| `DATETIME` | DATE, TIME, TIMESTAMP 及其变体 |
| `BOOLEAN` | BOOLEAN |
| `ARRAY` | ARRAY |
| `MAP` | MAP |
| `ANY` | ANY, DYNAMIC_STAR |

类型族在操作符重载解析中起关键作用——当一个函数可以接受多种类型时，通常以 Family 为单位定义约束。

### 2.3.3 BasicSqlType — 基本类型

`BasicSqlType` 是最核心的类型实现。它承载了精度、标度、字符集、排序规则等所有属性：

```java
// sql/type/BasicSqlType.java
class BasicSqlType extends AbstractSqlType {
  // 精度相关
  private @MonotonicNonNull Integer precision;
  private @MonotonicNonNull Integer scale;

  // 字符串类型相关
  private @MonotonicNonNull Charset charset;
  private @MonotonicNonNull SqlCollation collation;

  // 计算列的 Java 类型（用于代码生成）
  private @Nullable Class<?> javaClass;
}
```

`BasicSqlType` 的关键设计：**不可变 + 工厂模式**。类型对象通过 `SqlTypeFactoryImpl` 创建，并通过 `canonize()` 方法保证唯一性（相同属性的类型是同一个 Java 对象）。这意味着类型比较可以用 `==` 而非 `equals()`。

## 2.4 SQL 类型 → Rel 类型的映射桥梁

理解 Calcite 的类型系统，最关键的是把握两个层次之间的映射关系。

### 2.4.1 统一接口

`BasicSqlType` 同时实现了 `RelDataType` 接口——这意味着一个 SQL `INTEGER` 类型对象同时也是一个 `RelDataType`。这种设计避免了 SQL 层和 Rel 层之间的类型转换开销。

```
SqlParser → SqlNode (携带 SqlTypeName/BasicSqlType)
                          ↓ SqlToRelConverter
              RelNode (携带 RelDataType, 实际是同一个 BasicSqlType 对象)
```

### 2.4.2 TypeFactory 的角色

`RelDataTypeFactory` 是类型创建的统一入口，`SqlTypeFactoryImpl` 是其默认实现：

```java
// 创建行类型
RelDataType rowType = factory.createStructType(
    ImmutableList.of(
        factory.createSqlType(SqlTypeName.INTEGER),
        factory.createSqlType(SqlTypeName.VARCHAR, 100)),
    ImmutableList.of("id", "name"));

// 创建可空类型
RelDataType nullableInt = factory.createTypeWithNullability(
    factory.createSqlType(SqlTypeName.INTEGER), true);

// 创建数组类型
RelDataType arrayType = factory.createArrayType(
    factory.createSqlType(SqlTypeName.VARCHAR), -1);

// 创建 MAP 类型
RelDataType mapType = factory.createMapType(
    factory.createSqlType(SqlTypeName.VARCHAR),
    factory.createSqlType(SqlTypeName.INTEGER));
```

`canonize()` 方法保证类型的唯一性：

```java
// RelDataTypeFactoryImpl.java:446
protected RelDataType canonize(final RelDataType type) {
    // 通过 digest 查找已存在的同类型对象
    // 如果存在则返回已有对象，否则注册新对象
    RelDataType existing = digestToType.putIfAbsent(digest, type);
    return existing != null ? existing : type;
}
```

### 2.4.3 RelDataTypeSystem — 类型系统配置

`RelDataTypeSystem`（`rel/type/RelDataTypeSystem.java`）定义了类型系统的边界参数：

```java
public interface RelDataTypeSystem {
  int getMaxPrecision(SqlTypeName typeName);    // 最大精度
  int getMaxScale(SqlTypeName typeName);        // 最大标度
  int getDefaultPrecision(SqlTypeName typeName); // 默认精度
  int getMinScale(SqlTypeName typeName);        // 最小标度
  boolean isAutoincrement(SqlTypeName typeName); // 是否支持自增
  boolean isSchemaCaseSensitive();              // Schema 名称是否大小写敏感
  RelDataType deriveDecimalMultiplyType(...);   // DECIMAL 乘法结果类型
  RelDataType deriveDecimalDivideType(...);     // DECIMAL 除法结果类型
  // ...
}
```

默认实现 `RelDataTypeSystem.DEFAULT` 遵循 SQL 标准。Hive、Spark 等项目可以通过实现此接口来自定义类型边界（如 Hive 的 `DECIMAL` 最大精度为 38 而非标准的 19）。

## 2.5 类型强转（Type Coercion）的完整实现

类型强转是类型系统中最复杂的部分——当不同类型的表达式出现在同一上下文时，如何决定隐式转换到哪种类型？

### 2.5.1 三层规则体系

Calcite 的类型转换规则分为三层：

| 层次 | 类 | 含义 |
|------|-----|------|
| 赋值规则 | `SqlTypeAssignmentRule` (296行) | 值能否赋给目标类型？最严格的层 |
| 强转规则 | `SqlTypeCoercionRule` (415行) | 值能否显式 CAST 到目标类型？赋值规则的超集 |
| 隐式强转 | 分散在各验证逻辑中 | 在特定上下文中能否隐式转换？强转规则的子集 |

赋值规则的核心——数值类型的提升链：

```java
// SqlTypeAssignmentRule.java 中的隐式规则
// TINYINT 可以赋给 TINYINT（自身）
// SMALLINT 可以赋给 TINYINT, SMALLINT
// INTEGER 可以赋给 TINYINT, SMALLINT, INTEGER
// BIGINT 可以赋给 TINYINT, SMALLINT, INTEGER, BIGINT
// DECIMAL 可以赋给所有数值类型
```

强转规则在赋值规则基础上扩展了**双向数值转换**和**跨族转换**：

```java
// SqlTypeCoercionRule.java 的扩展
// 1. 数值类型之间对称可转（TINYINT ↔ BIGINT）
// 2. VARCHAR/CHAR 可以转数值（如 CAST('123' AS INT)）
// 3. TIMESTAMP 可以转 VARCHAR
// 4. DATE/TIME 可以转 TIMESTAMP
```

### 2.5.2 leastRestrictive — 类型推导的核心算法

当多个不同类型的值出现在同一上下文（如 `CASE WHEN ... THEN 1 ELSE 1.5 END`）时，`leastRestrictive()` 方法决定最通用类型：

```java
// SqlTypeFactoryImpl.java:185
@Override public @Nullable RelDataType leastRestrictive(
    List<RelDataType> types, SqlTypeMappingRule mappingRule) {
  // 1. 所有类型相同 → 直接返回
  // 2. 所有类型在同一族内 → 取族内最宽类型
  //    NUMERIC 族: TINYINT < SMALLINT < INTEGER < BIGINT < DECIMAL < FLOAT/REAL/DOUBLE
  //    CHARACTER 族: CHAR < VARCHAR
  // 3. 跨族 → 通过显式 CAST 路径推导
  //    如 INTEGER 和 VARCHAR → DECIMAL（因为两者都可以 CAST 为 DECIMAL）
  // 4. 无法推导 → 返回 null（类型不兼容）
}
```

### 2.5.3 返回类型推断策略

SQL 操作符的返回类型推断由 `ReturnTypes`（`sql/type/ReturnTypes.java`）定义：

| 策略 | 含义 | 示例 |
|------|------|------|
| `ARG0` | 返回第一个参数类型 | `COALESCE(a, b)` → a 的类型 |
| `ARG0_FORCE_NULLABLE` | 返回第一个参数类型，但强制可空 | `CAST(x AS INT)` |
| `BIGINT` | 固定返回 BIGINT | `COUNT(*)` |
| `VARCHAR_2000` | 固定返回 VARCHAR(2000) | `UPPER(s)` |
| `LEAST_RESTRICTIVE` | 取所有参数的最通用类型 | `CASE WHEN ... THEN ... END` |
| `CASCADE` | 与第一个参数同类型 | `SUBSTRING(s, n)` → s 的类型 |
| `DECIMAL_SCALE0` | 返回 DECIMAL，标度为 0 | `ROUND(x)` |
| `ARG0_INT` | 第一个参数的类型，但精度按 INT | `EXTRACT(YEAR FROM d)` → INTEGER |
| `DOUBLE` | 固定返回 DOUBLE | `SQRT(x)` |
| `DYNAMIC` | 运行时确定 | 动态类型函数 |

这些策略通过 `SqlReturnTypeInference` 函数式接口组合：

```java
// 算术运算的返回类型推断
SqlStdOperatorTable.PLUS = SqlBasicOperator.create("+")
    .withReturnTypeInference(ReturnTypes.DECIMAL_SUM);  // 精确数值求和

SqlStdOperatorTable.CONCAT = SqlBasicOperator.create("||")
    .withReturnTypeInference(ReturnTypes.DYADIC_STRING_SUM);  // 字符串拼接
```

### 2.5.4 操作数类型检查

`OperandTypes`（`sql/type/OperandTypes.java`）定义了操作符参数的类型约束：

| 检查器 | 含义 |
|--------|------|
| `NUMERIC` | 所有参数必须是数值 |
| `STRING` | 所有参数必须是字符串 |
| `SAME_SAME` | 所有参数类型必须相同 |
| `SAME_VARIADIC` | 可变参数，所有参数类型必须相同 |
| `ANY` | 接受任意类型 |
| `NUMERIC_NUMERIC` | 恰好两个数值参数 |
| `CHARACTER_CHARACTER` | 恰好两个字符串参数 |
| `or(type1, type2)` | 任一类型即可 |
| `family(FAMILY)` | 指定类型族 |

检查器与推断器的配合：**先检查参数类型是否合法，再推断返回类型**。这个两步过程在 `SqlOperator.checkOperandTypes()` → `SqlOperator.inferReturnType()` 中完成。

## 2.6 时间帧（TimeFrame）系统

Calcite 1.42 引入了 `TimeFrame` 抽象，这是一个值得关注的新设计。

### 2.6.1 问题背景

在 SQL 中，时间粒度之间的转换是模糊的——1 个月不总是 30 天，1 年不总是 365 天。传统上，Calcite 用 `SqlIntervalQualifier` 表示时间间隔，但缺乏精确的粒度间换算机制。

### 2.6.2 TimeFrame 接口

```java
// rel/type/TimeFrame.java
public interface TimeFrame {
  TimeFrameSet frameSet();                          // 所属的时间帧集合
  String name();                                    // 名称: SECOND, MINUTE, HOUR, DAY, WEEK...
  @Nullable BigFraction per(TimeFrame timeFrame);   // 换算比率: MONTH.per(YEAR) = 1/12
  default int dateEpoch();                          // 时间帧的起始日期（epoch 值）
}
```

`per()` 方法是核心——它返回两个时间帧之间的精确比率：

```
MINUTE.per(HOUR)  = 1/60    (1分钟 = 1/60小时)
HOUR.per(DAY)     = 1/24    (1小时 = 1/24天)
DAY.per(WEEK)     = 1/7     (1天 = 1/7周)
MONTH.per(YEAR)   = 1/12    (1月 = 1/12年)
```

### 2.6.3 TimeFrameSet 与 CORE 集合

`TimeFrameSet` 是一组相关联的 TimeFrame 的集合。`TimeFrames.CORE` 是 Calcite 内置的标准集合：

```
SECOND → MINUTE → HOUR → DAY → WEEK (起始于周日)
MONTH → QUARTER → YEAR → DECADE → CENTURY → MILLENNIUM
ISOYEAR → ISOWEEK (起始于周一) → ISODOW
```

两棵树：一棵是精确换算的（秒→分→时→日→周），另一棵是近似换算的（月→季→年）。月和日之间的转换是不精确的——这正是 TimeFrame 用 `BigFraction`（分数）而非整数表示比率的原因。

### 2.6.4 TimeFrame 的应用

TimeFrame 目前主要用于 `EXTRACT`、`DATE_TRUNC`、窗口帧定义等场景中，提供比传统 `TimeUnit` 更精确的粒度间换算。未来可能扩展到更多时间相关优化中。

## 2.7 从源码理解：类型系统的设计精髓

### 2.7.1 Canonization 模式

类型对象的规范化（Canonization）是 Calcite 类型系统最重要的性能优化。通过 `canonize()` 方法，相同属性的类型共享同一个 Java 对象：

```java
// 效果: 类型比较可以用 ==
RelDataType t1 = factory.createSqlType(SqlTypeName.INTEGER);
RelDataType t2 = factory.createSqlType(SqlTypeName.INTEGER);
assert t1 == t2;  // 同一个对象！

// 不同的类型当然不同
RelDataType t3 = factory.createSqlType(SqlTypeName.BIGINT);
assert t1 != t3;
```

这避免了在整个优化过程中反复调用 `equals()` 的开销。`digest` 字符串是规范化的键——它是一个类型的紧凑文本表示，如 `INTEGER`、`VARCHAR(100) NOT NULL`、`RecordType(INTEGER id, VARCHAR(100) name)`。

### 2.7.2 不可变性

类型对象一旦创建就不可修改。需要新属性时（如添加可空性），创建新对象：

```java
// 错误方式：类型对象不可修改
// type.setNullable(true);  // 不存在此方法

// 正确方式：创建新类型
RelDataType nullableType = factory.createTypeWithNullability(type, true);
```

不可变性保证了类型对象可以安全地在整个查询处理管线中传递和共享，无需担心意外修改。

### 2.7.3 类型系统的扩展点

Calcite 类型系统的可扩展性体现在三个层面：

1. **RelDataTypeSystem**：自定义类型边界（精度上限、DECIMAL 运算规则）
2. **SqlTypeCoercionRule**：自定义隐式类型转换规则
3. **SqlReturnTypeInference / SqlOperandTypeChecker**：自定义函数的参数和返回类型

这种扩展性让 Hive、Spark、Flink 等项目可以在不修改 Calcite 核心代码的情况下适配各自的类型语义。

---

## 本章小结

Calcite 的类型系统是一个双层统一设计：SQL 层的 `SqlTypeName`/`BasicSqlType` 和关系代数层的 `RelDataType` 共享同一个类型对象。三层类型转换规则（赋值→强转→隐式强转）定义了类型兼容性的边界，`leastRestrictive` 算法是类型推导的核心。Canonization 和不可变性是性能与安全的基石。TimeFrame 系统是 Calcite 1.42 的新抽象，为时间粒度换算提供了更精确的基础。

理解了类型系统，下一章我们将进入 SQL 解析的世界——看 Calcite 如何将 SQL 文本转化为承载这些类型的 SqlNode AST。
