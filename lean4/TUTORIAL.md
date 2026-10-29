# Lean 4：从可运行的函数到优化正确性证明

目标：把“看起来正确”变成带明确前提、可由内核检查的命题。
先按 [README](README.md) 安装并构建项目，
然后在 VS Code 安装官方 `leanprover.lean4` 扩展，打开 `lean4/` 目录。
终端环境脚本不会自动修改图形编辑器的 PATH；可从已激活的终端启动编辑器。

## 第一课：Lean 也是编程语言

打开 [Basics.lean](Xlab/Basics.lean)，观察递归定义：

```lean
def sum : List Nat → Nat
  | [] => 0
  | first :: rest => first + sum rest
```

`Nat` 表示自然数，`List Nat` 表示自然数列表。
`def` 定义可计算的值；递归分支处理更短的列表，因此 Lean 能检查终止性。
在临时练习文件中写：

```lean
import Xlab
#check Xlab.sum
#eval Xlab.sum [1, 2, 3]
#check Xlab.safeHead
```

保存文件后用 `lake env lean 文件名.lean` 检查；
其中 `#check` 查看类型，`#eval` 执行求值，结果应包含 `6`。
`safeHead` 使用 `Option`，避免空列表取头这样的未定义操作。

练习：写列表长度函数，先理解递归调用为何终止。

## 第二课：命题、证明与相等

```lean
example : (2 : Nat) + 3 = 5 := by
  rfl
```

`example` 声明一个待检查的命题；`by` 后是构造证明的步骤。
`rfl` 用定义归约证明等式两边相同，不会自动解决任意数学问题。
Lean 的 `=` 是需要证明的相等命题，`==` 是可计算的布尔比较。

本项目 `Tests.lean` 中的 `#guard` 会在编译期检查具体条件。
具体样例通过，与“对任意输入成立”是两种不同的证据。

练习：观察 `example (n : Nat) : n = n := by rfl`。
再尝试证明 `0 + n = n`，查看能否直接使用已有定理或 `simp`。

## 第三课：用归纳证明递归程序性质

项目中的第一个通用性质是：

```lean
theorem sum_append (left right : List Nat) :
    sum (left ++ right) = sum left + sum right := by
  induction left with
  | nil => simp [sum]
  | cons first rest ih => simp [sum, ih, Nat.add_assoc]
```

`++` 拼接列表。证明对 `left` 做结构归纳：

1. 空列表时，展开 `sum` 就能化简。
2. 非空列表时，`ih` 是更短列表上的归纳假设。
3. `simp` 展开定义、使用归纳假设，再用加法结合律整理表达式。

在编辑器中把光标放到每一行末尾，观察目标和假设怎样变化。
不要只记住 tactic 名称，要理解每一步消除了哪个证明义务。

练习：证明自定义长度函数满足拼接长度相加。

## 第四课：建立语义，再写优化

[Expr.lean](Xlab/Expr.lean) 的 `inductive Expr` 定义四种节点：
常量、变量、加法、乘法。`eval` 给出表达式的求值含义。
环境类型 `String → Nat` 为每个变量提供值，因此这里没有未绑定变量错误。
演示环境将 `x` 映射到 `9`，其余变量映射到 `0`。

`smartAdd` 和 `smartMul` 仅在两个操作数都是常量时合并。
`foldConstants` 先递归处理子树，再调用这两个构造函数。

先阅读定义，再运行：

```bash
lake exe xlab-lean
```

应观察到 AST 由 `(2 + 3) * x` 变为 `5 * x`，求值均为 `45`。
此处没有文本 parser，也没有 SQL 类型、NULL 或数据库执行计划。

## 第五课：证明常量折叠正确

[Proofs.lean](Xlab/Proofs.lean) 先证明两个局部性质：

```lean
eval environment (smartAdd left right)
  = eval environment left + eval environment right
```

对 `left` 和 `right` 分别 `cases`，覆盖所有构造器组合；
每个分支展开定义后用 `rfl` 完成。
`<;>` 把后一个 tactic 应用于前一个 tactic 产生的所有子目标。

随后证明整个递归优化：

```lean
theorem foldConstants_correct (expression : Expr) (environment : String → Nat) :
    eval environment (foldConstants expression) = eval environment expression
```

证明对表达式结构归纳。常量和变量分支直接归约；
加法和乘法分支组合局部性质与两个子树的归纳假设。
`simp only` 明确列出允许使用的化简规则，便于跟踪证明依赖。

在项目目录执行：

```bash
lake build xlab-lean xlab-tests
lake env lean Xlab/Proofs.lean
lake exe xlab-tests
```

构建会检查定理；测试程序另外检查有限样例。
项目不使用 `sorry`、`admit` 或自定义公理跳过证明。
可以在临时文件中写 `#print axioms Xlab.Expr.foldConstants_correct`
查看定理的公理依赖；不要把依赖标准逻辑公理与伪造未完成证明混为一谈。

练习：增加减法节点。先说明自然数减法截断为 `0` 的语义，
再扩展求值、折叠和归纳证明。进一步加入 `Let` 时，要重新设计环境语义。

## 与 OCaml 项目对照

| 维度 | OCaml 实验 | Lean 实验 |
| --- | --- | --- |
| 数值 | 有界机器整数 | 任意精度自然数 |
| 变量 | 可缺失，返回 `Error` | 全定义函数环境 |
| 绑定 | 包含词法作用域 `Let` | 当前不含 `Let` |
| 验证 | 有限语义对照测试 | 通用定理＋有限检查 |

两个项目共享学习主题，但其语义并不完全相同；
Lean 定理不自动成为 OCaml 编译产物或真实 SQL 优化器的证明。

官方资料：[Functional Programming in Lean](https://lean-lang.org/functional_programming_in_lean/)、
[Theorem Proving in Lean 4](https://lean-lang.org/theorem_proving_in_lean4/)、
[Lean Reference](https://lean-lang.org/doc/reference/latest/)、
[Lean 安装说明](https://lean-lang.org/install/)。
