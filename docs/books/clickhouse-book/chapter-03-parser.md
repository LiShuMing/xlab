# Chapter 3: Parser — 递归下降解析器与 AST 构建

## 3.1 解析管线概览

```
SQL 字符串
  │
  ├── Lexer (Flex Tokenizer)        → Token 流
  │     src/Parsers/clickhouse_lexer.l
  │
  ├── Pos (TokenIterator + Depth)    → 解析器游标
  │     src/Parsers/IParser.h:103-154
  │
  ├── Parser (递归下降 + 回溯)       → AST 树
  │     src/Parsers/ParserQuery.cpp:48-157
  │
  └── IAST (语法树节点)              → AST
        src/Parsers/IAST.h:32-430
```

> **第一性原理**：为什么选择手写递归下降而非解析器生成器（如 ANTLR4）？ClickHouse 有大量非标准语法（PREWHERE、ARRAY JOIN、GLOBAL IN、MergeTree 引擎参数等），手写解析器可以灵活处理这些特殊情况。此外，递归下降的回溯机制让 ClickHouse 能提供精准的错误提示——"最远匹配"策略只报告解析进展最远处的期望 Token。

## 3.2 Lexer：Flex 词法分析器

Token 类型定义在 `src/Parsers/clickhouse_lexer.h`，由 Flex 生成器从 `clickhouse_lexer.l` 生成 C 代码。核心 Token 类型：

```
Keyword          → SELECT, FROM, WHERE, JOIN, CREATE, TABLE...
Number           → 42, 3.14, 1e10, 0xFF
StringLiteral    → 'hello', "world"
Identifier       → table_name, column_name
QuotedIdentifier → `column with spaces`
Comment          → --, /* */
EndOfStream      → 输入结束
```

ClickHouse 使用经典 Flex 而非 ANTLR4 做词法分析——Flex 在编译时将正则表达式展开为 C 状态机跳转表，运行时零开销。

### Lexer 的特殊处理

```
1. 数值字面量:
   整数:    42, 0xFF, 0b1010, 0o77
   浮点数:  3.14, 1e10, 1.5e-3
   特殊值:  NaN, Inf, -Inf

2. 字符串字面量:
   单引号:  'hello', 'it''s' (双写转义)
   双引号:  "hello" (等同于单引号)
   Heredoc: $$hello$$, $tag$hello$tag$

3. 标识符:
   普通标识符:  column_name
   反引号标识符: `column with spaces`, `select`
   双引号标识符: "ColumnWithSpaces"

4. 关键字识别:
   大小写不敏感: SELECT = select = SeLeCt
   保留字: 不能作为标识符使用
   非保留字: 可以作为标识符（如 date, key）
```

## 3.3 IParser：解析器接口与安全边界

`src/Parsers/IParser.h:99-212` — 解析器基类：

```cpp
class IParser
{
public:
    struct Pos : TokenIterator
    {
        uint32_t depth = 0;          // 递归深度
        uint32_t max_depth = 0;      // 最大深度限制
        uint32_t backtracks = 0;     // 回溯计数
        uint32_t max_backtracks = 0; // 最大回溯限制
    };

    virtual bool parse(Pos & pos, ASTPtr & node, Expected & expected) = 0;
};
```

**两个安全边界**（`IParser.h:121-142`）：
- `max_depth` — 防栈溢出（默认 1000），每 128/8192 步（debug/release）调用 `checkStackSize()`
- `max_backtracks` — 防 DoS（默认 1,000,000），超限直接抛异常

**Expected 错误累积**（`IParser.h:59-94`）— "最远匹配"错误提示：

```cpp
struct Expected
{
    absl::InlinedVector<const char *, 7> variants;
    const char * max_parsed_pos = nullptr;

    void add(const char * current_pos, const char * description)
    {
        if (current_pos > max_parsed_pos) {
            variants.clear();  // 更远处 = 重置
            max_parsed_pos = current_pos;
        }
        if (current_pos == max_parsed_pos)
            variants.push_back(description);
    }
};
```

`SELECT x FR` → 报告期望 `FROM`，而非 `SELECT` 已经完成。

### 错误报告示例

```
输入: SELECT a, b FORM t

解析过程:
  1. SELECT ✓ → 读取列列表 ✓
  2. 期望 FROM，但读到 FORM
  3. 最远匹配位置: "FORM"
  4. 错误消息: "Expected one of: FROM, got FORM at position 15"

输入: CREATE TABL t (a Int32)

解析过程:
  1. CREATE ✓
  2. 期望 TABLE 或 TEMPORARY 等
  3. 最远匹配位置: "TABL"
  4. 错误消息: "Expected one of: TABLE, TEMPORARY, VIEW, DICTIONARY, ..., got TABL"
```

## 3.4 ParserQuery：顶级分发站

`src/Parsers/ParserQuery.cpp:48-157` — **贪婪短路求值**：

```cpp
bool ParserQuery::parseImpl(Pos & pos, ASTPtr & node, Expected & expected)
{
    ParserQueryWithOutput query_with_output_p(...);
    ParserInsertQuery insert_p(...);
    ParserSetQuery set_p;
    ParserSystemQuery system_p;
    // ... 30+ 个 Parser

    bool res = query_with_output_p.parse(pos, node, expected)
        || insert_p.parse(pos, node, expected)
        || set_p.parse(pos, node, expected)
        || system_p.parse(pos, node, expected)
        || delete_p.parse(pos, node, expected)
        || update_p.parse(pos, node, expected)
        || copy_p.parse(pos, node, expected);

    // 隐式 SELECT：裸表达式 1 + 2
    if (!res && implicit_select)
    {
        ParserSelectQuery implicit_select_p(true);
        res = implicit_select_p.parse(pos, node, expected);
        // 包装为 SelectWithUnionQuery 保证格式化往返一致性
    }
    return res;
}
```

**Trade-off**：
- 优点：每个 Parser 独立，添加新语法只需一个 `|| new_p.parse()`
- 缺点：最坏 O(n²)，由 `max_backtracks` 硬约束保护

### 主要解析器

| 解析器 | 处理的语句 | 关键文件 |
|--------|-----------|----------|
| `ParserSelectQuery` | SELECT | `ParserSelectQuery.cpp` |
| `ParserInsertQuery` | INSERT | `ParserInsertQuery.cpp` |
| `ParserCreateQuery` | CREATE TABLE/DATABASE/VIEW | `ParserCreateQuery.cpp` |
| `ParserAlterQuery` | ALTER TABLE | `ParserAlterQuery.cpp` |
| `ParserDropQuery` | DROP TABLE/DATABASE | `ParserDropQuery.cpp` |
| `ParserSystemQuery` | SYSTEM 命令 | `ParserSystemQuery.cpp` |
| `ParserSetQuery` | SET 语句 | `ParserSetQuery.cpp` |
| `ParserDeleteQuery` | DELETE FROM | `ParserDeleteQuery.cpp` |
| `ParserUpdateQuery` | UPDATE SET WHERE | `ParserUpdateQuery.cpp` |
| `ParserUseQuery` | USE database | `ParserUseQuery.cpp` |

## 3.5 IAST：语法树节点

`src/Parsers/IAST.h:32` — IAST 基类核心结构：

```cpp
class IAST : public TypePromotion<IAST>
{
public:
    ASTs children;               // n-ary 子节点
    mutable std::atomic<UInt32> ref_counter{0}; // 侵入式引用计数
    UInt32 flags_storage = 0;    // 位域复用（省 4 字节 padding）

    virtual String getID(char delimiter = '_') const = 0; // 类型标识
    virtual ASTPtr clone() const = 0;    // 深拷贝
    String getColumnName() const;        // 列名解析
    virtual void formatImpl(...) const = 0;  // 格式化

    template <typename T> void set(T * & field, const ASTPtr & child);
    template <typename T> void replace(T * & field, const ASTPtr & child);
};
```

**侵入式引用计数**：`ref_counter` 和 `flags_storage` 共享 IAST 的 8 字节，避免 `boost::intrusive_ref_counter` 带来的额外 padding。`flags_storage` 支持继承链式位域——子类通过 `BitfieldStruct` 模板复用同一个 `UInt32`。

**set/replace 模式**：AST 节点的命名字段（如 `ASTSelectQuery::where`）是指向 `children` 中元素的裸指针。`set()` 同时添加到 `children` 和设置指针；`replace()` 原地替换并更新指针。

### 核心 AST 节点

```cpp
// ASTSelectQuery — SELECT 语句（每个子句一个命名字段）
class ASTSelectQuery : public IAST
{
    ASTPtr select;     // SELECT 表达式
    ASTPtr tables;     // FROM + JOIN
    ASTPtr prewhere;   // PREWHERE
    ASTPtr where;      // WHERE
    ASTPtr group_by;   // GROUP BY
    ASTPtr having;     // HAVING
    ASTPtr order_by;   // ORDER BY
    ASTPtr limit_by;   // LIMIT BY
    ASTPtr limit;      // LIMIT
    ASTPtr settings;   // SETTINGS
};

// ASTFunction — 函数/运算符（运算符映射为函数名：+ → "plus", > → "greater"）
class ASTFunction : public IAST
{
    String name;           // "plus", "count", "arrayJoin"
    ASTPtr arguments;      // ASTExpressionList
};

// ASTIdentifier — 标识符（表名、列名、数据库名）
class ASTIdentifier : public IAST
{
    String name;                    // 短名
    std::vector<String> name_parts; // 长名: db.table.col → ["db", "table", "col"]
};

// ASTLiteral — 字面量
class ASTLiteral : public IAST
{
    Field value;  // 可以是 UInt64, Float64, String, Array, Tuple, NULL
};

// ASTTablesInSelectQuery — FROM + JOIN 子句
class ASTTablesInSelectQuery : public IAST { /* 多个 ASTTablesInSelectQueryElement */ };

// ASTExpressionList — 逗号分隔的表达式列表
class ASTExpressionList : public IAST { /* 子节点是表达式 */ };
```

### 运算符到函数的映射

```
运算符 → 内部函数名:

算术:   + → plus, - → minus, * → multiply, / → divide, % → modulo
比较:   = → equals, != → notEquals, > → greater, < → less, >= → greaterOrEquals
逻辑:   AND → and, OR → or, NOT → not
字符串: || → concat, LIKE → like, NOT LIKE → notLike
其他:   IN → in, NOT IN → notIn, IS NULL → isNull, IS NOT NULL → isNotNull
```

这种映射使得表达式优化可以统一处理——所有运算符都是函数，适用于相同的优化 Pass（常量折叠、公共子表达式消除等）。

### 示例 AST 树

```
SQL: SELECT a, count(*) FROM t WHERE x > 1 GROUP BY a

ASTSelectWithUnionQuery
  └── ASTSelectQuery
        ├── SELECT: ASTExpressionList
        │     ├── ASTIdentifier("a")
        │     └── ASTFunction("count") → ASTAsterisk
        ├── FROM: ASTTablesInSelectQuery
        │     └── ASTTableExpression → ASTIdentifier("t")
        ├── WHERE: ASTFunction("greater")
        │     ├── ASTIdentifier("x")
        │     └── ASTLiteral(1)
        └── GROUP BY: ASTExpressionList
              └── ASTIdentifier("a")
```

### 更复杂的 AST 示例

```
SQL: SELECT a, sum(b) FROM t1 JOIN t2 ON t1.id = t2.id
     WHERE t1.x > 0 GROUP BY a HAVING sum(b) > 100 ORDER BY a LIMIT 10

ASTSelectWithUnionQuery
  └── ASTSelectQuery
        ├── SELECT: ASTExpressionList
        │     ├── ASTIdentifier("a")
        │     └── ASTFunction("sum") → ASTIdentifier("b")
        ├── FROM: ASTTablesInSelectQuery
        │     └── ASTTablesInSelectQueryElement
        │           ├── ASTTableExpression → ASTIdentifier("t1")
        │           └── ASTTableJoin
        │                 ├── kind: Inner
        │                 ├── ASTTableExpression → ASTIdentifier("t2")
        │                 └── ON: ASTFunction("equals")
        │                       ├── ASTIdentifier("t1.id")
        │                       └── ASTIdentifier("t2.id")
        ├── WHERE: ASTFunction("greater")
        │     ├── ASTIdentifier("t1.x")
        │     └── ASTLiteral(0)
        ├── GROUP BY: ASTExpressionList → [ASTIdentifier("a")]
        ├── HAVING: ASTFunction("greater")
        │     ├── ASTFunction("sum") → ASTIdentifier("b")
        │     └── ASTLiteral(100)
        ├── ORDER BY: ASTExpressionList
        │     └── ASTOrderByElement → ASTIdentifier("a")
        └── LIMIT: ASTLiteral(10)
```

## 3.6 解析器组合子模式

ClickHouse 用 C++ 继承实现类似函数式 parser combinator 的范式：

```cpp
ParserKeyword("SELECT")           → 匹配关键字
ParserToken(TokenType::Number)    → 匹配 token 类型
ParserList(expr_p, comma_p)       → 逗号分隔列表
ParserOptional(sub_p)             → 可选（失败不报错，回退 pos）
ParserOneOf(a_p, b_p)             → 多选一
ParserNotEmpty(sub_p)             → 必须匹配
```

**典型 SELECT 解析链**：
```
ParserSelectQuery::parseImpl()
  ├── ParserKeyword("SELECT").ignore()
  ├── ParserExpressionList.parse()     → 列/表达式
  ├── ParserKeyword("FROM").ignore()
  ├── ParserTablesInSelectQuery.parse() → 表+JOIN
  ├── ParserOptional("WHERE").parse()
  ├── ParserOptional("GROUP BY").parse()
  ├── ParserOptional("HAVING").parse()
  ├── ParserOptional("ORDER BY").parse()
  ├── ParserOptional("LIMIT BY").parse()
  └── ParserOptional("LIMIT").parse()
```

### 表达式解析 — 运算符优先级

`src/Parsers/ParserExpression.cpp` — 使用 Pratt 解析器实现运算符优先级：

```
优先级 (低 → 高):
  OR
  AND
  NOT
  =, !=, <, >, <=, >=, LIKE, IN, IS NULL
  +, -
  *, /, %
  一元 -, NOT
  ., [, (
  函数调用

解析方式:
  递归下降，每个优先级一层
  左结合运算符: a + b + c → plus(plus(a, b), c)
  右结合运算符: NOT NOT x → not(not(x))
```

### 子查询解析

```
子查询形式:
  1. 标量子查询: (SELECT count() FROM t)
  2. IN 子查询: WHERE x IN (SELECT y FROM t)
  3. GLOBAL IN: WHERE x GLOBAL IN (SELECT y FROM t)

解析:
  遇到 '(' → 尝试解析为子查询
  → 如果以 SELECT 开头 → ASTSubquery
  → 否则 → 普通表达式

GLOBAL IN 的特殊处理:
  → GLOBAL 关键字修饰 IN/NOT IN
  → 解析为 ASTFunction("globalIn") 而非 ASTFunction("in")
  → 在后续执行中行为不同（Coordinator 广播子查询结果）
```

## 3.7 隐式 SELECT

`ParserQuery.cpp:132-154` — 允许裸表达式：

```sql
:) 1 + 2           -- 不用写 SELECT
:) abs(-42)
:) now()
```

实现：所有 Parser 失败后，将输入当 `SELECT ...` 重试，然后包装为 `ASTSelectWithUnionQuery` 保证格式化往返一致。

## 3.8 AST 格式化

`IAST::format()` — AST 可以序列化回 SQL 文本，支持多种格式：

```
格式化模式:
  1. 常规格式化: SELECT a, b FROM t WHERE x > 1
  2. 紧凑格式化: SELECT a, b FROM t WHERE x > 1  (无多余空格)
  3. SQL 格式化: 多行缩进，适合阅读
  4. MySQL 兼容格式: 反引号替代双引号

格式化往返一致性:
  SQL → Parser → AST → format() → SQL' → Parser → AST'
  要求: AST == AST'

用途:
  - EXPLAIN SYNTAX: 显示优化后的 SQL
  - 查询日志: 记录规范化后的 SQL
  - 分布式查询: 将重写后的 SQL 发送到远程节点
```

> **侧边栏 · 与 Spark SQL 对比**：Spark 使用 ANTLR4 生成 LL(*) 解析器 + Visitor 遍历 CST→AST。ClickHouse 的手写递归下降+回溯的 trade-off：(1) 更好的错误消息定制；(2) 无需 JAR 体积膨胀；(3) 更容易为 ClickHouse 特有语法做短路径。代价是维护成本更高，每个新特性需在 `ParserQuery` 注册链中添加位置。

## 3.9 本章小结

| 组件 | 文件 | 核心作用 |
|------|------|----------|
| Lexer | `src/Parsers/clickhouse_lexer.l` | SQL → Token 流 |
| IParser | `src/Parsers/IParser.h` | 解析器接口 + 深度/回溯控制 |
| IAST | `src/Parsers/IAST.h` | AST 节点基类（n-ary 树 + 侵入式引用计数） |
| ParserQuery | `src/Parsers/ParserQuery.cpp` | 顶级分发（30+ 短路求值） |
| ParserExpression | `src/Parsers/ParserExpression.cpp` | 运算符优先级解析 |

**关键设计决策**：
- **递归下降 + 回溯** — 牺牲最坏复杂度，换取扩展性和错误消息质量
- **侵入式引用计数 + 位域复用** — IAST 的 8 字节同时存储引用计数和标志位
- **运算符 → 函数映射** — 统一优化框架，所有运算符都是函数
- **COW AST 树** — 通过共享 `ASTPtr` 减少拷贝

**关键文件地图**：
```
src/Parsers/clickhouse_lexer.l          → 词法分析器定义
src/Parsers/IParser.h                   → 解析器接口
src/Parsers/IAST.h                      → AST 节点基类
src/Parsers/ParserQuery.cpp             → 顶级查询分发
src/Parsers/ParserSelectQuery.cpp       → SELECT 解析
src/Parsers/ParserExpression.cpp        → 表达式 + 运算符优先级
src/Parsers/ParserCreateQuery.cpp       → CREATE 解析
src/Parsers/ParserInsertQuery.cpp       → INSERT 解析
src/Parsers/ASTSelectQuery.h            → SELECT AST 节点
src/Parsers/ASTFunction.h               → 函数 AST 节点
```
