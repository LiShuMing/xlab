# 第3章：SQL Parser — 文法驱动的基础设施

## 3.1 JavaCC 语法文件解析

Calcite 的 SQL 解析器由 JavaCC（Java Compiler Compiler）生成。JavaCC 是一个自顶向下的 LL(k) 解析器生成器，它读取 `.jj` 语法定义文件，生成 Java 源码的递归下降解析器。

### 3.1.1 模板系统：FMPP + FreeMarker + JavaCC

Calcite 的 Parser 不是直接维护一个 `.jj` 文件，而是通过三层模板系统生成：

```
config.fmpp (FMPP 配置)
  → templates/Parser.jj (FreeMarker 模板 + JavaCC 语法)
    → target/generated-sources/fmpp/javacc/Parser.jj (纯 JavaCC 文件)
      → JavaCC 编译
        → SqlParserImpl.java (最终解析器实现)
```

为什么需要这种间接层？因为 **Calcite 允许下游项目扩展语法**。模板系统提供了注入点：

- `parserImpls.ftl`：注入自定义语句解析方法
- `compoundIdentifier.ftl`：注入复合标识符解析逻辑
- `config.fmpp` 中的 `implementationFiles` 列表：指定要注入的文件

核心语法模板位于 `core/src/main/codegen/templates/Parser.jj`，是一个 9432 行的巨型文件。

### 3.1.2 Parser.jj 的结构

```javacc
// Parser.jj 顶部
options {
  STATIC = false;
  USER_TOKEN_MANAGER = true;
  // ...
}

PARSER_BEGIN(${parser.class})  // FreeMarker 变量，默认为 SqlParserImpl
public class ${parser.class} extends SqlAbstractParserImpl {
  // Java 代码区：辅助方法、静态常量
  private static final SqlLiteral LITERAL_ZERO = ...;
  private static final SqlLiteral LITERAL_ONE = ...;

  public SqlNode parseSqlExpressionEof() throws Exception { ... }
  public SqlNode parseSqlStmtEof() throws Exception { ... }
  public SqlNodeList parseSqlStmtList() throws Exception { ... }
}
PARSER_END(${parser.class})

// 词法规则
TOKEN:
{
  < SELECT: "SELECT" >
| < FROM: "FROM" >
| < WHERE: "WHERE" >
| ...
}

// 语法规则（递归下降）
SqlNode SqlStmtEof() : { ... }
{
  SqlStmt() <EOF>
}

SqlNode SqlStmt() : { ... }
{
  SqlSelect()
| SqlInsert()
| SqlDelete()
| SqlUpdate()
| SqlMerge()
| ...
}

SqlSelect SqlSelect() : {
  SqlNodeList selectList;
  SqlNode from;
  SqlNode where;
  ...
}
{
  <SELECT> SqlSelectKeywords(keywords) selectList = SqlSelectList()
  [ <FROM> from = FromClause() ]
  [ <WHERE> where = SqlExpression(ExprContext.ACCEPT_SUBQUERY) ]
  ...
  {
    return new SqlSelect(pos, keywords, selectList, from, where, ...);
  }
}
```

关键观察：**每条语法规则的返回值是一个 SqlNode**。这意味着解析过程直接构建了 SQL AST，不需要额外的树构建阶段。

### 3.1.3 FMPP 配置详解

`config.fmpp` 定义了解析器的可定制参数：

```fmpp
data: {
  parser: {
    package: "org.apache.calcite.sql.parser.impl",
    class: "SqlParserImpl",
    implementationFiles: [
      "parserImpls.ftl"     // 自定义语句解析方法
    ]
  }
}

freemarkerLinks: {
  includes: includes/        // 模板注入点目录
}
```

下游项目（如 Babel）通过修改此配置来注入自己的语法：

```fmpp
// babel/src/main/codegen/config.fmpp
data: {
  parser: {
    package: "org.apache.calcite.sql.parser.impl",
    class: "SqlBabelParserImpl",
    implementationFiles: [
      "parserImpls.ftl",
      "parserPostgresImpls.ftl"   // 额外注入 PostgreSQL 方言语法
    ]
  }
}
```

## 3.2 SqlParser 入口

### 3.2.1 创建与使用

`SqlParser` 是解析器的公共入口，它封装了底层的 `SqlAbstractParserImpl` 实现：

```java
// sql/parser/SqlParser.java
public class SqlParser {
  private final SqlAbstractParserImpl parser;

  private SqlParser(SqlAbstractParserImpl parser, Config config) {
    this.parser = parser;
    parser.setTabSize(1);
    parser.setQuotedCasing(config.quotedCasing());
    parser.setUnquotedCasing(config.unquotedCasing());
    parser.setIdentifierMaxLength(config.identifierMaxLength());
    parser.setConformance(config.conformance());
    parser.switchTo(SqlAbstractParserImpl.LexicalState.forConfig(config));
  }

  public static SqlParser create(String sql, Config config) {
    return create(new SourceStringReader(sql), config);
  }

  // 解析单条语句
  public SqlNode parseStmt() throws SqlParseException { ... }

  // 解析表达式
  public SqlNode parseExpression() throws SqlParseException { ... }

  // 解析语句列表
  public SqlNodeList parseStmtList() throws SqlParseException { ... }
}
```

### 3.2.2 Config — 解析器配置

`SqlParser.Config` 是 Immutables 风格的配置接口，控制解析行为：

| 配置项 | 默认值 | 含义 |
|--------|--------|------|
| `identifierMaxLength` | 128 | 标识符最大长度 |
| `quotedCasing` | UNCHANGED | 引号内标识符大小写 |
| `unquotedCasing` | TO_UPPER | 非引号标识符大小写 |
| `quoting` | DOUBLE_QUOTE | 引号字符：`"` vs `` ` `` vs `[` |
| `caseSensitive` | true | 是否大小写敏感 |
| `conformance` | DEFAULT | SQL 兼容性级别 |
| `parserFactory` | 默认 | 自定义解析器工厂 |
| `charLiteralStyles` | STANDARD | 字符字面量风格 |
| `timeUnitCodes` | 空 | 时间单位缩写映射 |

### 3.2.3 Lex — 预置词法配置

Calcite 预置了几种常见数据库的词法配置：

```java
// config/Lex.java
public enum Lex {
  ORACLE(      DOUBLE_QUOTE, TO_UPPER, UNCHANGED, true),  // Oracle 风格
  MYSQL(       BACK_TICK,    TO_UPPER, UNCHANGED, false),  // MySQL 风格
  MYSQL_ANSI(  DOUBLE_QUOTE, TO_UPPER, UNCHANGED, false),  // MySQL ANSI 模式
  SQL_SERVER(  BRACKET,      TO_UPPER, UNCHANGED, false),  // SQL Server 风格
  JAVA(        DOUBLE_QUOTE, TO_UPPER, UNCHANGED, true),   // Java 风格
}
```

使用示例：

```java
// Oracle 风格：双引号标识符，非引号标识符转大写
SqlParser parser = SqlParser.create(sql,
    SqlParser.config().withLex(Lex.ORACLE));

// MySQL 风格：反引号标识符
SqlParser parser = SqlParser.create(sql,
    SqlParser.config().withLex(Lex.MYSQL));
```

## 3.3 SqlNode 体系：SQL AST 的完整类型系统

解析器的输出是 `SqlNode` 树——SQL 语句的抽象语法树。理解 SqlNode 的类型体系是理解整个 SQL 处理管线的基础。

### 3.3.1 SqlNode — AST 基类

```java
// sql/SqlNode.java
public abstract class SqlNode implements Cloneable {
  protected final SqlParserPos pos;  // 源码位置（行号、列号、结束位置）

  public abstract SqlKind getKind();     // 节点类型
  public abstract SqlNode clone(SqlParserPos pos);  // 深拷贝

  public SqlNode accept(SqlVisitor<@Nullable R> visitor) { ... }  // 访问者模式
  public void validate(SqlValidator validator, SqlValidatorScope scope) { ... }
}
```

每个 SqlNode 都携带 `SqlParserPos`，这让 Calcite 能够在错误消息中精确定位问题所在。

### 3.3.2 SqlNode 的四大子类

SqlNode 的直接子类构成了 SQL AST 的四种基本形态：

```
SqlNode (abstract)
├── SqlCall        — 函数调用/复合表达式（最核心的子类）
├── SqlLiteral     — 字面量
├── SqlIdentifier  — 标识符（表名、列名等）
└── SqlNodeList    — 节点列表（SELECT 列表、GROUP BY 列表等）
```

**SqlCall** 是最重要的子类——几乎所有 SQL 结构都是 SqlCall：

```java
// sql/SqlCall.java
public abstract class SqlCall extends SqlNode {
  public abstract SqlOperator getOperator();      // 操作符
  public abstract List<SqlNode> getOperandList(); // 操作数
  public abstract void setOperand(int i, @Nullable SqlNode operand);
}
```

SqlCall 的设计精妙之处在于：**它将结构（子节点列表）和行为（操作符）分离**。`getOperator()` 返回的 `SqlOperator` 定义了此节点的语义——名称、参数类型、返回类型、如何 unparse 回 SQL 字符串等。

**SqlBasicCall** 是 SqlCall 的通用实现：

```java
// sql/SqlBasicCall.java
public class SqlBasicCall extends SqlCall {
  private SqlOperator operator;
  private SqlNode[] operands;  // 操作数数组

  @Override public SqlOperator getOperator() { return operator; }
  @Override public List<SqlNode> getOperandList() { return ImmutableList.copyOf(operands); }
}
```

### 3.3.3 特化的 SqlCall 子类

虽然 `SqlBasicCall` 可以表示任何调用，但 Calcite 为重要 SQL 结构定义了特化子类，携带更丰富的结构信息：

| 类 | 语义 | 关键字段 |
|----|------|---------|
| `SqlSelect` | SELECT 语句 | selectList, from, where, groupBy, having, orderBy, offset, fetch, hints |
| `SqlJoin` | JOIN 子句 | left, natural, joinType, right, conditionType, condition |
| `SqlInsert` | INSERT 语句 | targetTable, source, columnList |
| `SqlDelete` | DELETE 语句 | targetTable, condition |
| `SqlUpdate` | UPDATE 语句 | targetTable, sourceExpressionList, condition |
| `SqlMerge` | MERGE 语句 | targetTable, source, condition, insertList, updateList |
| `SqlOrderBy` | ORDER BY | query, orderByList, offset, fetch |
| `SqlWith` | WITH (CTE) | withItemList, body |
| `SqlWindow` | WINDOW 定义 | partitionList, orderList, lowerBound, upperBound |
| `SqlMatchRecognize` | MATCH_RECOGNIZE | pattern, measures, subsetList, definitions |
| `SqlPivot` | PIVOT | pivotColumns, aggregateList, valueList |
| `SqlUnpivot` | UNPIVOT | measureList, axisList |
| `SqlSnapshot` | AS OF | table, period |
| `SqlHint` | Hint | name, optionList |
| `SqlLambda` | Lambda 表达式 (1.42) | parameters, expression |

以 `SqlSelect` 为例，它有明确命名的字段而非通用的操作数数组：

```java
// sql/SqlSelect.java
public class SqlSelect extends SqlCall {
  public static final int FROM_OPERAND = 2;
  public static final int WHERE_OPERAND = 3;
  public static final int HAVING_OPERAND = 5;

  SqlNodeList keywordList;      // DISTINCT, ALL, etc.
  SqlNodeList selectList;       // SELECT 后的列
  @Nullable SqlNode from;       // FROM 子句
  @Nullable SqlNode where;      // WHERE 条件
  @Nullable SqlNodeList groupBy; // GROUP BY 列
  @Nullable SqlNode having;     // HAVING 条件
  SqlNodeList windowDecls;      // WINDOW 定义
  @Nullable SqlNode qualify;    // QUALIFY 条件
  @Nullable SqlNodeList orderBy; // ORDER BY 列
  @Nullable SqlNode offset;     // OFFSET
  @Nullable SqlNode fetch;      // FETCH/LIMIT
  @Nullable SqlNodeList hints;  // 查询提示
}
```

### 3.3.4 SqlLiteral — 字面量体系

`SqlLiteral` 是所有字面量的基类：

```java
// sql/SqlLiteral.java
public class SqlLiteral extends SqlNode {
  private final @Nullable Object value;   // 值
  private final RelDataType type;          // 类型
}
```

特化子类处理不同类型的字面量：

| 子类 | 示例 |
|------|------|
| `SqlNumericLiteral` | `42`, `3.14`, `DECIMAL '9.99'` |
| `SqlCharStringLiteral` | `'hello'`, `N'你好'` |
| `SqlBinaryStringLiteral` | `X'4D7953514C'` |
| `SqlDateLiteral` | `DATE '2024-01-01'` |
| `SqlTimeLiteral` | `TIME '12:34:56'` |
| `SqlTimestampLiteral` | `TIMESTAMP '2024-01-01 12:34:56'` |
| `SqlIntervalLiteral` | `INTERVAL '1' YEAR`, `INTERVAL '3:30' HOUR TO MINUTE` |
| `SqlUuidLiteral` | `UUID '12345678-1234-1234-1234-123456789012'` |

### 3.3.5 SqlIdentifier — 标识符

```java
// sql/SqlIdentifier.java
public class SqlIdentifier extends SqlNode {
  private final ImmutableList<String> names;  // 限定名的各部分
  // 如 "schema.table.column" → ["schema", "table", "column"]
  private final SqlCollation collation;
  private final @Nullable SqlParserPos componentPositions;
}
```

### 3.3.6 SqlKind — 节点类型枚举

`SqlKind` 是一个 1884 行的巨型枚举，定义了 200+ 种 SQL 节点类型。它提供了比 `instanceof` 更高效的类型判断：

```java
// 常见的 SqlKind 值
SELECT, INSERT, DELETE, UPDATE, MERGE,        // DML
UNION, INTERSECT, MINUS,                      // 集合运算
JOIN, INNER_JOIN, LEFT_JOIN, RIGHT_JOIN, FULL_JOIN,  // Join 类型
FILTER, PROJECT, AGGREGATE, SORT,             // 逻辑算子映射
LITERAL, IDENTIFIER,                          // 基本节点
CAST, TRIM, FLOOR, CEIL, EXTRACT, POSITION,   // 函数
PLUS, MINUS, TIMES, DIVIDE, MOD,              // 算术运算
EQUALS, NOT_EQUALS, GREATER_THAN, LESS_THAN,  // 比较运算
AND, OR, NOT,                                 // 逻辑运算
IN, EXISTS, SCALAR_QUERY,                     // 子查询
OVER, WINDOW,                                 // 窗口函数
WITH, WITH_ITEM,                              // CTE
OTHER                                         // 兜底
```

`SqlKind` 的分组机制允许批量判断：

```java
// 判断是否属于 DML
sqlNode.getKind().belongsTo(SqlKind.DML)

// 判断是否属于比较运算
sqlNode.getKind().belongsTo(SqlKind.COMPARISON)

// 判断是否属于集合运算
sqlNode.getKind().belongsTo(SqlKind.SET_QUERY)
```

### 3.3.7 SqlOperator — 操作符体系

每个 SqlCall 都有一个 `SqlOperator`，它定义了该调用的语义：

```java
// sql/SqlOperator.java
public abstract class SqlOperator {
  String name;                         // 操作符名称
  SqlKind kind;                        // 类型
  SqlSyntax syntax;                    // 语法形式
  SqlOperandCountRange operandCountRange;  // 操作数数量范围

  // 类型系统
  SqlReturnTypeInference returnTypeInference;    // 返回类型推断
  SqlOperandTypeInference operandTypeInference;  // 操作数类型推断
  SqlOperandTypeChecker operandTypeChecker;      // 操作数类型检查

  // 核心方法
  public abstract RelDataType deriveType(SqlValidator validator, SqlValidatorScope scope, SqlCall call);
  public void validateCall(SqlCall call, SqlValidator validator, ...);
  public void unparse(SqlWriter writer, SqlCall call, ...);
}
```

SqlOperator 的继承体系：

```
SqlOperator (abstract)
├── SqlFunction              — 函数（有参数列表）
│   ├── SqlAggFunction       — 聚合函数
│   ├── SqlBasicFunction     — 基本函数
│   ├── SqlUnresolvedFunction — 未解析函数
│   └── SqlUserDefinedFunction — 用户自定义函数
├── SqlBinaryOperator        — 二元运算符 (a + b)
├── SqlPrefixOperator        — 前缀运算符 (-x, NOT x)
├── SqlPostfixOperator       — 后缀运算符 (x IS NULL)
├── SqlInfixOperator         — 中缀运算符 (a BETWEEN b AND c)
├── SqlSpecialOperator       — 特殊操作符 (CASE, CAST, EXTRACT)
└── SqlInternalOperator      — 内部操作符（不在 SQL 中出现）
```

### 3.3.8 SqlStdOperatorTable — 标准操作符注册表

`SqlStdOperatorTable`（`sql/fun/SqlStdOperatorTable.java`）注册了 Calcite 支持的所有标准 SQL 操作符。它是一个巨大的类，包含数百个静态字段：

```java
// sql/fun/SqlStdOperatorTable.java (部分)
public class SqlStdOperatorTable extends ReflectiveSqlOperatorTable {
  // 算术运算
  public static final SqlBinaryOperator PLUS = ...;
  public static final SqlBinaryOperator MINUS = ...;
  public static final SqlBinaryOperator MULTIPLY = ...;
  public static final SqlBinaryOperator DIVIDE = ...;

  // 比较运算
  public static final SqlBinaryOperator EQUALS = ...;
  public static final SqlBinaryOperator NOT_EQUALS = ...;
  public static final SqlBinaryOperator GREATER_THAN = ...;

  // 逻辑运算
  public static final SqlBinaryOperator AND = ...;
  public static final SqlBinaryOperator OR = ...;
  public static final SqlPrefixOperator NOT = ...;

  // 聚合函数
  public static final SqlCountAggFunction COUNT = ...;
  public static final SqlSumAggFunction SUM = ...;
  public static final SqlAvgAggFunction AVG = ...;
  public static final SqlMinMaxAggFunction MIN = ...;
  public static final SqlMinMaxAggFunction MAX = ...;

  // 特殊操作符
  public static final SqlSpecialOperator CASE = ...;
  public static final SqlSpecialOperator CAST = ...;
  public static final SqlSpecialOperator EXTRACT = ...;

  // 窗口函数
  public static final SqlRankFunction ROW_NUMBER = ...;
  public static final SqlRankFunction RANK = ...;
  public static final SqlRankFunction DENSE_RANK = ...;

  // 集合运算
  public static final SqlSetOperator UNION = ...;
  public static final SqlSetOperator UNION_ALL = ...;
  public static final SqlSetOperator INTERSECT = ...;
  public static final SqlSetOperator MINUS = ...;
}
```

`ReflectiveSqlOperatorTable` 使用反射自动发现所有 `public static SqlOperator` 字段并注册到操作符查找表中。

## 3.4 Babel 模块：多方言解析的扩展机制

Babel 模块是 Calcite 的多方言解析器扩展，它通过 FMPP 模板注入机制在标准解析器基础上添加各数据库特有的语法。

### 3.4.1 Babel 的结构

```
babel/src/main/codegen/
├── config.fmpp                      — Babel 专属 FMPP 配置
└── includes/
    ├── parserImpls.ftl              — 通用方言扩展
    └── parserPostgresImpls.ftl      — PostgreSQL 方言扩展

babel/src/main/java/org/apache/calcite/sql/babel/
├── SqlBabelCreateTable.java         — 扩展的 CREATE TABLE
└── postgres/
    ├── SqlBegin.java                — BEGIN 事务
    ├── SqlCommit.java               — COMMIT
    ├── SqlRollback.java             — ROLLBACK
    ├── SqlShow.java                 — SHOW 命令
    └── SqlSetOptions.java           — SET 命令
```

### 3.4.2 方言语法注入示例

`parserPostgresImpls.ftl` 向解析器注入 PostgreSQL 特有语法：

```ftl
<#-- PostgreSQL SHOW 命令 -->
SqlNode SqlShowTables()
{
  SqlIdentifier db;
}
{
  <SHOW> <TABLES> [ <FROM> db = SimpleIdentifier() ]
  {
    return new SqlShow(pos, SqlShow.Scope.TABLES, null, db);
  }
}
```

## 3.5 扩展 Parser 的三种方式

### 3.5.1 方式一：FMPP includes 注入

这是 Calcite 官方推荐的扩展方式，不需要修改 Calcite 源码：

1. 创建自定义的 `config.fmpp`，指定 `implementationFiles`
2. 在 `parserImpls.ftl` 中编写自定义 JavaCC 规则
3. 定义对应的 `SqlCall` 子类和 `SqlOperator`

```ftl
// parserImpls.ftl 示例：添加 EXPLAIN DDL 语句
SqlNode SqlExplainDdl()
{
  SqlNode ddl;
}
{
  <EXPLAIN> <DDL> ddl = SqlStmt()
  {
    return new SqlExplainDdl(pos, ddl);
  }
}
```

这种方式被 Babel 模块、Hive、Flink 等广泛使用。

### 3.5.2 方式二：SqlParserImplFactory 自定义解析器

通过 `Config.parserFactory()` 替换整个解析器实现：

```java
SqlParser parser = SqlParser.create(sql,
    SqlParser.config()
        .withParserFactory(MyCustomParserImpl::new));
```

这种方式适用于需要深度修改语法结构的场景，但需要维护完整的 `.jj` 文件。

### 3.5.3 方式三：SqlOperator 扩展

不修改 Parser，而是通过注册新的 `SqlOperator` 来扩展函数：

```java
// 创建自定义函数
SqlOperator myFunc = SqlBasicOperator.create("MY_FUNC")
    .withReturnTypeInference(ReturnTypes.INTEGER)
    .withOperandTypeChecker(OperandTypes.NUMERIC);

// 注册到操作符表
SqlOperatorTable operatorTable = SqlOperatorTables.chain(
    SqlStdOperatorTable.instance(),
    SqlOperatorTables.of(myFunc));
```

这种方式不需要修改语法——如果函数名是合法标识符，标准解析器就能解析 `MY_FUNC(1, 2)` 为 `SqlBasicCall`，后续验证阶段会解析操作符。

### 3.5.4 三种方式的对比

| 方式 | 适用场景 | 复杂度 | 需要重新编译 Parser |
|------|---------|--------|---------------------|
| FMPP includes | 添加新语句类型 | 中 | 是 |
| SqlParserImplFactory | 深度修改语法 | 高 | 是 |
| SqlOperator 扩展 | 添加新函数/操作符 | 低 | 否 |

对于大多数场景，**SqlOperator 扩展**是最简单的方式——只要新函数的调用语法符合标准函数调用形式，就不需要修改 Parser。

## 3.6 从源码跟踪一次解析过程

让我们跟踪 `SELECT 1 + 2 FROM t` 的解析过程：

```
1. SqlParser.create("SELECT 1 + 2 FROM t")
   → 创建 SqlParserImpl 实例，配置词法状态

2. parser.parseStmt()
   → 调用 SqlStmtEof()
     → 匹配 <SELECT>，进入 SqlSelect()
       → SqlSelectKeywords(): 无关键字
       → SqlSelectList():
         → SqlSelectItem(): 解析 "1 + 2"
           → SqlExpression(): 解析表达式
             → SqlAdditiveExpression():
               → SqlLiteral(1)   ← 左操作数
               → <PLUS>
               → SqlLiteral(2)   ← 右操作数
             → 返回 SqlBasicCall(PLUS, [SqlLiteral(1), SqlLiteral(2)])
       → <FROM>
       → FromClause():
         → SqlIdentifier("t")
   → 返回 SqlSelect:
       selectList=[SqlBasicCall(PLUS, [1, 2])]
       from=SqlIdentifier("t")
```

最终的 AST 结构：

```
SqlSelect
├── keywordList: []
├── selectList: SqlNodeList
│   └── SqlBasicCall (operator=PLUS)
│       ├── SqlLiteral(1, INTEGER)
│       └── SqlLiteral(2, INTEGER)
├── from: SqlIdentifier("t")
├── where: null
├── groupBy: null
├── having: null
├── orderBy: null
├── offset: null
└── fetch: null
```

---

## 本章小结

Calcite 的 SQL Parser 由 JavaCC 生成，通过 FMPP 模板系统支持语法扩展。解析输出是 SqlNode AST，其中 SqlCall（及其特化子类 SqlSelect、SqlJoin 等）是最核心的节点类型。SqlOperator 携带了每个调用的语义信息，SqlKind 提供了高效的节点类型判断。扩展 Parser 有三种方式，从轻量的 SqlOperator 注册到重量的 FMPP 注入，复杂度递增。下一章将深入 SqlValidator——它如何在这棵 AST 上进行语义验证。
