# 第 4 章 · Binder——语义分析

> **核心源码**：`src/frontend/src/binder/`
> **规模**：约 37 个文件，覆盖 SQL 语句绑定、表达式绑定、关系绑定、CTE 处理
> **关键数据结构**：`Binder`、`BindContext`、`BoundStatement`、`Relation`

---

## 4.1 什么是"Bind"？

在经典的数据库前端架构中，Parser 输出的 AST 只是语法正确而已。一个标识符 `a` 到底是列名、表名、函数名还是参数，Parser 无从知晓。Binder 的职责就是回答这些问题。

> **第一性原理思考**：Binding 的本质是什么？是一个 **Name → Entity** 的解析过程。在 RisingWave 中，这个名字可能是一个列名（绑定到某个表的列）、表名（绑定到 catalog 中的表/源/视图）、函数名（绑定到内置函数或 UDF）、或者是一个参数（绑定到 prepared statement 的参数类型）。从信息论的角度，Binder 就是在 AST 之上**附加类型和实体的外延信息**，将模糊的名字映射为精确的引用。

Binder 的输入是 `Statement`（Parser 的 AST 输出），输出是 `BoundStatement`。这个过程包含以下子任务：

1. **名字解析**（Name Resolution）：通过 search_path 和上下文找到名字对应的实体
2. **类型推导**（Type Inference）：为表达式推导返回类型
3. **权限检查**（Authorization）：验证当前用户是否有权访问
4. **依赖收集**（Dependency Tracking）：记录引用的关系/函数/密钥

---

## 4.2 Binder 的结构

```rust
// binder/mod.rs:93-150
pub struct Binder {
    catalog: CatalogReadGuard,
    user: UserInfoReadGuard,
    db_name: String,
    database_id: DatabaseId,
    session_id: SessionId,
    context: BindContext,
    auth_context: Arc<AuthContext>,
    upper_subquery_contexts: Vec<(BindContext, Vec<LateralBindContext>)>,
    lateral_contexts: Vec<LateralBindContext>,
    next_subquery_id: usize,
    next_values_id: usize,
    next_share_id: ShareId,
    session_config: Arc<RwLock<SessionConfig>>,
    search_path: SearchPath,
    bind_for: BindFor,           // Stream | Batch | Ddl | System
    shared_views: HashMap<ViewId, ShareId>,
    included_relations: HashSet<ObjectId>,
    included_udfs: HashSet<FunctionId>,
    included_secrets: HashSet<SecretId>,
    param_types: ParameterTypes,
    temporary_source_manager: TemporarySourceManager,
    staging_catalog_manager: StagingCatalogManager,
    secure_compare_context: Option<SecureCompareContext>,
}
```

Binder 的一个核心状态是 `BindContext`——一个"作用域"的抽象。SQL 查询中存在多层作用域：子查询、LATERAL 子句、CTE 等。Binder 在绑定过程中通过 `push_context()` / `pop_context()` 管理作用域栈。

Binder 通过 `BindFor` 区分绑定目标类型（`binder/mod.rs:81-90`）：

```rust
enum BindFor {
    Stream,   // 绑定 MV/SINK → 走流计算链路
    Batch,    // 绑定普通查询 → 走批处理链路
    Ddl,      // 绑定 CREATE TABLE/SOURCE → 仅收集元数据
    System,   // 绑定 SHOW/DESCRIBE → 系统表查询
}
```

例如，绑定 `CREATE MATERIALIZED VIEW` 时使用 `Binder::new_for_stream(session)`，绑定 `SELECT * FROM t` 时使用 `Binder::new_for_batch(session)`。

---

## 4.3 BindContext——作用域管理

```rust
// binder/bind_context.rs:34-43
pub struct ColumnBinding {
    pub table_name: String,
    pub schema_name: Option<String>,
    pub table_alias: Option<String>,
    pub index: usize,       // 在 Schema 中的位置
    pub is_hidden: bool,    // 隐藏列（如 _row_id）
    pub field: Field,       // 列名 + 数据类型
}
```

`BindContext` 维护了列绑定、表绑定、CTE、窗口定义等信息的集合。当 Binder 处理 `FROM t` 时，它会从 catalog 中读取表 `t` 的 schema，将每一列注册为 `ColumnBinding`，存入 `BindContext`。之后遇到 `SELECT a` 时，Binder 在 `BindContext` 中查找名为 `a` 的列。

```
    SQL Query                        BindContext
  ┌─────────────┐               ┌─────────────────────┐
  │ SELECT a, b │               │ columns: {          │
  │ FROM t      │  ──bind──►   │   "a" → ColumnBinding│
  │ WHERE a > 0 │               │   "b" → ColumnBinding│
  └─────────────┘               │ }                   │
                                │ tables: {           │
                                │   "t" → TableId(42) │
                                │ }                   │
                                └─────────────────────┘
```

`BindContext` 还管理 CTE（Common Table Expression）。CTE 的绑定状态有两种（`binder/bind_context.rs:86-95`）：

```rust
pub enum BindingCteState {
    Bound { query: BoundQuery },  // 已完全绑定的 CTE
    ChangeLog { table: Relation }, // 用于 CDC 的 changelog CTE
}
```

---

## 4.4 BoundStatement——绑定的输出

```rust
// binder/statement.rs:29-38
pub enum BoundStatement {
    Insert(Box<BoundInsert>),
    Delete(Box<BoundDelete>),
    Update(Box<BoundUpdate>),
    Query(Box<BoundQuery>),
    DeclareCursor(Box<BoundDeclareCursor>),
    DeclareSubscriptionCursor(Box<BoundDeclareSubscriptionCursor>),
    FetchCursor(Box<BoundFetchCursor>),
    CreateView(Box<BoundCreateView>),
}
```

`BoundStatement` 和 Parser 的 `Statement` 枚举形成一个对应关系，但不是一一对应。许多 DDL 语句（如 `CREATE SOURCE`、`CREATE TABLE`、`CREATE SINK`）被特殊处理：它们在 binder 阶段不走 `BoundStatement` 的路径，而是在 `handler/` 模块中被单独调用 binder 方法按需绑定部分内容。

绑定分发的主入口是 `bind_statement`（`binder/statement.rs:68`）：

```rust
pub(super) fn bind_statement(&mut self, stmt: Statement) -> Result<BoundStatement> {
    match stmt {
        Statement::Insert { table_name, columns, source, returning } =>
            Ok(BoundStatement::Insert(self.bind_insert(...)?.into())),
        Statement::Delete { table_name, selection, returning } =>
            Ok(BoundStatement::Delete(self.bind_delete(...)?.into())),
        Statement::Query(q) =>
            Ok(BoundStatement::Query(self.bind_query(&q)?.into())),
        // ...
    }
}
```

---

## 4.5 Relation——关系绑定

`Relation` 是 Binder 最核心的类型之一（`binder/relation/mod.rs:57-73`）：

```rust
pub enum Relation {
    Source(Box<BoundSource>),           // 外部数据源
    BaseTable(Box<BoundBaseTable>),     // 普通表
    SystemTable(Box<BoundSystemTable>), // 系统表 (pg_catalog)
    Subquery(Box<BoundSubquery>),       // 子查询
    Join(Box<BoundJoin>),               // 标准 Join
    Apply(Box<BoundJoin>),             // LATERAL Join (correlated)
    WindowTableFunction(Box<BoundWindowTableFunction>), // TUMBLE/HOP/SESSION
    TableFunction { expr, with_ordinality }, // 表函数 (generate_series)
    Watermark(Box<BoundWatermark>),     // Watermark 源
    Share(Box<BoundShare>),             // 共享引用 (CTE/Shared View)
    GapFill(Box<BoundGapFill>),         // 时间序列空洞补齐
}
```

这个枚举的丰富性体现了 RisingWave 对 SQL "关系" 概念的扩展——不仅是传统的表和子查询，还包括 Source（外部数据流）、Watermark（带水位线的流）、GapFill（时间序列填充）等流式特有的概念。

### 4.5.1 表/源的绑定流程

`bind_catalog_relation_by_object_name`（`binder/relation/table_or_source.rs:72`）是绑定表和源的核心方法。流程如下：

1. **名字解析**：将 `ObjectName` 分解为 `(schema_name, table_name)`
2. **Catalog 查找**：在 Catalog 中按 schema_path 搜索
3. **权限检查**：检查当前用户是否有 SELECT/USAGE 权限
4. **类型分发**：根据找到的实体类型创建对应的 `Relation` 变体

```rust
// binder/relation/table_or_source.rs:72-80
pub fn bind_catalog_relation_by_object_name(
    &mut self,
    object_name: &ObjectName,
    bind_creating_relations: bool,
) -> Result<Relation> {
    let (schema_name, table_name) =
        Binder::resolve_schema_qualified_name(&self.db_name, object_name)?;
    self.bind_catalog_relation_by_name(
        None,
        schema_name.as_deref(),
        &table_name,
        bind_creating_relations,
    )
}
```

对于视图，Binder 的处理比较特殊。视图在 Catalog 中只是一个 SQL 定义文本，绑定视图时需要**递归解析**：解析视图的 SQL → 绑定 → 替换为底层的 `Relation` 树。共享视图（Shared View）还涉及 `ShareId` 的去重引用，避免重复处理。

---

## 4.6 表达式绑定

表达式绑定是 Binder 中最精细的部分，代码组织在 `binder/expr/` 下：

```
binder/expr/
├── mod.rs          # 主入口 bind_expr
├── binary_op.rs    # 二元运算符绑定
├── column.rs       # 列引用绑定 (bind_column)
├── function/       # 函数绑定
│   ├── mod.rs
│   ├── aggregate.rs    # 聚合函数
│   ├── builtin_scalar.rs  # 内置标量函数
│   └── window.rs       # 窗口函数
├── order_by.rs     # ORDER BY 项绑定
├── subquery.rs     # 子查询表达式绑定
└── value.rs        # 字面量绑定
```

一个典型的表达式绑定链路：

```
AST Expr               →  ExprImpl (逻辑表达式)
─────────────────────────────────────────────
Expr::Identifier("a")  →  bind_column("a")
  → 在 BindContext 中查找
  → InputRef { index: 0, data_type: Int32 }

Expr::Value("42")      →  bind_value("42")
  → 类型推断: cast_to(42, target_type)
  → Literal { data: Int32(42) }

Expr::BinaryOp {       →  bind_binary_op(left, op, right)
  left: Expr::Identifier("a"),     → 先 bind left → InputRef
  op: BinaryOperator::Plus,        → 查找 + 的函数实现
  right: Expr::Value("1")          → bind right → Literal
}                      →  FunctionCall { func_type: Add, ... }
```

### 4.6.1 函数绑定

函数绑定分为三路：

1. **普通函数**：由 `builtin_scalar.rs` 处理，通过 `FUNC_MAP` (phf hashmap) 将函数名映射到具体实现
2. **聚合函数**：由 `aggregate.rs` 处理，生成 `AggCall` 节点
3. **窗口函数**：由 `window.rs` 处理，绑定 OVER 子句和窗口规约

RisingWave 中函数的返回类型是**通过函数签名计算得出的**，而非静态声明。例如 `length(str)` 返回 `Int32`，`length(array)` 返回 `Int32`，`concat(str1, str2)` 返回 `Varchar`。这个类型推导在 `FunctionRegistry` 中完成。

### 4.6.2 参数的绑定

Binder 通过 `ParameterTypes`（`binder/mod.rs:181-182`）管理 prepared statement 的参数类型：

```rust
pub struct ParameterTypes(Arc<RwLock<HashMap<u64, Option<DataType>>>>);
```

参数的绑定遵循 PG 兼容的规则：
- 用户先在 prepared statement 中指定参数类型（可选）
- 绑定阶段第一次遇到参数时记录为 `None`（未知类型）
- 如果参数随后被 `CAST` 为某类型，记录推理类型
- 最终未推理的未知类型 **默认为 `VARCHAR`**（与 PostgreSQL 一致）

---

## 4.7 Bind 的四种模式：Stream vs Batch vs DDL vs System

`BindFor` 影响了 Binder 的某些行为：

| BindFor | 典型场景 | 关键区别 |
|---------|---------|---------|
| `Stream` | CREATE MV / CREATE SINK | 绑定带有 EMIT MODE 和 watermarks；允许某些流特有的连接操作 |
| `Batch` | SELECT 查询 | 标准查询绑定，不涉及 checkpoint 和 barrier |
| `Ddl` | CREATE TABLE / SOURCE | 仅绑定列定义和 WITH options，不生成完整查询计划 |
| `System` | SHOW / DESCRIBE | 绑定系统表查询，走特殊的系统表 schema |

例如，在 `BindFor::Stream` 模式下，`EmitMode` 会被解析并附加到 MV：

```rust
// CREATE MATERIALIZED VIEW mv1 WITH (EMIT ON UPDATE) AS SELECT ...
Statement::CreateView { materialized: true, emit_mode: Some(EmitMode::OnUpdate), ... }
// → BoundCreateView { emit_mode: Some(EmitMode::OnUpdate), ... }
```

`EmitMode` 控制物化视图的更新频率，有三种模式（由 `ast/mod.rs` 中的 `EmitMode` 枚举定义）：
- `Immediately`（默认）：每次变化立即输出
- `OnWindowClose`：窗口关闭时才输出
- `Deferred`：延迟到 checkpoint 时输出

---

## 4.8 子查询与相关引用

子查询是 Binder 最复杂的部分之一。关键在于 **Correlated Subquery**（相关子查询）的处理：

```sql
SELECT * FROM orders o
WHERE o.amount > (SELECT AVG(amount) FROM orders WHERE customer_id = o.customer_id)
--                                                    ^^^^^^^^^^^^^^^^^^^^^^^^
--                                                    这里引用了外层的 o.customer_id
```

Binder 通过以下机制处理：

1. **`push_context()` / `pop_context()`**：进入子查询时保存当前 BindContext，子查询拥有独立的作用域
2. **`upper_subquery_contexts` 栈**：当绑定子查询内部的表达式时，如果在当前作用域找不到名字，就去 `upper_subquery_contexts` 中逐层查找
3. **`CorrelatedInputRef`**：如果名字在外部作用域找到，生成一个 `CorrelatedInputRef` 而非 `InputRef`。这个 `CorrelatedInputRef` 携带了 `depth` 信息（跨越了几层作用域）

```rust
// binder/mod.rs:93-107
/// A stack holding contexts of outer queries when binding a subquery.
/// It also holds all of the lateral contexts for each respective subquery.
upper_subquery_contexts: Vec<(BindContext, Vec<LateralBindContext>)>,
```

`visible_upper_subquery_contexts_rev()` 方法（`binder/mod.rs:406-413`）提供了一个从当前到最外层的反向迭代器，但会跳过 SQL UDF 的边界——这是出于 UDF 的卫生性（hygiene）考虑。

---

## 4.9 LATERAL Join 的上下文管理

LATERAL 是 PostgreSQL 的扩展语法，允许子查询引用前面 FROM 项中的列：

```sql
SELECT * FROM t1, LATERAL (SELECT * FROM t2 WHERE t2.x = t1.x) AS s;
--                                                ^^^^
--                                         引用左侧的 t1
```

Binder 通过 `lateral_contexts` 栈（`binder/mod.rs:110`）和三个方法管理：

- **`push_lateral_context()`**：扫描到 LATERAL 表因子时，将当前上下文推入 lateral 栈
- **`pop_and_merge_lateral_context()`**：完成 LATERAL 表因子的绑定后，合并左右上下文
- **`try_mark_lateral_as_visible()`** / **`try_mark_lateral_as_invisible()`**：控制 LATERAL 绑定的可见性开关

这种精密的上下文操作确保了**只有在 LATERAL 关键字出现时，左侧的列才是可见的**——这正是 PG 的行为。

---

## 4.10 CTE 与 ShareId

CTE（WITH 子句）在 Binder 中通过 `ShareId` 机制实现共享引用。每个 CTE 会被赋予一个唯一的 `ShareId`，多次引用同一 CTE 时共享同一个 `ShareId`。

```rust
// binder/mod.rs:119
next_share_id: ShareId,
shared_views: HashMap<ViewId, ShareId>,
```

绑定的 CTE 在 `BindContext.cte_to_relation` 中注册。在 `binder/relation/share.rs` 中，`BoundShare` 处理对 CTE 的引用——每个引用处生成一个 `BoundShare` 节点，但它们共享同一个 `ShareId`。这保证了 Planner 阶段能识别出这是同一个数据源，进而做出共享算子的优化。

---

## 4.11 依赖跟踪

Binder 在绑定过程中自动收集三种依赖：

```rust
included_relations: HashSet<ObjectId>,   // 引用的表/源/视图
included_udfs: HashSet<FunctionId>,      // 引用的 UDF
included_secrets: HashSet<SecretId>,     // 引用的密钥
```

这些依赖信息在 Meta Service 中用于：
1. **级联删除保护**：有依赖的对象不能被 DROP
2. **Catalog 版本通知**：依赖变更时通知订阅者
3. **MV 刷新决策**：Source 更新后判断哪些 MV 需要刷新

> **设计洞察**：依赖收集发生在 Binder 阶段而非 Planner 阶段，这是因为 Planner 的优化可能**移除**一些引用（例如常量折叠掉不必要的列），但这些引用在语义上仍然存在，必须被视为依赖。这体现了 RisingWave 工程团队对"语义正确性优先于优化正确性"的权衡。

---

## 4.12 从 Parser AST 到 BoundStatement 的完整示例

以一个简单查询为例来串联全流程：

```sql
SELECT upper(name), count(*) FROM users WHERE age > 18 GROUP BY name
```

Parser 输出：
```
Statement::Query(
    SELECT { projection: [Function(upper, [Identifier("name")]),
                          Function(count, [Wildcard])],
             from: [Table("users")],
             selection: BinaryOp(Identifier("age"), Gt, Number("18")),
             group_by: [Identifier("name")] })
```

Binder 处理过程：

1. **bind_query** → `bind_select`
2. **bind_table_or_source("users")**：在 catalog 中找到 `users` 表（schema: `id: Int32, name: Varchar, age: Int32`），将三列注册到 BindContext
3. **bind_expr(upper(name))**：
   - `bind_column("name")` → `InputRef { index: 1, data_type: Varchar }`
   - `bind_function("upper", [InputRef])` → `FunctionCall { func_type: Upper, return_type: Varchar, inputs: [InputRef(1)] }`
4. **bind_expr(count(*))** → `AggCall { agg_type: Count, return_type: Int64, args: [] }`
5. **bind_expr(age > 18)**：
   - `bind_column("age")` → `InputRef { index: 2, data_type: Int32 }`
   - `bind_value("18")` → `Literal { data: Int32(18) }`（推断类型与 age 对齐）
   - `bind_binary_op` → `FunctionCall { func_type: GreaterThan, return_type: Boolean }`
6. **bind_group_by(name)** → 验证 `name` 存在于 Context 中，收集为 GroupKey

最终输出：
```
BoundQuery {
    body: BoundSelect {
        select_items: [
            FunctionCall { func_type: Upper, return_type: Varchar, inputs: [InputRef(1)] },
            AggCall { agg_type: Count, return_type: Int64, args: [] }
        ],
        from: BaseTable { table_id: 42, columns: [id, name, age] },
        where_clause: FunctionCall { func_type: GreaterThan, ... },
        group_by: GroupKey([InputRef(1)]),
        schema: { name:Varchar, count:Int64 }
    }
}
```

注意 Parser 中的 `Identifier("name")` 变成了 `InputRef { index: 1 }`——这是 Binder 最重要的转换：**从名字到位置的映射**。

---

## 4.13 小结

Binder 完成了 SQL 编译链路中的语义分析：

- **名字解析**：通过 Catalog 和 BindContext 将名字映射为实体引用
- **类型推导**：为表达式推导准确的数据类型
- **作用域管理**：通过 BindContext 栈正确处理子查询和 LATERAL
- **依赖收集**：为 Meta Service 提供准确的依赖图

Binder 的输出 `BoundStatement` 是一个语义完整的中间表示。接下来 Planner 会将它转化为逻辑计划，进入查询优化阶段。

> **工程师视角提示**：绑定阶段的设计质量直接影响 SQL 编译的健壮性。RisingWave 的 Binder 在处理作用域时采用了显式的、手写的状态管理（push/pop context），而非依赖 Rust 的 borrow checker 自动管理——这给了更多控制力，但也要求更精确的配对调用。阅读代码时重点跟踪 `push_context` 和 `pop_context` 的调用点，它们是理解作用域逻辑的关键。

---

*本章完成。下一章：[第 5 章 · Planner——逻辑计划生成](../chapters/05-Planner-逻辑计划生成.md)*
