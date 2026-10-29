# Lean 4 学习实验室

使用 Lean 4.35.0 和随工具链提供的 Lake，版本固定在
[lean-toolchain](lean-toolchain)。只使用工具链附带的 `Std`，不依赖 Mathlib。

## 环境和运行

在仓库根目录执行：

```bash
bash tools/setup-learning.sh lean4
source tools/learning-env.sh
cd lean4
lake build xlab-lean xlab-tests
lake exe xlab-lean
lake exe xlab-tests
```

工具链位于用户专属安装目录。新终端重新 source 环境脚本；
安装需网络，已安装工具链后的项目构建不需要下载外部包。
`.lake/` 是生成目录，不提交。构建把 Lean 警告视为错误，
练习中的未完成证明不要加入默认构建。

## 阅读顺序

1. [中文教程](TUTORIAL.md)：函数、命题、归纳和优化器正确性证明。
2. [Basics.lean](Xlab/Basics.lean)：列表递归与 `sum_append`。
3. [Expr.lean](Xlab/Expr.lean)：自然数表达式、求值和常量折叠。
4. [Proofs.lean](Xlab/Proofs.lean)：对任意表达式和环境证明求值结果不变。
5. [Tests.lean](Tests.lean)：编译期断言、定理应用和运行期枚举。

示例 `(2 + 3) * x` 折叠为 `5 * x`，当 `x = 9` 时结果为 `45`。
定理 `foldConstants_correct` 在构建期间由 Lean 内核检查，
其范围是这里定义的 `Nat` AST 和全定义变量环境。
它不涵盖 SQL NULL、浮点数、机器整数溢出、OCaml 实现或完整数据库优化器。
