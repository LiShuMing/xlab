# OCaml：从类型到一个小解释器

目标：读懂类型签名，写出可组合的纯函数，用代数数据类型描述程序，
再实现一个返回明确错误的解释器。先运行 [README](README.md) 中的构建命令。

## 第一课：表达式、函数与交互环境

进入 `ocaml/` 后运行 `ocaml`，在交互环境输入：

```ocaml
let square x = x * x;;
square 7;;
List.map square [1; 2; 3];;
```

结果分别包含 `int -> int`、`49` 和 `[1; 4; 9]`。
`;;` 用于向交互环境提交输入；普通 `.ml` 文件不要求每行加它。
`let` 默认建立不可变绑定，`let rec` 才允许函数直接递归。
应用函数写成 `square 7`，无需 C++ 风格的括号。

再加载项目的基础实现：

```ocaml
#use "lib/basics.ml";;
sum_squares [1; 2; 3];;
```

`sum_squares` 用 `List.fold_left` 累积平方和，得到 `14`。
修改输入为空列表，观察为什么初始累加值必须是 `0`。

练习：写一个用 `List.filter` 保留偶数、再计算平方和的函数。
先写类型 `int list -> int`，再写实现。

## 第二课：用类型表达“可能没有”和“可能失败”

打开 [basics.mli](lib/basics.mli)：

```ocaml
val safe_head : 'a list -> 'a option
val safe_divide : int -> int -> (int, string) result
```

`'a` 是类型变量，表示 `safe_head` 不依赖元素的具体类型。
`option` 的构造器是 `Some value` 与 `None`；
`result` 的构造器是 `Ok value` 与 `Error message`。
调用者通过模式匹配处理每个分支：

```ocaml
match safe_divide 8 0 with
| Ok value -> Printf.printf "%d\n" value
| Error message -> Printf.printf "error: %s\n" message;;
```

观察 `safe_head []` 与 `safe_head ["ocaml"]`。
练习：实现安全的列表索引，负数和越界都返回 `None`。

## 第三课：模块、接口与持久化数据结构

`.mli` 是模块的公开接口，`.ml` 是实现。
本项目库由 Dune 包装成 `Ocaml_lab`，使用者通过
`Ocaml_lab.Basics` 和 `Ocaml_lab.Expr` 访问子模块。

`Map.Make(String)` 是 functor：它接收提供字符串比较规则的模块，
生成以字符串为键的 Map 模块。Map 更新产生新值，不就地改变旧 Map。
`count_words ["ocaml"; "lean"; "ocaml"]` 的结果按键排序：

```ocaml
[("lean", 1); ("ocaml", 2)]
```

练习：在现有实现旁增加大小写归一化版本，明确空字符串的处理方式。
不要为了一个新例子向项目添加第三方依赖。

## 第四课：用 AST 表达程序

AST 即抽象语法树：用结构描述表达式，而不是直接解释字符串。
[expr.mli](lib/expr.mli) 定义五种节点：

```ocaml
type t =
  | Int of int
  | Var of string
  | Add of t * t
  | Mul of t * t
  | Let of string * t * t
```

例如 `Add (Int 2, Int 3)` 表示 `2 + 3`。
每一种构造器都是一个必须考虑的语义分支。
相对于 C++ 中使用基类和虚函数的 AST，这里主要通过“类型＋模式匹配”组织操作。

解释器类型是：

```ocaml
val eval : (string * int) list -> t -> (int, string) result
```

第一个参数是变量环境。`List.assoc_opt` 从前往后查找，
因此 `Let` 把新绑定放到表头就可以实现词法遮蔽。
绑定的右侧先在外层环境求值，得到值后再扩展环境计算 body。
项目测试分别验证这两个步骤。

`let*` 是本项目为 `Result.bind` 定义的绑定运算符，
把“成功就继续、失败就返回”写成顺序结构，不依赖异常处理。

练习：手工跟踪 `let x = 2 in let x = x + 3 in x * 4` 的环境变化。

## 第五课：常量折叠首先要保持语义

`fold_constants` 递归处理子树，只有左右两边都是整数常量时才计算。
它不会执行变量替换，也不会删除 `Let`。

特别考虑：

```ocaml
Mul (Int 0, Var "missing")
```

在当前解释器中，右侧变量不存在就应返回错误。
如果直接套用代数恒等式变成 `Int 0`，错误会消失。
因此“数学上相等”不足以证明带错误语义的程序可替换。

运行 `dune runtest`。测试对多种表达式和环境比较：

```ocaml
eval environment expression
= eval environment (fold_constants expression)
```

比较结果包括 `Ok` 与 `Error`，而不只是成功值。
这些是有限样例测试，不是对所有输入的形式化证明。
OCaml 的机器整数也不等同于 Lean 示例中的 `Nat`。

练习：增加减法节点，并同步更新 `.mli`、求值、打印、折叠与测试。
再讨论什么前提下允许增加 `0 * e -> 0`。

## 日常开发与后续学习

```bash
dune build                    # 增量构建
dune runtest                  # 执行发生变化的测试
dune exec ocaml-lab            # 运行演示
```

建议按五课逐步学习，每课完成一个练习后再继续。
后续可学习 parser、模块签名、GADT 和 OCaml 5 Domains；
本项目尚未实现这些扩展。

官方资料：[OCaml 手册](https://ocaml.org/manual/)、
[OCaml 学习入口](https://ocaml.org/docs)、
[Dune 文档](https://dune.readthedocs.io/)、
[opam 使用指南](https://opam.ocaml.org/doc/Usage.html)。
