# simd —— 向量化写法对照

同一段粒子模拟分别用标量、SSE（Streaming SIMD Extensions）、AVX2 实现，比较手写内建函数
与编译器自动向量化的差距；外加一个 `movemask` 过滤示例和 CPU 特性探测。

`src/simd/*.cpp` 各自带 `main`，独立编译成 `bin/<name>`。

| 目标 | 内容 |
| --- | --- |
| `float_simd` | 1024×64 粒子对 10 个中心的受力计算，`VEC_*` 宏切换标量 / SSE / AVX 实现并输出时间统计 |
| `simd1` | 三个 double 加法的写法对照（朴素循环、`_mm256_*` 内建函数、GCC vector extension） |
| `test_simd` | 打印本机 CPU 支持的特性（SSE / SSE2 / AVX / AVX2 / AVX-512F） |
| `test_a` | 最小 C++ 程序，验证工具链 |

`obj_simd1*.s` 是 `simd1` 的 `objdump -d` 反汇编记录，用于对照三种写法的实际指令，不参与构建。

## 前置条件

- `g++`，C++17 即可（Makefile 固定 `-std=c++17`，GCC 9 也能构建）
- CPU 支持 AVX2；`test_simd` 会打印实际支持情况

换机器时若缺 AVX2，用 `make AVX=` 覆盖编译选项，或改 `float_simd.cpp` 顶部的 `VEC_*` 宏。

## 使用

```sh
make                    # 构建全部目标到 bin/
make run-test_simd
make run-simd1
./bin/float_simd        # 按回车开始，随后打印 Mean/Stddev/Min/Max
make clean
```

`float_simd` 开头的 `getchar()` 是留给性能分析器挂载的暂停点，交互运行时按回车继续；
脚本里非交互运行用 `./bin/float_simd < /dev/null`，否则会一直等标准输入。
