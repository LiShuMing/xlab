# lowlevel —— 贴硬件的优化实验

同一段计算交给 CPU 的不同表达能力之后，代码形状和开销会怎么变。三个实验是同一条线索的
三段：`simd/` 让编译器与内建函数生成向量指令，`nasm/` 直接手写汇编，看清每条指令到底在
做什么；`llvm/` 停在两者中间，读编译器产出的 IR（Intermediate Representation，中间表示）
并自己写 pass 去改它。

| 实验 | 内容 | 入口 |
| --- | --- | --- |
| `simd/` | 标量 / SSE / AVX2（Advanced Vector Extensions 2）三种写法的粒子模拟基准，加 `movemask` 过滤、CPU 特性探测 | [simd/README.md](simd/README.md) |
| `nasm/` | NASM（Netwide Assembler）教程：系统调用、函数调用、栈与 libc 链接、AVX2 指令 | [nasm/README.md](nasm/README.md) |
| `llvm/` | 四层递进学 LLVM（Low Level Virtual Machine）IR：手写 `.ll`、clang 生成三档 IR、`opt` 逐 pass 看 diff、自写 new PM（New Pass Manager）插件 | [llvm/README.md](llvm/README.md) |

## 前置条件

| 实验 | 需要 |
| --- | --- |
| `simd/` | `g++`（C++17 即可，GCC 9 也能构建）；CPU 支持 AVX2 |
| `nasm/` | NASM 2.x；`gcc`/`ld` 用于链接 |
| `llvm/` | LLVM 18 工具链与同源的 C++ 编译器（写 pass 插件用） |

本机没有系统级 NASM，也没有任何 LLVM 工具，两者都装在独立的 conda 环境里：

```sh
conda create -y -n asm nasm
conda create -y -n llvm18 -c conda-forge --override-channels \
    llvm=18 clang=18 llvmdev=18 clangxx gxx_linux-64

conda activate asm
conda activate llvm18   # 叠加而非替换：PATH 里同时有 nasm 与 LLVM
```

只做某一个实验时，激活对应环境即可，直接进子目录构建也行：`make -C labs/lowlevel/llvm`。
`llvm/` 为什么必须用 `gxx_linux-64` 而不是系统 g++，见 [llvm/README.md](llvm/README.md)。

Mac 版本（`*_macos.asm`、`*_mac`）与 ARM64 驱动 `t1_main.c` 只作对照保留，不参与 Linux 构建。

## 快速开始

```sh
make -C labs/lowlevel                     # 构建三个实验的全部目标
make -C labs/lowlevel/nasm run-t1         # 运行单个汇编教程
make -C labs/lowlevel/llvm check          # 跑通 IR 四层的全部断言
./labs/lowlevel/simd/bin/test_simd        # 看本机 CPU 特性探测结果
make -C labs/lowlevel/llvm passes         # 逐 pass 打印指令行数与 diff
```

三个实验的产物都落在各自 `bin/`，`make -C labs/lowlevel clean` 一并删除。
