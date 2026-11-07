# jit —— 把 AST 交给 LLVM 后端

`tree-walk/` 在语法树上逐节点求值；这里换第三条路：把 AST 降低成 LLVM IR（Intermediate
Representation，中间表示），再由执行引擎即时编译成本机代码。

## 内容

| 路径 | 作用 |
| --- | --- |
| `src/M0_JITSetup.cpp` | 建 LLVM 上下文、模块、执行引擎，跑通"常量 → 机器码"的最小闭环 |
| `src/M1_AST.cpp` | 把表达式解析成 AST，再把 AST 降低为 IR |
| `include/` | 上述两步的头文件与打印工具 |
| `test/` | GoogleTest 用例（AST 解析与 IR 生成） |
| `benchmarks/` | Google Benchmark 用例 |

## 构建

需要 LLVM 开发包（含 `Core`、`Support`、`ExecutionEngine`、`IRCompiler` 组件）与 CMake：

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build
```

测试与基准通过仓库统一的 `cmake/XlabDependencies.cmake` 取依赖，不引用固定的第三方源码
路径；找不到本地源码时会退回已安装的软件包。

## 与相邻目录的关系

- 与 `tree-walk/` 共用"先解析成 AST"这一半，差别只在后半程：解释执行还是编译执行。
- 与 `self-hosting/` 无关：那个是 C 子集解释器，没有 LLVM 依赖。
