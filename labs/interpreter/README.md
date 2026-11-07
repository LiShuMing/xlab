# interpreter —— 把源码变成结果的三条路

同一件事的三种执行策略：字符流先变成 AST（Abstract Syntax Tree，抽象语法树），之后可以
在树上逐节点求值、让解释器解释自己的源码，或者编译成机器码直接跑。三者互不依赖，各自
能单独构建。

| 目录 | 做法 | 前置 | 入口 |
| --- | --- | --- | --- |
| `tree-walk/` | lexer / parser 生成 AST，递归遍历求值 | C++20、CMake | [tree-walk/README.md](tree-walk/README.md) |
| `self-hosting/` | 用 C 写一个能解释自身源码的解释器 | C 编译器（gcc / clang）与 make | [self-hosting/README.md](self-hosting/README.md) |
| `jit/` | AST 生成 LLVM IR，再由 JIT（Just-In-Time compilation，即时编译）执行 | LLVM 开发包、CMake | [jit/README.md](jit/README.md) |

## 为什么放在一起

三个目录回答同一个问题的不同深度：**一段源码到底怎么变成结果**。

- `tree-walk/` 是最小闭环：只要 lexer、parser 和一棵树就能跑，代价是每个节点都要重新解释。
- `self-hosting/` 换了个问题：解释器自己的源码也喂给它，看自举在哪一步断裂。
- `jit/` 把 AST 交给 LLVM 后端，观察"解释一次"与"编译一次、执行多次"的分界。

单独看一个只能看到一种策略；并排看才能比较三者在启动开销、执行开销和实现复杂度上的
取舍。

## 独立边界

- 三者各自带构建入口，不共享 lexer、parser 或 codegen：删掉任意两个，剩下的仍能构建运行。
- `tree-walk/` 与 `jit/` 通过仓库统一的 `cmake/XlabDependencies.cmake` 取 GoogleTest 与
  Google Benchmark，不写死第三方源码路径。
- `self-hosting/` 只有 C 源码与 Makefile，不依赖 CMake。
