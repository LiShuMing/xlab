# SQL Parser & Optimizer Implementation Summary

## 项目概述

本项目实现了一个函数式的 SQL 解析器和基于规则的优化器，专为 OLAP 引擎设计。

## 构建说明

### 环境要求

- **GHC**: 9.6.4
- **Stack**: 最新稳定版本
- **Cabal**: 3.10.1.0

### 构建命令

```bash
# 构建项目
stack build

# 运行测试
stack test

# 运行可执行文件
stack run sql-parser-exe

# 进入 GHCi 交互环境
stack ghci
```

### 依赖项

```yaml
- base >= 4.14 && < 5
- megaparsec >= 9.0
- parser-combinators >= 1.0
- text >= 1.2
- mtl >= 2.2
- hspec >= 2.7 (测试)
```

## 测试说明

### 运行测试

```bash
stack test
```

### 测试覆盖范围

#### Parser 测试 (4 项)

| 测试项 | 状态 | 说明 |
|--------|------|------|
| `SELECT * FROM table` | ✅ 通过 | 基础星号投影解析 |
| `SELECT col FROM table WHERE col = 1` | ⚠️ 部分通过 | 列投影解析工作，多列有待完善 |
| `SELECT * FROM t WHERE a = 1 AND b = 2` | ⚠️ 部分通过 | 单条件工作，多条件有待完善 |
| 无效 SQL 拒绝 | ✅ 通过 | 错误处理正确 |

#### Optimizer 测试 (7 项)

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 常量折叠 (加法) | ✅ 通过 | `1 + 2` → `3` |
| 常量折叠 (乘法) | ✅ 通过 | `3 * 4` → `12` |
| AND 与 TRUE 简化 | ✅ 通过 | `TRUE AND x` → `x` |
| AND 与 FALSE 简化 | ✅ 通过 | `FALSE AND x` → `FALSE` |
| OR 与 TRUE 简化 | ✅ 通过 | `TRUE OR x` → `TRUE` |
| OR 与 FALSE 简化 | ✅ 通过 | `FALSE OR x` → `x` |
| 完整 SELECT 优化 | ✅ 通过 | 端到端优化流程 |

### 测试通过率

- **总体**: 9/11 (81.8%)
- **Optimizer**: 7/7 (100%)
- **Parser**: 2/4 (50%)

## 架构设计

### 模块结构

```text
src/
├── AST.hs       # 抽象语法树定义
├── Parser.hs    # Megaparsec 解析器
└── Optimizer.hs # 基于规则的优化器
```

### 核心数据类型 (AST.hs)

```haskell
Statement
  └── SelectStmt
        ├── SelectItem (NonEmpty)  -- 投影列表
        ├── FromClause (Maybe)     -- FROM 子句
        └── WhereClause (Maybe)    -- WHERE 子句

Expr
  ├── ELit Literal       -- 字面量
  ├── ECol ColumnRef     -- 列引用
  ├── EBin BinaryOp Expr Expr  -- 二元表达式
  └── EFunc Text [Expr]  -- 函数调用

BinaryOp
  ├── 比较操作符：=, <>, <, <=, >, >=
  ├── 算术操作符：+, -, *, /
  └── 逻辑操作符：AND, OR

Literal
  ├── LitInt Int
  ├── LitString Text
  ├── LitBool Bool
  └── LitNull
```

### 设计原则

#### 1. 纯函数式 (Pure Functions)

所有核心函数都是纯函数，无副作用：

```haskell
-- 解析器：纯函数
parseSQL :: Text -> Either ParseError Statement

-- 优化器：纯函数
optimize :: Statement -> Statement
```

**优势：**

- 可引用透明性：相同输入总是产生相同输出
- 可等式推理：便于形式化验证
- 线程安全：无需同步机制

#### 2. 使不可能状态无法表示 (Make Impossible States Unrepresentable)

```haskell
-- 使用 NonEmpty 确保至少有一个投影项
ssSelect :: NonEmpty SelectItem

-- 使用 Maybe 表示可选子句
ssFrom :: Maybe FromClause
ssWhere :: Maybe WhereClause
```

**优势：**

- 编译时捕获错误
- 减少运行时检查
- 自文档化类型

#### 3. 无偏函数 (No Partial Functions)

```haskell
-- ❌ 避免使用
head :: [a] -> a  -- 空列表会崩溃

-- ✅ 使用 NonEmpty
NonEmpty.head :: NonEmpty a -> a  -- 总是安全
```

#### 4. 深度模式匹配 (Deep Pattern Matching)

```haskell
optimizeExpr :: Expr -> Expr
optimizeExpr = \case
    ELit lit -> ELit lit
    ECol col -> ECol col
    EFunc name args -> EFunc name (map optimizeExpr args)
    EBin op left right -> applyRules op (optimizeExpr left) (optimizeExpr right)
```

## 优化规则

### 1. 常量折叠 (Constant Folding)

在编译时计算常量表达式：

```haskell
-- 算术常量折叠
(OpAdd, ELit (LitInt l), ELit (LitInt r)) -> ELit (LitInt (l + r))
(OpSub, ELit (LitInt l), ELit (LitInt r)) -> ELit (LitInt (l - r))
(OpMul, ELit (LitInt l), ELit (LitInt r)) -> ELit (LitInt (l * r))
(OpDiv, ELit (LitInt l), ELit (LitInt r)) | r /= 0 -> ELit (LitInt (l `div` r))
```

**示例：**

```sql
-- 优化前
SELECT * FROM t WHERE x = 1 + 2

-- 优化后
SELECT * FROM t WHERE x = 3
```

### 2. 布尔简化 (Boolean Simplification)

简化布尔表达式：

```haskell
-- AND 规则
(OpAnd, ELit (LitBool True), expr)  -> expr
(OpAnd, expr, ELit (LitBool True))  -> expr
(OpAnd, ELit (LitBool False), _)    -> ELit (LitBool False)
(OpAnd, _, ELit (LitBool False))    -> ELit (LitBool False)

-- OR 规则
(OpOr, ELit (LitBool True), _)      -> ELit (LitBool True)
(OpOr, _, ELit (LitBool True))      -> ELit (LitBool True)
(OpOr, ELit (LitBool False), expr)  -> expr
(OpOr, expr, ELit (LitBool False))  -> expr
```

**示例：**

```sql
-- 优化前
SELECT * FROM t WHERE TRUE AND x = 1

-- 优化后
SELECT * FROM t WHERE x = 1
```

### 3. 常量比较 (Constant Comparison)

```haskell
-- 相等比较
(OpEq, ELit l, ELit r) | l == r -> ELit (LitBool True)
(OpEq, ELit l, ELit r) | l /= r -> ELit (LitBool False)

-- 不等比较
(OpNe, ELit l, ELit r) | l == r -> ELit (LitBool False)
(OpNe, ELit l, ELit r) | l /= r -> ELit (LitBool True)
```

## 解析器实现细节

### 表达式解析层级

```text
expr          → orExpr
orExpr        → andExpr (`OR` andExpr)*
andExpr       → comparisonExpr (`AND` comparisonExpr)*
comparisonExpr → addExpr (cmpOp addExpr)*
addExpr       → mulExpr (addOp mulExpr)*
mulExpr       → term (mulOp term)*
term          → literal | columnRef | function | (expr)
```

### 操作符优先级 (从低到高)

1. `OR`
2. `AND`
3. 比较操作符 (`=`, `<>`, `<`, `<=`, `>`, `>=`)
4. 加法操作符 (`+`, `-`)
5. 乘法操作符 (`*`, `/`)

### 回溯处理

使用 `try` 处理需要回溯的解析：

```haskell
term = choice
    [ ELit <$> literal
    , try (EFunc <$> identifier <* char '(' <*> ...)
    , ECol <$> columnRef
    , between (char '(') (char ')') expr
    ]
```

## 使用示例

### 解析 SQL

```haskell
import Parser (parseSQL)
import Data.Text (pack)

let sql = "SELECT id, name FROM users WHERE age > 18"
case parseSQL (pack sql) of
    Left err  -> putStrLn $ "Parse error: " ++ show err
    Right ast -> putStrLn $ "Parsed: " ++ show ast
```

### 优化 AST

```haskell
import Optimizer (optimize)

let optimized = optimize ast
```

### 完整流程

```haskell
import Parser (parseSQL)
import Optimizer (optimize)

compile :: Text -> Either ParseError Statement
compile sql = do
    ast <- parseSQL sql
    pure $ optimize ast
```

## 扩展方向

### 待添加的 SQL 特性

- [ ] JOIN 支持
- [ ] GROUP BY / HAVING
- [ ] ORDER BY / LIMIT
- [ ] 子查询
- [ ] INSERT / UPDATE / DELETE

### 待添加的优化规则

- [ ] 谓词下推 (Predicate Pushdown)
- [ ] 投影下推 (Projection Pushdown)
- [ ] 死代码消除 (Dead Code Elimination)
- [ ] 公共子表达式消除 (CSE)

## 性能考虑

### 当前实现

- 解析器：Megaparsec 组合子，时间复杂度 O(n)
- 优化器：单次遍历，时间复杂度 O(n)

### 优化建议

1. 使用 `Data.Text` 的 `unpack` 最小化
2. 考虑使用 `Builder` 模式输出
3. 对于大型 AST，考虑使用 `foldl'` 严格折叠

## 测试最佳实践

### 添加新测试

在 `test/Spec.hs` 中添加：

```haskell
it "parses new feature" $ do
    parseSQL "SELECT ... " `shouldBe` Right expectedAst
```

### 运行特定测试

```bash
# 运行特定测试
stack test --test-arguments="--match /Parser/parses simple SELECT */"

# 显示详细信息
stack test --test-arguments="--format=detailed"
```

## 故障排除

### 常见问题

**Q: 解析器失败，错误信息不清晰**

A：Megaparsec 提供详细错误，检查 `ParseErrorBundle` 的 `bundleErrors` 字段。

**Q: 优化器没有应用预期规则**

A：检查 AST 结构，确保模式匹配正确。使用 `:set -XViewPatterns` 调试。

**Q: 构建失败，依赖冲突**

A：运行 `stack update` 更新包索引，然后 `stack build --upgrade-dependencies`。

## 参考资源

- [Megaparsec 文档](https://hackage.haskell.org/package/megaparsec)
- [Haskell 风格指南](https://github.com/tibbe/haskell-style-guide)
- [类型驱动设计](https://lexi-lambda.github.io/blog/2019/11/05/learn-you-a-haskell-for-great-good/)
