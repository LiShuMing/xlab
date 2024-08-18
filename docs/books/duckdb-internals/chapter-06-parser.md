# 第6章：Parser —— 从文本到 AST

> 解析器是 SQL 引擎的第一站。DuckDB 在这一站选择了一条"看起来懒但实际非常聪明"的路：不是自己写词法分析和语法解析，而是 fork 了 PostgreSQL 的解析器，然后通过 Transformer 将其转化为自己的内部 AST。这不是偷懒——这是工程上最合理的资源分配。

## 6.1 两层解析架构：PostgresParser → Transformer

DuckDB 不自己解析 SQL。它 fork 了 PostgreSQL 的 `libpgquery`（`src/parser/` 目录中的 `libpg_query/`），将其作为原始的语法解析后端。然后通过 `Transformer` 类将 PG 的解析树转换为 DuckDB 内部 AST。

```cpp
// src/parser/parser.cpp:193-207
unique_ptr<SQLStatement> Parser::GetStatement(const string &query) {
    Transformer transformer(options);
    vector<unique_ptr<SQLStatement>> statements;
    PostgresParser parser;
    parser.Parse(query);                                    // Step 1: PG 解析
    if (parser.success) {
        if (!parser.parse_tree) {
            return {};                                      // 空语句
        }
        transformer.TransformParseTree(parser.parse_tree, statements);  // Step 2: 转换
        return std::move(statements[0]);
    }
    return {};
}
```

### 为什么不自己写解析器？

这是一个所有数据库工程师都会问的问题。答案：

1. **SQL 语法极其复杂**。PostgreSQL 的 SQL 语法规则文件（`gram.y`）有近 18000 行——这不是一个人或一个小团队能轻易维护的
2. **PostgreSQL 有最接近标准的 SQL 语法支持**。与 MySQL 的方言不同，PG 更严格地遵循 SQL 标准
3. **DuckDB 的创新不在语法解析**，而在优化器和执行引擎。将有限的人力投入到最能产生差异化的层面
4. **fork + 裁剪**保证不需要运行时依赖——`libpg_query` 被编译进 DuckDB 并静态链接，不违反"零依赖"原则

### fork 了什么？

```cpp
// src/parser/parser.cpp:17
#include "postgres_parser.hpp"  // DuckDB 的 fork 版本
```

`src/parser/libpg_query/` 包含 fork 自 `pganalyze/libpg_query` 的代码，后者又 fork 自 PostgreSQL 源码。它不只是"拿来用"——DuckDB 做了大量裁剪：

- 移除所有 PostgreSQL 特定功能（如 PL/pgSQL、COPY、VACUUM 等）
- 保留核心 DML/DDL 语法（SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER）
- 添加 DuckDB 特有语法扩展（PIVOT, UNPIVOT, ASOF JOIN, MACRO 等）
- 输出不是 PostgreSQL 的 `Query` 对象，而是一棵 `PGNode` 的抽象语法树——类似于 Clang 的 AST

### 两阶段解析流程（ParseQuery）

```cpp
// src/parser/parser.cpp:222-362
void Parser::ParseQuery(const string &query) {
    Transformer transformer(options);
    // Phase 0: Unicode 空格处理
    // Phase 1: Parser Extension 覆盖尝试
    // Phase 2: PostgresParser 解析
    // Phase 3: Transformer 转换 PG AST → DuckDB AST
    // Phase 4: 语句分割与重解析（多语句场景）
}
```

完整流程有四层防护：

1. **Unicode 空格剥离**：`StripUnicodeSpaces` 处理全角空格（U+3000）、不间断空格（U+00A0）等多种 unicode 空格字符
2. **Parser Extension 覆盖**：外部扩展可以抢先解析（`parser_override`），如果设置了 `STRICT_OVERRIDE` 则直接使用扩展结果
3. **PostgresParser 标准解析**：调用 `libpg_query` 的 `pg_parse_query()` 生成 PG AST
4. **语句分割 + 扩展重试**：如果标准解析失败，按 `;` 分割成多个语句，逐条重试——可能某个语句是扩展特定的语法

### Transformer：PG AST → DuckDB AST

```cpp
// src/parser/transformer.cpp: TransformParseTree
// 输入：PostgresParser 产生的 PGNode 树（libpg_query 的内部结构）
// 输出：src/parser/statement/ 下的各种语句类型（SQLStatement 派生类）
// 转换方式：每种 PG AST 节点有对应的 Transfrom* 方法
```

Transformer 的核心是一组 `Transform*` 方法——每个方法处理一种 PG AST 节点类型：

```
TransformSelectStmt   → SelectStatement
TransformInsertStmt   → InsertStatement
TransformCreateStmt   → CreateStatement
TransformExpr         → ParsedExpression
TransformTableRef     → TableRef
```

这是一个"浅转换"——不需要语义分析或类型检查，只是重新包装数据结构。

### 双解析器对象的微妙之处

```cpp
// src/parser/parser.cpp:261-279
{
    PostgresParser parser;      // 创建 PG 解析器
    parser.Parse(query);        // 解析（内部调用 pg_parse_query）
    if (parser.success) {
        if (!parser.parse_tree) {
            return;  // 空语句
        }
        transformer.TransformParseTree(parser.parse_tree, statements);
        parsing_succeed = true;
    } else {
        parser_error = parser.error_message;
        if (parser.error_location > 0) {
            parser_error_location = NumericCast<idx_t>(parser.error_location - 1);
        }
    }
}  // ⚠️ parser 对象在这里析构
```

注意 `PostgresParser` 对象被放在一个显式的作用域中——不是无意的。`PostgresParser` 不是可重入的（reentrant），它的析构会清理全局状态。必须在这个 parser 对象析构后，才能创建新的 parser 实例用于后续的分割重解析。

## 6.2 代码页与 Unicode 空格处理

DuckDB 的 Parser 做了大多数数据库忽略的一件事：正确处理 Unicode 空格。

```cpp
// src/parser/parser.cpp:31-167
static bool ReplaceUnicodeSpaces(const string &query, string &new_query,
                                  vector<UnicodeSpace> &unicode_spaces);
bool Parser::StripUnicodeSpaces(const string &query_str, string &new_query);
```

这是一个状态机驱动的扫描器，跟踪三种位置：
- **正则位置**：在标准 SQL 文本中扫描 unicode 空格
- **引号内位置**：在 `'...'` 或 `"..."` 中——跳过，不干扰字符串字面量
- **dollar-quote 内位置**：在 `$$...$$` 或 `$tag$...$tag$` 中——PG 的字符串字面量语法
- **注释内位置**：在 `--...` 单行注释中——跳过

支持的 Unicode 空格列表（摘自源码中的注释：https://jkorpela.fi/chars/spaces.html）：
```
U+00A0 (C2A0)          - 不换行空格
U+2000..U+200B (E2808x) - 各种宽度的空白字符（EN SPACE, EM SPACE 等）
U+202F (E280AF)        - 窄不换行空格
U+205F (E2819F)        - 中等数学空格
U+2060 (E281A0)        - 单词连接符（zero-width non-breaking space 的变体）
U+3000 (E38080)        - 表意空格（全角空格——中日韩文本中常见）
U+FEFF (EFBBBF)        - BOM / 零宽度不换行空格
```

这个功能的价值场景：当用户从网页、Office 文档或其他非 ASCII 源复制粘贴 SQL 时，不可见的 unicode 空格不会被人类肉眼察觉，但会导致语法解析错误。DuckDB 透明地修复这个问题——在解析前先把 unicode 空格替换为普通 ASCII 空格。

## 6.3 AST 节点家族

Parser 的输出是一棵 `SQLStatement` 树。DuckDB 的 AST 分为四个子家族：

### SQLStatement：顶层语句

```cpp
// src/parser/statement/ 目录
SelectStatement    → SELECT ...
InsertStatement    → INSERT INTO ...
UpdateStatement    → UPDATE ... SET ...
DeleteStatement    → DELETE FROM ...
CreateStatement    → CREATE TABLE/INDEX/VIEW/...
DropStatement      → DROP TABLE/...
AlterStatement     → ALTER TABLE/...
TransactionStatement → BEGIN/COMMIT/ROLLBACK
PrepareStatement   → PREPARE ...
ExecuteStatement   → EXECUTE ...
ExplainStatement   → EXPLAIN ...
CopyStatement      → COPY ...
...
```

每个语句类型有对应的解析后数据结构。`SelectStatement` 包含一个 `QueryNode`，`InsertStatement` 包含目标表+列+值表达式。

### QueryNode：查询的核心结构

```cpp
// src/parser/query_node/ 目录
SelectNode          ← 标准 SELECT 查询（最常用）
SetOperationNode    ← UNION/INTERSECT/EXCEPT
RecursiveCTENode    ← WITH RECURSIVE
UpdateQueryNode     ← UPDATE 的内部表示
```

### TableRef：表引用

```cpp
// src/parser/tableref/ 目录
BaseTableRef           ← 直接表名：SELECT * FROM t
JoinRef                ← JOIN：a JOIN b ON ...
SubqueryRef            ← 子查询：SELECT * FROM (SELECT ...)
TableFunctionRef       ← 表函数：SELECT * FROM read_csv('...')
ExpressionListRef      ← VALUES 子句：VALUES (1,2), (3,4)
ColumnDataRef          ← 列数据引用（内部优化）
EmptyTableRef          ← 无表引用：SELECT 1+2
PivotRef               ← PIVOT 语法
ShowRef                ← SHOW/DESCRIBE
```

### ParsedExpression：表达式树

```cpp
// src/parser/expression/ 目录
ColumnRefExpression     ← 列引用：amount
ConstantExpression      ← 常量：42, 'hello'
FunctionExpression      ← 函数调用：sum(x), concat(a,b)
ComparisonExpression    ← 比较：a > 10
ConjunctionExpression   ← 逻辑运算：a > 10 AND b < 5
OperatorExpression      ← 算术运算：a + b
CaseExpression          ← CASE WHEN ... THEN ... END
CastExpression          ← CAST(x AS INT)
SubqueryExpression      ← 子查询：EXISTS (SELECT ...)
StarExpression          ← * 通配符
WindowExpression        ← OVER 子句
LambdaExpression        ← 匿名函数：(x -> x + 1)
BetweenExpression       ← x BETWEEN a AND b
InClauseExpression      ← x IN (a, b, c)
CollateExpression       ← 排序规则：col COLLATE 'en_US'
ParameterExpression     ← 预备参数：$1, $2
```

这棵 AST 被 Binder（下一章）消费。Binder 会为每个 `ColumnRefExpression` 解析列引用，将 `FunctionExpression("count", *)` 转为 `BoundAggregateExpression("count_star")`，将 `ConstantExpression(100)` 转为 `Value(100:DECIMAL)`。

## 6.4 DuckDB 的 SQL 方言扩展

DuckDB "违背"了 PostgreSQL 兼容语法路线，添加了多个独有扩展：

### PIVOT / UNPIVOT

```sql
-- DuckDB 的 PIVOT 语法
FROM t PIVOT (SUM(amount) FOR region IN ('US', 'EU', 'APAC'));

-- 等价的传统 SQL
SELECT date,
  SUM(CASE WHEN region='US' THEN amount END) AS "US",
  SUM(CASE WHEN region='EU' THEN amount END) AS "EU",
  SUM(CASE WHEN region='APAC' THEN amount END) AS "APAC"
FROM t GROUP BY date;
```

FROM/JOIN 优先的语法设计让 PIVOT 可以链式组合——`FROM t PIVOT (...) AS p JOIN ...`。这不是 SQL 标准化的选择，而是 DuckDB 的"开发者体验优先"路线。

### FROM 优先的 SELECT

```sql
-- DuckDB 支持两种写法
SELECT * FROM t WHERE a > 10;            -- 经典 SQL
FROM t SELECT * WHERE a > 10;            -- DuckDB 风格（FROM 在前）
```

FROM 优先对 DuckDB 的项目名称起到了作用：它使得在 IDE 中能更快地键自动完成表的列——输入 `FROM t ` 之后，列列表就有了上下文字段可能的值。

### 列表推导 (List Comprehension)

```sql
-- Python 风格的列表推导
SELECT [x + 1 FOR x IN range(5) IF x % 2 = 0];
-- 结果: [1, 3, 5]

-- 等价的 SQL 构造
SELECT LIST(res.x + 1) FROM (SELECT unnest(range(5)) as x WHERE x % 2 = 0) res;
```

DuckDB 将列表推导直接集成到语法规则中——`src/parser/transform/expression/` 中包含 `TransformListComprehension` 方法。这使得处理列表的嵌套循环场景可以用一行表达式完成。

### 友元语法（Friendly SQL）

```sql
SELECT * EXCLUDE (col1, col2);            -- 选择除指定列外的所有列
SELECT COLUMNS('amount_.*') FROM t;       -- 正则匹配选择多列
SELECT * REPLACE (col + 1 AS col);        -- 替换某列的计算结果
```

这些不是建立在新的 AST 节点上——它们在 Parser 中展开为标准节点（对 COLUMNS 是多个独立的 ColumnRefExpression，对 REPLACE 是 Expression 列表）。由此 Binder 和 Optimizer 看到的仍然是标准 AST。

### ASOF Join

```sql
-- 时序数据专用的模糊 Join
SELECT a.*, b.price
FROM trades a ASOF JOIN prices b
  ON a.symbol = b.symbol AND a.ts >= b.ts;
```

ASOF Join 是金融/传感器/日志时序数据场景中的关键功能——它在 Parser 层面产生一个特殊的 Join 类型标记，Binder 会将其转换为相应的物理算子。

### MACRO：用户自定义宏

```sql
CREATE MACRO add(a, b) AS a + b;
SELECT add(1, 2);  -- 3
```

MACRO 不同于 UDF——它在查询解析时内联展开，不经过函数注册层。在 Transformer 中，MACRO 解析后存储为 `CreateMacroInfo`，Binder 阶段将调用点展开为表达式树。

## 6.5 Parser Extension：可插拔的语法扩展

DuckDB 允许扩展定义自己的 SQL 语法：

```cpp
// src/parser/parser.cpp:236-256
if (options.extensions) {
    for (auto &ext : options.extensions->ParserExtensions()) {
        if (!ext.parser_override) continue;
        auto result = ext.parser_override(ext.parser_info.get(), query, options);
        if (result.type == ParserExtensionResultType::PARSE_SUCCESSFUL) {
            statements = std::move(result.statements);
            return;  // 扩展解析成功，直接返回
        }
        if (options.parser_override_setting == AllowParserOverride::STRICT_OVERRIDE) {
            ThrowParserOverrideError(result);
        }
    }
}
```

支持的三种覆盖模式：

| 设置 | 行为 |
|------|------|
| `DEFAULT_OVERRIDE` | 跳过扩展，直接使用标准 PG 解析器 |
| `STRICT_OVERRIDE` | 只使用扩展解析，失败即错误 |
| `FALLBACK_OVERRIDE` | 先尝试扩展，失败则回退到 PG 解析器 |

一条覆盖路径后的完整流程：

```
SQL text 进入 Parser
  ├── 扩展 #1 parser_override  → 成功返回 ✓
  │    └── ExtensionStatement(扩展类型, parse_data)
  ├── 扩展 #N parser_override  → 失败 → PG 标准解析
  │    └── PostgresParser 解析 → Transformer 转换
  └── 最终输出: vector<Unique<SQLStatement>>
```

## 6.6 辅助解析：ParseExpressionList / ParseGroupByList / ParseOrderList

Parser 提供了一些特殊场景的辅助公开方法：

```cpp
// 从字符串直接解析表达式列表（如用于 Python API）
Parser::ParseExpressionList("a + 1, b * 2, 'hello'")
// → 内部构造伪查询 "SELECT a+1, b*2, 'hello'" 然后解析

// 解析 GROUP BY 子句
Parser::ParseGroupByList("ROLLUP(a, b), c")

// 解析 VALUES 子句
Parser::ParseValuesList("(1, 2), (3, 4)")
// → 内部构造 "VALUES (1,2), (3,4)" 然后解析
```

这些方法通过构造伪查询（mock query）来解复用 PostgresParser 的能力——不重复实现解析逻辑，而是借已有的 SQL 语法规则来解析部分片段。例如 `ParseColumnList` 构造 `"CREATE TABLE tbl (" + column_list + ")"`，解析出 `CreateTableInfo` 后提取列定义。

---

## 本章小结

DuckDB 的 Parser 是一个"众长"式设计——借 PostgreSQL 的语法解析 + 裁剪 + 重新包装。核心要点：

1. **两层架构**：PostgresParser（fork 的 PG 解析器）→ Transformer（PG 树 → DuckDB 树）
2. **零依赖的 fork**：`libpg_query` 被编译进 DuckDB，静态链接——遵守"零外部依赖"原则
3. **Unicode 空格智能处理**：多字节状态机扫描器，处理 8 种 unicode 空格，同时不干扰字符串字面量
4. **AST 家族**：SQLStatement（顶层语句）→ QueryNode（查询核心）→ TableRef（表引用）→ ParsedExpression（表达式树）
5. **DuckDB 方言**：PIVOT/UNPIVOT、FROM 优先、列表推导、ASOF Join、MACRO——在 Parser 中展开为带标记的标准 AST
6. **可插拔扩展**：Parser Extension 机制允许第三方定义自己的 SQL 语法

下一章，Binder 将消费这棵语法树——走进 Catalog 查找表，推导列类型，将每个名字转化为具体的数据实体。这是从"语法"到"语义"的关键一跳。
