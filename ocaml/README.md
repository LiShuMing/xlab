# OCaml 学习实验室

从函数式编程基础走到表达式解释器与常量折叠。项目只依赖 OCaml 标准库，
使用 OCaml 5.5.2 和 Dune 3.24.2；版本分别固定在
[.ocaml-version](.ocaml-version) 和 [ocaml-lab.opam](ocaml-lab.opam)。

## 环境和运行

在仓库根目录执行：

```bash
bash tools/setup-learning.sh ocaml
source tools/learning-env.sh
cd ocaml
dune build
dune runtest
dune exec ocaml-lab
```

安装脚本使用用户目录中的独立工具链，不修改 shell 启动文件。
新终端需要重新 `source tools/learning-env.sh`；自定义安装位置可设置
`XLAB_LEARNING_HOME`。安装过程需要网络，项目构建本身不调用外部服务。

示例将 `let x = 2 + 3 in x * (4 + 5)` 折叠为
`let x = 5 in x * 9`，求值结果为 `45`。

## 阅读顺序

1. [中文教程](TUTORIAL.md)：REPL、类型、模式匹配、模块、解释器、测试与练习。
2. [basics.ml](lib/basics.ml)：`option`、`result`、高阶函数、Map functor。
3. [expr.mli](lib/expr.mli)、[expr.ml](lib/expr.ml)：AST、词法作用域、显式错误传播。
4. [test_lab.ml](test/test_lab.ml)：基础断言和常量折叠前后的值/错误对照。

`lib/` 是库，`bin/` 是演示程序，`test/` 是可执行测试。
Dune 输出位于 `_build/`，不提交生成文件。

## 边界

这是手工构造 AST 的语言实验，不包含文本 parser 或 SQL 优化器。
OCaml `int` 是有界机器整数；本例不检测溢出，不宣称数学整数语义。
常量折叠保留变量查找错误，不将 `0 * missing` 擅自改成 `0`。
Lean 项目证明的是其自己的自然数 AST，不是对本 OCaml 程序的形式化认证。
