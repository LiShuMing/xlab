# 第4章：SQL 验证 — 语义世界的守门人

## 4.1 验证的本质

SQL 解析器只关心语法正确性——`SELECT FROM WHERE` 是否按正确顺序出现，括号是否匹配。但一条语法正确的 SQL 可能语义上是非法的：

```sql
-- 语法正确，语义错误
SELECT nonexistent_col FROM t           -- 列不存在
SELECT name FROM t WHERE amount > 'hello' -- 类型不匹配
SELECT COUNT(*) FROM t GROUP BY id HAVING name > 0 -- HAVING 引用非聚合列
```

SQL 验证器的职责是回答四个问题：

1. **名称解析**：每个标识符指向什么？（表？列？函数？）
2. **类型检查**：每个表达式的类型是什么？操作符参数类型是否合法？
3. **语义合法性**：GROUP BY/HAVING 的列引用是否合法？子查询是否在允许的位置？
4. **隐式转换**：需要类型强转吗？转换为哪种类型？

源码位置：`core/src/main/java/org/apache/calcite/sql/validate/`（88 文件）

## 4.2 SqlValidator 接口与 SqlValidatorImpl 实现

### 4.2.1 SqlValidator 接口

`SqlValidator` 是验证器的公共接口，核心方法：

```java
// sql/validate/SqlValidator.java
public interface SqlValidator {
  // 验证入口
  SqlNode validate(SqlNode topNode);

  // 获取验证后的类型
  RelDataType getValidatedNodeType(SqlNode node);

  // 获取各子句的作用域
  SqlValidatorScope getSelectScope(SqlSelect select);
  SqlValidatorScope getFromScope(SqlSelect select);
  SqlValidatorScope getWhereScope(SqlSelect select);
  SqlValidatorScope getGroupScope(SqlSelect select);
  SqlValidatorScope getHavingScope(SqlSelect select);

  // 获取命名空间
  SqlValidatorNamespace getNamespace(SqlNode node);

  // 名称解析
  SqlQualified fullyQualify(SqlIdentifier identifier);
}
```

### 4.2.2 SqlValidatorImpl — 验证的核心实现

`SqlValidatorImpl` 是一个 5000+ 行的核心类，管理验证的完整状态：

```java
// SqlValidatorImpl.java 关键状态
protected final SqlValidatorCatalogReader catalogReader;  // 元数据读取器
protected final RelDataTypeFactory typeFactory;           // 类型工厂
protected final SqlOperatorTable opTab;                   // 操作符表

// 映射表
private final Map<SqlNode, SqlValidatorScope> scopes = new HashMap<>();      // 节点 → 作用域
private final Map<SqlNode, SqlValidatorNamespace> namespaces = new HashMap<>(); // 节点 → 命名空间
private final Map<SqlNode, RelDataType> nodeToTypeMap = new HashMap<>();       // 节点 → 类型
private final Map<String, IdInfo> idPositions = new HashMap<>();               // 位置 → 标识符信息
```

### 4.2.3 验证入口流程

```java
// SqlValidatorImpl.java:942
@Override public SqlNode validate(SqlNode topNode) {
  // 1. 创建初始作用域（EmptyScope → CatalogScope）
  SqlValidatorScope scope = new EmptyScope(this);
  scope = new CatalogScope(scope, ImmutableList.of("CATALOG"));

  // 2. 执行验证（含无条件改写 + 作用域注册 + 类型推导）
  final SqlNode topNode2 = validateScopedExpression(topNode, scope);

  // 3. 确保根节点有类型
  final RelDataType type = getValidatedNodeType(topNode2);
  return topNode2;
}
```

验证分为三个阶段：

1. **无条件改写**（`performUnconditionalRewrites`）：将 `IN` 子查询改写为 `EXISTS`，标准化语法
2. **注册**（`registerQuery`）：遍历 AST，为每个子查询创建 Namespace 和 Scope
3. **验证**（`validateNamespace`）：对每个 Namespace 执行语义检查和类型推导

## 4.3 命名空间（Namespace）与作用域（Scope）

Namespace 和 Scope 是验证器的两个核心数据结构，理解它们的区别是读懂验证器的关键。

### 4.3.1 Namespace — "这是什么"

`SqlValidatorNamespace` 描述一个 SQL 子查询产生的**行类型**——它有哪些列，每列什么类型。

```java
// sql/validate/SqlValidatorNamespace.java
public interface SqlValidatorNamespace {
  RelDataType getRowType();          // 行类型（所有列的类型）
  RelDataType getType();             // 自身类型（可能是标量、行或集合）
  SqlValidatorNamespace resolve();    // 解析到基础命名空间
  void validate(RelDataType targetRowType);  // 验证此命名空间
  SqlNode getNode();                 // 对应的 SqlNode
}
```

### 4.3.2 Namespace 的继承体系

每个产生行类型的 SQL 构造都有对应的 Namespace 实现：

```
SqlValidatorNamespace (接口)
└── AbstractNamespace (抽象类)
    ├── SelectNamespace       — SELECT 语句
    ├── IdentifierNamespace   — 表名/视图名 (如 t, schema.t)
    ├── JoinNamespace         — JOIN 的结果
    ├── SetopNamespace        — UNION/INTERSECT/MINUS
    ├── AliasNamespace        — 别名 (如 t AS x)
    ├── CollectNamespace      — COLLECT/ARRAY/MAP 构造
    ├── PivotNamespace        — PIVOT
    ├── UnpivotNamespace      — UNPIVOT
    ├── MatchRecognizeNamespace — MATCH_RECOGNIZE
    ├── WithNamespace         — WITH (CTE)
    ├── WithItemNamespace     — WITH 项
    ├── TableNamespace        — 表值构造函数
    ├── SchemaNamespace       — Schema（顶级）
    ├── ProcedureNamespace    — 存储过程调用
    ├── FieldNamespace        — 字段引用
    ├── ParameterNamespace    — 参数
    ├── LambdaNamespace       — Lambda 表达式
    └── UnnestNamespace       — UNNEST
```

### 4.3.3 Scope — "在这里能看见什么"

`SqlValidatorScope` 描述在 SQL 的某个位置，**哪些名称是可见的**——它定义了名称解析的搜索空间。

```java
// sql/validate/SqlValidatorScope.java
public interface SqlValidatorScope {
  SqlValidator getValidator();

  // 名称解析：查找标识符
  void resolve(List<String> names, SqlNameMatcher nameMatcher,
      boolean deep, Resolved resolved);

  // 查找哪些表包含指定列名
  Pair<String, RelDataType> findQualifyingTableName(
      String columnName, SqlNode ctx, SqlNameMatcher nameMatcher);

  // 完全限定一个标识符
  SqlQualified fullyQualify(SqlIdentifier identifier);

  // 添加子作用域
  void addChild(SqlValidatorNamespace ns, @Nullable String alias,
      boolean nullable);
}
```

### 4.3.4 Scope 的继承体系

```
SqlValidatorScope (接口)
├── EmptyScope           — 空作用域（验证起点，无任何可见名称）
├── CatalogScope         — Catalog 作用域（只能看到 Schema 名）
├── DelegatingScope      — 委托基类（所有其他 Scope 的父类）
│   ├── ListScope        — 列表作用域基类
│   │   ├── SelectScope  — SELECT 作用域（可见 FROM 的所有列）
│   │   ├── JoinScope    — JOIN 作用域
│   │   ├── WithScope    — WITH 作用域
│   │   ├── TableScope   — 表作用域
│   │   ├── MatchRecognizeScope — MATCH_RECOGNIZE
│   │   ├── UnpivotScope — UNPIVOT
│   │   └── CollectScope — COLLECT
│   ├── AggregatingSelectScope — 聚合 SELECT（处理 GROUP BY 可见性）
│   ├── GroupByScope     — GROUP BY 作用域
│   ├── OrderByScope     — ORDER BY 作用域
│   ├── OverScope        — OVER 窗口作用域
│   ├── ParameterScope   — 参数作用域
│   └── PivotScope       — PIVOT 作用域
└── MeasureScope         — MEASURE 作用域
```

### 4.3.5 Namespace vs Scope：关键区别

| 维度 | Namespace | Scope |
|------|-----------|-------|
| 回答的问题 | "这个查询产出什么？" | "在这里能看见什么？" |
| 核心属性 | `rowType`（列的类型列表） | `resolve()`（名称查找） |
| 生命周期 | 每个 SqlNode 一个 | 每个 SqlNode 位置一个 |
| 嵌套关系 | 通过 `resolve()` 委托到基础 Namespace | 通过 `parent` 链委托查找 |

用一个例子说明：

```sql
SELECT e.name, d.dept_name
FROM emp e JOIN dept d ON e.dept_id = d.id
WHERE e.salary > 1000
```

这条语句产生的 Namespace 和 Scope：

```
SqlSelect → SelectNamespace (rowType: [name VARCHAR, dept_name VARCHAR])
         → SelectScope (可见: e.*, d.*)
              → JoinScope (可见: e.*, d.*)
                   → IdentifierNamespace("emp AS e") → SelectScope (可见: e.*)
                   → IdentifierNamespace("dept AS d") → SelectScope (可见: d.*)
```

WHERE 子句的 Scope 是 `SelectScope`，它可以看到 `e.*` 和 `d.*` 的所有列。

## 4.4 名称解析：从 SqlIdentifier 到列引用

名称解析是验证器最核心也最复杂的逻辑。它需要处理：

- 非限定名：`name` → 需要搜索所有可见的表
- 限定名：`e.name` → 在表 `e` 中查找
- 嵌套结构：`e.address.city` → 逐层深入
- 歧义：多个表有同名列
- 大小写：依赖 `SqlNameMatcher` 的策略

### 4.4.1 resolve 方法

名称解析的核心是 `SqlValidatorScope.resolve()` 方法：

```java
// DelegatingScope.resolve() 伪代码
void resolve(List<String> names, SqlNameMatcher nameMatcher,
    boolean deep, Resolved resolved) {
  // names = ["e", "name"] 或 ["name"]

  // 1. 先在子作用域中查找
  for (ScopeChild child : children) {
    if (nameMatcher.matches(child.alias, names[0])) {
      // 找到匹配的子命名空间
      SqlValidatorNamespace ns = child.namespace.resolve();
      if (names.size() == 1) {
        // 非限定名 → 添加到结果
        resolved.found(ns, false, path);
      } else {
        // 限定名 → 继续在子命名空间中解析剩余部分
        ns.resolve(names.subList(1, names.size()), ...);
      }
    }
  }

  // 2. 子作用域没找到 → 委托给父作用域
  parent.resolve(names, nameMatcher, deep, resolved);
}
```

### 4.4.2 fullyQualify — 完全限定标识符

`fullyQualify()` 方法将部分限定的标识符转换为完全限定形式：

```sql
-- 输入
name

-- 输出（假设 emp 表的 name 列）
e.name
```

这个过程包括：

1. 尝试将标识符解析为列引用
2. 如果是非限定名，搜索所有可见表
3. 如果找到唯一匹配，扩展为完全限定名
4. 如果有歧义，报错
5. 如果找不到，尝试解析为表名/Schema 名

### 4.4.3 StructKind 对名称解析的影响

前面提到的 `StructKind` 在此发挥作用。当行类型的 `StructKind` 为 `PEEK_FIELDS` 时，嵌套字段的列可以直接引用，无需前缀：

```sql
-- 假设 emp 表有嵌套结构 address(city, street)
-- PEEK_FIELDS 模式下，可以直接写：
SELECT city FROM emp

-- FULLY_QUALIFIED 模式下，必须写：
SELECT address.city FROM emp
```

## 4.5 类型推导

### 4.5.1 deriveType — 表达式类型推导

每个 SqlNode 的类型通过 `SqlValidatorImpl.deriveType()` 推导：

```java
// SqlValidatorImpl.java:2095
@Override public RelDataType deriveType(SqlValidatorScope scope, SqlNode operand) {
  // 根据 SqlNode 的类型分发
  switch (operand.getKind()) {
    case IDENTIFIER:
      // 从作用域中查找列类型
      return deriveTypeFromIdentifier(scope, (SqlIdentifier) operand);
    case LITERAL:
      // 字面量直接返回类型
      return ((SqlLiteral) operand).createSqlType(typeFactory);
    default:
      // 对于 SqlCall，委托给 SqlOperator.deriveType()
      if (operand instanceof SqlCall) {
        return ((SqlCall) operand).getOperator().deriveType(this, scope, (SqlCall) operand);
      }
  }
}
```

### 4.5.2 SqlOperator.deriveType — 操作符类型推导

操作符的类型推导是最复杂的部分。以 `SqlBinaryOperator` 为例：

```java
// SqlOperator.deriveType() 伪代码
public RelDataType deriveType(SqlValidator validator, SqlValidatorScope scope, SqlCall call) {
  // 1. 推导每个操作数的类型
  List<RelDataType> argTypes = new ArrayList<>();
  for (SqlNode operand : call.getOperandList()) {
    argTypes.add(validator.deriveType(scope, operand));
  }

  // 2. 检查操作数类型是否合法
  checkOperandTypes(callBinding, ...);

  // 3. 推导返回类型
  RelDataType returnType = inferReturnType(opBinding);

  // 4. 应用隐式类型强转
  if (needsCoercion) {
    argTypes = coerceTypes(...);
  }

  return returnType;
}
```

### 4.5.3 inferUnknownTypes — 未知类型推导

某些上下文中，表达式的类型最初是未知的（如 `NULL` 字面量、`?` 参数）。`inferUnknownTypes()` 根据目标类型推导这些未知类型：

```sql
-- NULL 的类型未知，但目标类型是 INTEGER
CAST(NULL AS INTEGER)
-- → NULL 被推导为 INTEGER 类型

-- 参数类型未知，但函数签名要求 INTEGER
MOD(?, 10)
-- → ? 被推导为 INTEGER 类型
```

## 4.6 子查询验证

子查询是 SQL 中最复杂的构造之一。Calcite 支持的子查询位置：

| 位置 | 示例 | SqlKind |
|------|------|---------|
| FROM | `SELECT * FROM (SELECT ...)` | — |
| WHERE (EXISTS) | `WHERE EXISTS (SELECT ...)` | `EXISTS` |
| WHERE (IN) | `WHERE x IN (SELECT ...)` | `IN` |
| WHERE (标量) | `WHERE x > (SELECT ...)` | `SCALAR_QUERY` |
| SELECT 列表 | `SELECT (SELECT ...) AS y` | `SCALAR_QUERY` |

### 4.6.1 关联变量识别

关联子查询引用外层查询的列：

```sql
SELECT * FROM emp e
WHERE EXISTS (
  SELECT 1 FROM dept d WHERE d.id = e.dept_id  -- e.dept_id 是关联引用
)
```

验证器通过 Scope 的 `parent` 链识别关联引用——当子查询的 Scope 中找不到某个标识符时，向外层 Scope 查找，如果找到了外层列，就创建一个关联变量。

### 4.6.2 子查询合法性检查

验证器检查子查询是否出现在允许的位置：

- 标量子查询只能返回一行一列
- EXISTS 子查询不限制返回列数
- FROM 子查询必须有别名
- DML 中的子查询有特殊限制

## 4.7 SqlConformance — SQL 兼容性级别

`SqlConformance` 定义了 Calcite 接受哪些非标准 SQL 行为。这是一个关键接口，因为不同数据库的 SQL 行为差异很大。

### 4.7.1 预置兼容性级别

```java
public enum SqlConformanceEnum implements SqlConformance {
  STRICT_92,       // SQL-92 严格模式
  STRICT_99,       // SQL:1999 严格模式
  STRICT_2003,     // SQL:2003 严格模式
  PRAGMATIC_99,    // SQL:1999 实用模式
  PRAGMATIC_2003,  // SQL:2003 实用模式（Calcite 默认）
  ORACLE_10,       // Oracle 10g 兼容
  ORACLE_12,       // Oracle 12c 兼容
  MYSQL_5,         // MySQL 5.x 兼容
  LENIENT,         // 宽松模式（尽可能接受）
  DEFAULT;         // 默认 = PRAGMATIC_2003
}
```

### 4.7.2 关键兼容性开关

| 开关 | STRICT | PRAGMATIC | ORACLE | MYSQL | 含义 |
|------|--------|-----------|--------|-------|------|
| `isGroupByAlias` | false | false | true | true | GROUP BY 能否用别名 |
| `isGroupByOrdinal` | false | true | false | false | GROUP BY 能否用序号 |
| `isSortByAlias` | true | true | true | true | ORDER BY 能否用别名 |
| `isBangEqualAllowed` | false | false | true | true | `!=` 是否合法 |
| `isMinusAllowed` | false | true | false | false | MINUS 是否合法 |
| `isApplyAllowed` | false | true | false | true | APPLY/LATERAL 是否合法 |
| `isHavingAlias` | false | true | true | true | HAVING 能否引用 SELECT 别名 |
| `allowCharLiteralAlias` | false | false | true | false | 字符字面量能否作别名 |
| `isNonStrictGroupBy` | false | false | true | true | GROUP BY 是否允许非严格分组 |
| `isInsertSubsetColumnsAllowed` | false | false | true | false | INSERT 能否只指定部分列 |

这些开关在验证过程中被反复检查，决定是否接受某种语法行为。

## 4.8 从源码跟踪一次验证过程

跟踪 `SELECT e.name FROM emp e WHERE e.id > 10` 的验证过程：

```
1. validate(SqlSelect)
   → 创建 EmptyScope + CatalogScope
   → validateScopedExpression()

2. registerQuery(SqlSelect)
   → 创建 SelectNamespace，注册到 namespaces
   → 创建 SelectScope，注册到 scopes
   → 递归注册 FROM 子句:
     registerQuery(IdentifierNamespace("emp AS e"))
       → 创建 IdentifierNamespace
       → 从 CatalogReader 获取 emp 表的行类型
       → 添加到 SelectScope 的子列表
   → 递归注册 WHERE 子句（无新 Scope）

3. validateNamespace(SelectNamespace)
   → validateSelect(SqlSelect)

4. validateSelect()
   → 验证 FROM: 已注册，类型已知
   → 验证 WHERE:
     deriveType(SelectScope, SqlBasicCall(>))
       → deriveType(SelectScope, SqlIdentifier("e.id"))
         → resolve(["e", "id"], SelectScope)
           → 找到 emp AS e 的 Namespace
           → 找到 id 列 → INTEGER
       → deriveType(SqlLiteral(10)) → INTEGER
       → 检查 > 操作符参数类型：INTEGER > INTEGER → 合法
       → 返回类型：BOOLEAN
   → 验证 SELECT 列表:
     deriveType(SelectScope, SqlIdentifier("e.name"))
       → resolve(["e", "name"]) → VARCHAR(100)
   → 设置 SelectNamespace.rowType = [name VARCHAR(100)]

5. 返回验证后的 SqlNode（可能有改写）+ 所有节点的类型信息
```

---

## 本章小结

SQL 验证器通过 Namespace（描述查询产出什么）和 Scope（描述名称可见性）两个正交的数据结构，在 SqlNode AST 上建立了完整的语义模型。名称解析通过 Scope 的 `resolve()` 方法沿作用域链搜索，类型推导通过 `deriveType()` 递归推导每个表达式的类型，SqlConformance 控制不同数据库方言的兼容性。下一章将进入 SqlToRelConverter——它如何将验证后的 SqlNode 转换为 RelNode 关系代数树。
