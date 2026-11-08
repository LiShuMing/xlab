# llvm —— 看懂 IR，再动手改它

LLVM（Low Level Virtual Machine）把编译流程切成前端、IR（Intermediate Representation，中间
表示）、后端三段。本实验只盯中间那段：先读手写 IR，再读编译器生成的 IR，最后自己写一个
pass 去改它。

四层递进，每层都能跑、都能断言，不是只读文档：

| 层 | 位置 | 学什么 | 怎么验证 |
| --- | --- | --- | --- |
| 1 手写 IR | `src/ir/` | 类型系统、SSA（Static Single Assignment，静态单赋值）、phi、GEP（GetElementPtr）、CFG（Control Flow Graph，控制流图） | `make check` 用 `lli` 跑出 42 / 45 / 36 / 945 |
| 2 编译器产物 | `src/cpp/` | 同一段 C++ 在 `-O0` / `-O2` / `-O3` 下的 IR 形状差异 | `bin/clang/*.ll` 逐个过 `opt -passes=verify` |
| 3 pass 观察 | `scripts/pass-diff.sh` | 单个 pass 到底改了哪几行 | `make passes` 打印指令行数与 unified diff |
| 4 自写 pass | `src/pass/` | new PM（New Pass Manager）插件：只读分析与 IR 改写 | `opt -load-pass-plugin` 加载后断言输出 |

## 前置条件

LLVM 18 工具链装在独立 conda 环境里，不动系统包：

```sh
conda create -y -n llvm18 -c conda-forge --override-channels \
    llvm=18 clang=18 llvmdev=18 clangxx gxx_linux-64
conda activate llvm18
```

| 包 | 提供什么 |
| --- | --- |
| `llvm` | `opt`、`llc`、`lli`、`llvm-as`、`llvm-dis`、`llvm-mca`、`llvm-config` |
| `clang` `clangxx` | 从 C++ 生成 IR 的前端 |
| `llvmdev` | 写 pass 插件需要的 LLVM 头文件 |
| `gxx_linux-64` | 与 LLVM 同源的 C++ 工具链 |

`gxx_linux-64` 不是可选项。本机系统 g++ 固定带 `-D_GLIBCXX_USE_CXX11_ABI=0`（旧 ABI
（Application Binary Interface，应用二进制接口）），用它编出的插件加载进 `opt` 会因
`std::string` 布局不同而崩溃，所以 Makefile 默认 `CXX=x86_64-conda-linux-gnu-g++`。

没激活环境时 `make` 直接 `$(error)` 报错并给出上面的安装命令，不会静默产出空结果。

## 快速开始

```sh
make            # IR 语法校验 + clang 三档 IR + 两个插件，产物落 bin/
make check      # 断言：lli 执行结果、opt verify、自写 pass 生效
make passes     # 逐 pass 打印指令行数与 diff
make help       # 列出全部目标
make clean
```

## 第一层：手写 IR（src/ir/）

用 `lli` 直接跑文本 IR，不经过后端：

```sh
lli src/ir/01_basics.ll; echo $?      # 42
lli src/ir/02_branch_phi.ll           # 45
lli src/ir/03_memory.ll               # 36
lli src/ir/04_loop_invariant.ll       # 945
```

| 文件 | 主题 | 要点 |
| --- | --- | --- |
| `01_basics.ll` | 类型与算术 | 每条指令显式带类型；SSA 名字只赋值一次；标量局部变量不需要 `alloca` |
| `02_branch_phi.ll` | 控制流与 phi | 基本块只有一个终结指令；循环变量靠 `phi` 汇合，前驱列表与 `br` 一一对应 |
| `03_memory.ll` | 内存与 GEP | `alloca` 分栈槽、`GEP` 只算地址、`load`/`store` 才访存；指针也能当循环变量 |
| `04_loop_invariant.ll` | 给 pass 的素材 | 循环内一个不变量乘法、一个依赖循环变量的乘法，看 `licm` 搬走前一个 |

## 第二层：clang 生成的 IR（src/cpp/）

```sh
make ir                                    # 生成 bin/clang/<name>-O0.ll、-O2.ll、-O3.ll
diff -u bin/clang/loop_sum-O0.ll bin/clang/loop_sum-O2.ll | head -40
```

| 文件 | 看什么 |
| --- | --- |
| `loop_sum.cpp` | `-O0` 每个变量一个 `alloca` 加 `load`/`store`；`-O2` 全变成 `phi` |
| `branch.cpp` | `-O0` 是三条 `br` 串起来的 CFG；`-O2` 被 `simplifycfg` 压成 `select` |
| `inline_call.cpp` | `-O0` 每轮 `call @square`；`-O2` 内联后只剩 `mul`/`add` |
| `vectorize.cpp` | `-O3` 出现 `vector.body` 与 `<4 x i32>`，与 `labs/lowlevel/simd` 的手写内建函数同一件事 |

`-O0` 产物由 `clang -O0 -Xclang -disable-O0-optnone` 生成。没有这个开关，每个函数都带
`optnone` 属性，任何 pass 都会跳过它，`-O0` 的 IR 就成了动不了的石头。

## 第三层：逐 pass 观察（make passes）

`scripts/pass-diff.sh <input.ll> [pass ...]` 把每个 pass 单独跑一遍，先让 `opt` 重新打印
输入（丢掉注释与 ModuleID 噪音），再打印指令行数和 unified diff。真实输出节选：

```text
=== loop-mssa(licm)          指令行 13 -> 14
 define i32 @scale_sum(i32 %n, i32 %factor) {
 entry:
+  %k = mul i32 %factor, 7
   br label %loop

 loop:
   %i = phi i32 [ 0, %entry ], [ %i.next, %loop ]
   %acc = phi i32 [ 0, %entry ], [ %acc.next, %loop ]
-  %k = mul i32 %factor, 7
   %v = mul i32 %i, %k
```

`%k` 被提到 `entry`：这就是 LICM（Loop Invariant Code Motion，循环不变量外提）的全部内容。
`-O0` 产物跑 `mem2reg` 更夸张，29 行指令掉到 15 行，`alloca`/`load`/`store` 全消失。

## 第四层：自写 pass（src/pass/）

两个插件覆盖 pass 的两种形态：

| 插件 | 类型 | 教学点 |
| --- | --- | --- |
| `IrStats.so` | 只读分析 | 怎么遍历函数、基本块、指令；为什么返回 `PreservedAnalyses::all()` |
| `MulToShift.so` | IR 改写 | 造指令 → `replaceAllUsesWith` → `eraseFromParent` → 声明分析失效 |

```sh
opt -load-pass-plugin=bin/passes/IrStats.so -passes=ir-stats -disable-output \
    src/ir/04_loop_invariant.ll
# [ir-stats] scale_sum: 8 instructions, 3 blocks, 2 phi, 0 memory ops, 0 calls

opt -load-pass-plugin=bin/passes/MulToShift.so -passes=mul-to-shift -S \
    src/ir/01_basics.ll -o - | grep shl
#   %prod.shl = shl i32 %sum, 1
```

插件只编 `.so`、不链 `libLLVM`：里面的 LLVM 符号由加载它的 `opt` 提供。`make check` 里
除了检查文本替换，还把改写后的 IR 重新交给 `lli` 跑一遍，确认结果仍是 42 —— 改 IR 最容易
犯的错不是编译不过，而是语义被悄悄改掉。

## 命令速查（均已在本机验证）

| 目的 | 命令 |
| --- | --- |
| C++ 生成 IR | `clang -O2 -S -emit-llvm src/cpp/loop_sum.cpp -o -` |
| 文本 IR 转二进制 | `llvm-as src/ir/01_basics.ll -o /tmp/a.bc` |
| 二进制转文本 | `llvm-dis /tmp/a.bc -o -` |
| 跑一段 IR | `lli src/ir/01_basics.ll` |
| 跑单个 pass | `opt -passes=mem2reg -S a.ll -o -` |
| 跑完整 O2 管线 | `opt -passes='default<O2>' -S a.ll -o -` |
| 看支配树 | `opt -passes='print<domtree>' -disable-output a.ll` |
| 看循环结构 | `opt -passes='print<loops>' -disable-output a.ll` |
| 看 IR 变成什么汇编 | `llc a.ll -o a.s` |
| 估算汇编的吞吐与延迟 | `llvm-mca -iterations=10 a.s` |
| 加载自写插件 | `opt -load-pass-plugin=bin/passes/MulToShift.so -passes=mul-to-shift -S a.ll -o -` |

管线语法要点：`default<O2>` 是整套 O2；`function(...)` / `loop-mssa(...)` / `cgscc(...)`
把 pass 限定在对应粒度，例如 `loop-mssa(licm)` 必须套在 loop 粒度里，直接写 `licm` 会报错。

## 两个容易踩的点

- **`optnone` 会让所有 pass 静默跳过。** `clang -O0` 的产物每个函数都带 `optnone`，
  拿它喂 `opt` 会"成功但什么都没改"。要么加 `-Xclang -disable-O0-optnone`，要么直接用
  手写 IR（本实验的 `src/ir/` 没有这个属性）。
- **LLVM 18 用 opaque pointer。** 指针类型只写 `ptr`，不再有 `i32*`；`getelementptr`
  的第一个下标跨数组、第二个才是元素下标，写错不会报类型错，只会算错地址。

## 与 labs/interpreter/jit 的分工

`labs/interpreter/jit/` 用 LLVM 的 C++ API 把 AST 变成 IR 再 JIT（Just-In-Time compilation，
即时编译）执行，回答"怎么用 LLVM"；本实验用命令行工具读 IR、跑 pass、写插件，回答"LLVM 的
优化到底怎么发生"。前者需要 `find_package(LLVM)` 与 JIT 链接，后者只需要 `opt`/`lli` 与一份
头文件，两者互不依赖，可单独删除。
