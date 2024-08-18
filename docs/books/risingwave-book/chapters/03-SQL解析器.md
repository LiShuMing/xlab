# 第 3 章 · SQL 解析器（sqlparser）

> **核心源码**：`src/sqlparser/`
> **规模**：约 12,000 行 Rust 代码（tokenizer 1576 + parser 6381 + AST 定义 3400 + keywords 776）
> **关键依赖**：[winnow](https://docs.rs/winnow)（parser combinator 框架）

---

## 3.1 前言：为什么要有自己的 SQL Parser？

在数据库系统的技术选型中，SQL Parser 通常有两种策略：**自研**或是**复用开源**。RisingWave 的选择是 Fork 自 [Apache DataFusion](https://github.com/apache/datafusion) 的 [sqlparser-rs](https://github.com/sqlparser-rs/sqlparser-rs)，然后进行了大量定制化改造。

这个决策背后有三个考量：

1. **PostgreSQL 兼容性的刚需**。作为一款定位为"Postgres-compatible"的流数据库，RisingWave 需要支持大量 PG 特有语法（`::type` 类型转换、`$1` 参数化、Dollar-quoted string 等），通用的 ANSI SQL Parser 远远不够。

2. **流式 DDL 的扩展**。`CREATE SOURCE`、`CREATE SINK`、`CREATE MATERIALIZED VIEW` 的语法在传统数据库中不存在，必须自行定义并解析。

3. **控制权的需要**。上下游（Binder/Planner）对 AST 节点有精确的类型要求，使用外部库的版本锁定会阻碍迭代。

> **第一性原理思考**：Parser 的本质是什么？是一个 **String → AST** 的函数。问题在于，这个映射过程是否足够简单，以至于可以用 Parser Generator（yacc/antlr）解决？RisingWave 的回答是"不够"——因为它的语法集合是 PostgreSQL + 流式扩展的交集，边界模糊，需要手写 Parser Combinator 来精确控制回溯与错误恢复策略。

---

## 3.2 模块全景

```
src/sqlparser/
├── src/
│   ├── ast/                    # AST 节点定义
│   │   ├── mod.rs              # Statement 枚举 + 核心类型 (Ident, ObjectName)
│   │   ├── query.rs            # SELECT/FROM/WHERE/JOIN 等查询 AST
│   │   ├── statement.rs        # DDL 语句的 AST 节点
│   │   ├── ddl.rs              # DDL 子句 (ColumnDef, AlterOperations)
│   │   ├── data_type.rs        # 数据类型 AST
│   │   ├── value.rs            # 字面量 AST (Value/SecretRef/ConnectionRef)
│   │   ├── operator.rs         # 运算符 AST
│   │   ├── legacy_source.rs    # 旧版 Source Schema 兼容层
│   │   └── analyze.rs          # ANALYZE 语句 (Hive 兼容)
│   ├── tokenizer.rs            # 词法分析器 (Tokenizer)
│   ├── parser.rs               # 语法分析器 (Parser) - 主解析逻辑
│   ├── parser_v2/              # Winnow 适配层 + 新版解析原语
│   │   ├── mod.rs              # TokenStream trait + keyword 组合子
│   │   ├── impl_.rs            # Parser 在 Winnow Stream 上的 trait 实现
│   │   ├── compact.rs          # 二进制紧凑格式转换 (V1 token 兼容)
│   │   ├── data_type.rs        # 数据类型解析
│   │   ├── expr.rs             # 表达式解析
│   │   └── number.rs           # 数字字面量解析
│   ├── keywords.rs             # 关键字枚举定义 (Keyword enum)
│   ├── quote_ident.rs          # PG quote_ident 实现
│   └── lib.rs                  # crate 入口
├── tests/                      # 集成测试 + testdata
├── sqlparser_bench/            # 性能基准测试
└── fuzz/                       # Fuzz 测试
```

整个解析链路是 `String → Tokenizer → [Token] → Parser → AST`。每个阶段都是明确的转换函数，没有全局状态。

---

## 3.3 词法分析：Tokenizer

词法分析的入口在 `tokenizer.rs:1576`，核心结构是：

```rust
// tokenizer.rs
pub struct Tokenizer<'a> {
    chars: Peekable<Chars<'a>>,
    // 用于判断下一个 < 是否可能是 << (PgLegacyTypedString)
    previous_token: Option<Token>,
}
```

`Tokenizer::new(sql)` 接受 `&str`，返回 `Peekable<Chars>` 的迭代器封装。整个 tokenize 过程是**单遍扫描**：

```rust
// tokenizer.rs - tokenize 的主循环
pub fn tokenize(&mut self) -> Result<Vec<Token>, TokenizerError> {
    // 逐字符消费，匹配下一个 token
    match self.next_char() {
        Some('"') => Ok(Word(self.parse_quoted_identifier('"')?)),
        Some('\'') => Ok(SingleQuotedString(self.parse_single_quoted_string()?)),
        Some('$') => self.parse_dollar_or_parameter(),
        Some('E') => self.parse_cstyle_escapes_string(),
        // ... 数字、运算符、空白等
    }
}
```

### 3.3.1 Token 类型体系

```rust
// tokenizer.rs:29
pub enum Token {
    EOF,
    Word(Word),                    // 关键字或标识符
    Number(String),                // 无符号数字
    Char(char),                    // 不可识别字符
    SingleQuotedString(String),    // 'string'
    DollarQuotedString(DollarQuotedString), // $$string$$ 或 $tag$string$tag$
    CstyleEscapesString(CstyleEscapedString), // E'string'
    NationalStringLiteral(String),  // N'string'
    HexStringLiteral(String),      // X'deadbeef'
    Parameter(String),             // $1, $2
    Comma, LParen, RParen,         // 分隔符
    SemColon, DoubleColon,         // ; 和 ::
    Eq, Neq, Lt, Gt, LtEq, GtEq,   // 比较运算符
    Plus, Minus, Mul, Div, Mod,    // 算术运算符
    Op(String),                    // 自定义运算符 (如 @>, <@ 等 PG 特有)
    Whitespace(Whitespace),        // 空白（含注释）
    // PgLegacyTypedString: PG 特有的 <<...>> 类型字符串
    ShiftLeft,                      // <<
    // ...
}
```

值得注意的设计细节：

- **`Word` 区分关键字和标识符**。`Word.value` 是原始字符串，`Word.keyword` 是 `Keyword` 枚举。如果字符串不匹配任何关键字，则 `keyword == Keyword::NoKeyword`。这意味着关键字识别在 **Tokenizer 阶段就完成了**，Parser 拿到的是已经分类好的 token 流。

- **`Op(String)` 处理 PG 自定义运算符**。PostgreSQL 允许任意字符序列作为运算符（如 `@>`、`<@`、`?|`），Tokenizer 通过贪心匹配 + `ALL_KEYWORDS` 排他来处理。

- **Dollar Quoted String 支持**。PG 的 `$$...$$` 和 `$tag$...$tag$` 语法在 tokenizer 层面就有专门支持，这避免了 Parser 需要感知字符串内部的转义。

### 3.3.2 关键字定义：宏驱动的代码生成

`keywords.rs` 采用声明式宏来生成关键字枚举：

```rust
// keywords.rs:43-62
macro_rules! define_keywords {
    ($($ident:ident $(= $string_keyword:expr)?),*) => {
        #[derive(Debug, Clone, Copy, PartialEq, PartialOrd, Eq, Ord, Hash)]
        pub enum Keyword {
            NoKeyword,
            $($ident),*
        }
        pub const ALL_KEYWORDS_INDEX: &[Keyword] = &[$(Keyword::$ident),*];
        $(kw_def!($ident $(= $string_keyword)?);)*
        pub const ALL_KEYWORDS: &[&'static str] = &[$($ident),*];
    };
}

define_keywords!(
    ABORT, ABS, ACTION, ADAPTIVE, ADD, AGGREGATE, ALL, ...
    SOURCE, SINK, SUBSCRIPTION, MATERIALIZED, ...
    WEBHOOK, WATERMARK, EMIT, ...
);
```

这比手写 `enum Keyword { ... }` 更易维护——添加新关键字就是在宏调用中加一行，`ALL_KEYWORDS` 和 `ALL_KEYWORDS_INDEX` 会自动更新。`ALL_KEYWORDS` 保持**字母序排列**，因为 Tokenizer 中的关键字查找使用的是二分搜索。

> **设计决策**：为什么不用 `phf`（完美哈希）做关键字查找？对于 300+ 的关键字集合，二分搜索 `O(log n)` 的常数因子在实测中与完美哈希差距不大，且不需要编译时代码生成的开销。

---

## 3.4 语法分析：Parser

### 3.4.1 Parser 的结构

```rust
// parser.rs:196
pub struct Parser<'a>(pub(crate) &'a [TokenWithLocation]);
```

Parser 本身是一个 **零大小状态的 newtype wrapper**，包裹着 token 切片。所有的解析状态（当前位置、backtrack 信息）都由 winnow 框架管理。这种设计的好处是：

- Parser 可以在任意位置 `Copy`/`Clone`，实现零成本的 checkpoint 和 backtrack
- 多线程解析天然安全（`Send + Sync`）

### 3.4.2 从字符串到 AST 的完整调用链

```rust
// parser.rs:201
pub fn parse_sql(sql: &str) -> Result<Vec<Statement>, ParserError> {
    let mut tokenizer = Tokenizer::new(sql);
    let tokens = tokenizer.tokenize_with_location()?;
    let parser = Parser(&tokens);
    let stmts = Parser::parse_statements.parse(parser).map_err(|e| {
        // 构造带行号的友好错误信息
        let loc = match tokens.get(e.offset()) { ... };
        let prefix = format!("LINE {}: ", loc.line);
        // ...
    });
    Ok(stmts)
}
```

调用链：`parse_sql` → `Tokenizer::tokenize_with_location` → `Parser::parse_statements` → `parse_statement` → 根据首关键字分发 → 具体语句的解析函数。

`parse_statement` 是解析的主入口（`parser.rs:295`）：

```rust
pub fn parse_statement(&mut self) -> ModalResult<Statement> {
    let checkpoint = *self;  // 零成本 checkpoint（Parser 是 Copy）
    let token = self.next_token();
    match token.token {
        Token::Word(w) => match w.keyword {
            Keyword::EXPLAIN => Ok(self.parse_explain()?),
            Keyword::SELECT | Keyword::WITH | Keyword::VALUES => {
                *self = checkpoint;  // 回退，让 parse_query 自己消费
                Ok(Statement::Query(Box::new(self.parse_query()?)))
            }
            Keyword::CREATE => Ok(self.parse_create()?),
            Keyword::DROP => Ok(self.parse_drop()?),
            Keyword::ALTER => Ok(self.parse_alter()?),
            // ...
        },
        // ...
    }
}
```

注意 `SELECT/WITH/VALUES` 处理中的 `*self = checkpoint`——这是因为这些 token 本身是查询的起始 token，`parse_query` 需要自己消费它们。Parser 先把 token 取出来看了一眼，确认是需要走 query 路径后，回退位置交给 `parse_query` 从头消费。

### 3.4.3 Winnow Parser Combinator 的运用

RisingWave 的 sqlparser 从 v2 版本开始引入了 [winnow](https://docs.rs/winnow) 作为 parser combinator 框架。`parser_v2/` 目录下是 winnow 的适配层：

```rust
// parser_v2/mod.rs:34-44
pub trait TokenStream:
    Stream<Token = TokenWithLocation> + StreamIsPartial + Default + compact::ParseV1
{}

impl<S> TokenStream for S where
    S: Stream<Token = TokenWithLocation> + StreamIsPartial + Default + compact::ParseV1
{}
```

`TokenStream` 是一个 trait alias，它将 winnow 的 `Stream`、`StreamIsPartial`、和 RisingWave 自己的 `ParseV1` 绑定在一起，这样所有组合子函数的泛型约束都可以简化为 `S: TokenStream`。

`parser_v2/` 中定义了细粒度的解析原语：

| 函数 | 位置 | 作用 |
|------|------|------|
| `keyword()` | `mod.rs:60` | 消费任意关键字，返回 `Keyword` |
| `single_quoted_string()` | （尾随定义） | 消费单引号字符串 |
| `dollar_quoted_string()` | 同上 | 消费 Dollar-quoted string |
| `literal_u32()` / `literal_u64()` / `literal_i64()` | `number.rs` | 解析数字字面量 |

`parser.rs` 主文件则使用 `alt!`、`dispatch!`、`preceded!`、`separated!` 等组合子来构建高层语法规则。例如：

```rust
use winnow::combinator::{alt, cut_err, dispatch, opt, preceded, separated};
```

这种 **低层原语 + 高层组合** 的分层架构，使得解析逻辑既保持了可读性（高层组合子接近 BNF），又能在必要时手写精细的控制流（低层直接操作 token 流）。

---

## 3.5 AST 节点设计

### 3.5.1 Statement——顶层语句的根节点

`Statement` 是解析后的顶层 AST 节点，定义在 `ast/mod.rs:1261`：

```rust
pub enum Statement {
    Query(Box<Query>),                   // SELECT / WITH / VALUES
    Insert { table_name, columns, source, returning },
    Update { table_name, assignments, selection, returning },
    Delete { table_name, selection, returning },
    CreateView { or_replace, materialized, if_not_exists, name, query, emit_mode },
    CreateTable { or_replace, temporary, if_not_exists, name, columns, ... },
    CreateIndex { name, table_name, columns, ... },
    CreateSource { stmt: CreateSourceStatement },
    CreateSink { stmt: CreateSinkStatement },
    CreateSubscription { stmt: CreateSubscriptionStatement },
    CreateConnection { stmt: CreateConnectionStatement },
    CreateSecret { stmt: CreateSecretStatement },
    CreateFunction { or_replace, name, args, returns, params },
    CreateAggregate { or_replace, name, args, returns, params },
    AlterTable { name, operation: AlterTableOperation },
    AlterSource { name, operation: AlterSourceOperation },
    AlterSink { name, operation: AlterSinkOperation },
    Drop(DropStatement),
    DeclareCursor { stmt: DeclareCursorStatement },
    FetchCursor { stmt: FetchCursorStatement },
    CloseCursor { stmt: CloseCursorStatement },
    SetVariable { ... },
    ShowVariable { ... },
    Explain { ... },
    Grant { ... },
    Revoke { ... },
    Comment { ... },
    Flush { ... },
    KillProcess { ... },
    Vacuum { ... },
    // ...
}
```

这个枚举的丰富程度直接反映了 RisingWave 的功能边界。除了标准的 SQL DML/DDL，还包括：
- **流式 DDL**（CreateSource / CreateSink / CreateSubscription）
- **Cursor 操作**（Declare / Fetch / Close）——PG 协议的 DECLARE CURSOR 支持
- **系统管理命令**（Flush / KillProcess / Vacuum / DeleteMetaSnapshots）
- **权限管理**（Grant / Revoke）
- **连接与密钥管理**（CreateConnection / CreateSecret）

### 3.5.2 Ident 与 ObjectName——标识符的两种抽象

```rust
// ast/mod.rs:105
pub struct Ident {
    pub(crate) value: String,
    pub(crate) quote_style: Option<char>,  // '"', '\'', '`', '['
}

// ast/mod.rs:219
pub struct ObjectName(pub Vec<Ident>);  // 多段名: db.schema.table
```

`Ident` 的设计保留了 **quote style** 信息。这一点非常重要——因为 PG 中 `SELECT "Foo"` 和 `SELECT Foo` 是不同的（前者大小写敏感，后者被折叠为小写）。`real_value()` 方法封装了这个语义：

```rust
// ast/mod.rs:168
pub fn real_value(&self) -> String {
    match self.quote_style {
        Some('"') => self.value.clone(),  // 双引号 → 保持原样
        _ => self.value.to_lowercase(),   // 其他 → 小写折叠
    }
}
```

`ObjectName` 是一个 `Vec<Ident>`，表示多部分名称（`db.schema.table`）。它的 `base_name()` 返回最后一段的 `real_value()`，这是大多数语义分析场景下实际需要的值。

### 3.5.3 ParseTo trait——AST 节点的反序列化接口

```rust
// ast/statement.rs:34
pub trait ParseTo: Sized {
    fn parse_to(parser: &mut Parser<'_>) -> ModalResult<Self>;
}
```

每个 AST 节点实现 `ParseTo`，由 `impl_parse_to!` 宏辅助生成解析代码。这个 trait 使得 winnow 的组合子可以直接以 `<$type>::parse_to` 的方式调用：

```rust
// 宏的使用示例（来自注释）
// sql_grammar!(CreateSourceStatement {
//     if_not_exists => [Keyword::IF, Keyword::NOT, Keyword::EXISTS],
//     source_name: Ident,
//     with_properties: AstOption<WithProperties>,
//     [Keyword::ROW, Keyword::FORMAT],
//     format_encode: SourceSchema,
// });
```

这个宏 DSL 的设计目标是用**声明式的方式描述 SQL 语法结构**，自动生成 `ParseTo` 的解析代码和 `Display` 的格式化代码。

### 3.5.4 Format/Encode——流式数据格式的 AST 建模

RisingWave 的核心创新之一是对多种数据格式的支持。这在 AST 层面体现为两种正交的枚举：

```rust
// ast/statement.rs:98
pub enum Format {
    Native,          // RisingWave 内部格式
    None,            // 自解释格式 (如 Iceberg)
    Debezium,        // Debezium CDC 格式
    DebeziumMongo,   // Debezium MongoDB
    Maxwell,         // Maxwell CDC
    Canal,           // Canal CDC (阿里)
    Upsert,          // Upsert 语义 (INSERT or UPDATE)
    Plain,           // 纯追加
}

// ast/statement.rs:144
pub enum Encode {
    Avro, Protobuf, Json, Csv,
    Bytes, Template, Parquet,
    Native, None,
}
```

两者组合为 `FormatEncodeOptions`（`ast/statement.rs:216`）：

```rust
pub struct FormatEncodeOptions {
    pub format: Format,
    pub row_encode: Encode,
    pub row_options: Vec<SqlOption>,
    pub key_encode: Option<Encode>,  // KEY ENCODE 子句
}
```

解析时的关键函数是 `parse_format_encode_with_connector`（`ast/statement.rs:233`），它根据 **connector 类型** 来确定默认的 Format/Encode 组合并执行校验。例如 CDC connector 强制要求 `Debezium + Json`，Iceberg 强制要求 `None + None`。这种在 Parser 层面的语义校验，虽然增加了解析阶段的复杂度，但极大地改善了错误信息——用户犯错时立刻得到清晰的提示，而非在 Planner 甚至运行时才发现。

---

## 3.6 PostgreSQL 兼容策略：Parser 层面的扩展点

RisingWave 的 PG 兼容不是事后打补丁，而是在 Parser 的每一层都有原生的支持：

| PG 特性 | 实现位置 | 说明 |
|---------|---------|------|
| `::type` 类型转换 | `parser.rs` | `DoubleColon` token → `Expr::Cast` |
| `$1` 参数化占位符 | `tokenizer.rs` | `Parameter(String)` token |
| Dollar-quoted string | `tokenizer.rs` | `DollarQuotedString` token |
| C-style escape string | `tokenizer.rs` | `CstyleEscapesString(E'...')` |
| `ARRAY[...]` 语法 | `parser.rs` | `Array { elem, named }` AST 节点 |
| PG 自定义运算符 | `tokenizer.rs` | `Op(String)` token（如 `@>`） |
| `DECLARE / FETCH / CLOSE CURSOR` | `parser.rs` | 完整的 Cursor 语句解析 |
| `SET / SHOW / RESET` 变量 | `parser.rs` | Session 变量管理 |
| `GRANT / REVOKE` | `parser.rs` | RBAC 权限管理 |
| `COMMENT ON` | `parser.rs` | 对象注释 |

> **设计取舍**：为什么不直接用 PostgreSQL 的 parser？PG 的 parser 是用 `bison` 生成的 C 代码，与 Rust 的互操作成本很高，而且它包含了大量 RisingWave 不需要的存储层和执行层特性（如 VACUUM FULL、表分区等）。Fork sqlparser-rs 然后用 Rust 手写扩展，更符合"最小依赖"原则。

---

## 3.7 新旧 Parser 的共存：legacy_source.rs

`ast/legacy_source.rs` 文件的存在，揭示了一个重要的工程现实：**兼容老版本语法**。

在早期版本中，RisingWave 的 Source Schema 有另一种语法格式（`ROW FORMAT`）。新版本统一为 `FORMAT ... ENCODE ...`，但老用户的建表语句必须继续工作。`CompatibleFormatEncode` 就是为此设计的兼容层：

```rust
// legacy_source.rs
pub enum CompatibleFormatEncode {
    RowFormat(FormatEncodeOptions),  // 旧语法: ROW FORMAT ...
    V2(FormatEncodeOptions),         // 新语法: FORMAT ... ENCODE ...
}
```

通过 `into_v2()` 方法统一到新格式后，下游的 Binder 和 Planner 就不需要感知语法差异。这种 **Parse → Normalize → Downstream** 的模式，是编译器前端设计中经典的"降级到统一 IR"策略。

---

## 3.8 错误处理：从 token 位置到友好提示

Parser 的错误处理采用了分层策略：

1. **Tokenizer 层**：无法 tokenize 的字符产生 `TokenizerError`，包含位置信息
2. **Parser 层**：语法不匹配时，winnow 的 `ContextError` 自动记录错误位置的 token offset
3. **最外层**（`parse_sql`）：将 offset 映射回 `LINE:COLUMN`，附加出错行的原文和 `^` 指示符

```rust
// parser.rs:205 - parse_sql 的错误包装
.map_err(|e| {
    let loc = match tokens.get(e.offset()) {
        Some(token) => token.location.clone(),
        None => Location { ... }  // EOF 位置
    };
    let prefix = format!("LINE {}: ", loc.line);
    let sql_line = sql.split('\n').nth(loc.line as usize - 1).unwrap();
    // 构造 "LINE N: <sql>\n         ^" 格式的错误信息
})
```

最终用户看到的是类似 PostgreSQL 风格的错误输出，带有准确的定位箭头。

---

## 3.9 性能考量

sqlparser 的性能优化在几个层面：

1. **零拷贝 token 流**：Tokenizer 产生的 `&str` 直接引用原始 SQL 字符串，无额外分配。只有在需要转义处理（如 `''` → `'`）时才分配新 String。

2. **`Box<Query>` 避免递归类型膨胀**：`Statement` 中 `Query` 被包裹在 `Box` 中，因为 `Query` 是递归结构（包含子查询），直接嵌入会导致 `Statement` 的大小无限递归。`Box` 将类型大小固定在一个指针大小。

3. **`Copy` Parser 的零成本 checkpoint**：`Parser` 是 `&[TokenWithLocation]` 的 newtype，`Copy` 意味着 backtrack 只是指针复制，不涉及堆分配。

4. **winnow 的 streaming 解析**：winnow 支持部分输入（partial stream），这意味着未来可以实现网络流式读入即解析，而不需要等待完整 SQL。

benchmark 文件在 `sqlparser_bench/benches/` 目录下，可以运行 `cargo bench -p risingwave_sqlparser` 查看具体指标。

---

## 3.10 从使用者视角：Parser 的调用入口

对于 RisingWave 的其他模块，Parser 的调用非常简单：

```rust
use risingwave_sqlparser::parser::Parser;

let sql = "CREATE MATERIALIZED VIEW mv1 AS SELECT a, count(*) FROM t GROUP BY a";
let ast = Parser::parse_sql(sql).unwrap();
// ast: Vec<Statement>
// ast[0]: Statement::CreateView { materialized: true, name: "mv1", ... }
```

下游的 Frontend 拿到 `Vec<Statement>` 后，逐条交给 `Binder::bind()` 进行语义分析。Parser 的职责到此结束——它不需要知道 `t` 表是否存在、`a` 列的类型是什么。这种**分层解耦**是编译器前端的经典架构。

---

## 3.11 小结

RisingWave 的 SQL Parser 展示了一个 **实用主义** 的技术选型：

- 从 sqlparser-rs 继承 ANSI SQL 的解析骨架（减少重复劳动）
- 用 winnow parser combinator 手写 PG 兼容和流式扩展（精确定制）
- 宏驱动的关键字和语法定义（声明式维护）
- 兼容层隔离新旧语法差异（工程演进）
- 分层错误处理提供友好诊断（用户体验）

从下一章的 Binder 开始，我们将看到这些 AST 节点如何被赋予语义，一步步走向可执行的流计算计划。

---

*本章完成。下一章：[第 4 章 · Binder——语义分析](../chapters/04-Binder-语义分析.md)*
