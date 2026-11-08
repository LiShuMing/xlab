# nasm —— 手写汇编教程

在 Linux x86_64 上用 NASM（Netwide Assembler）写的最小可运行程序，从裸系统调用到与 libc
链接。每个目标都是独立单元，构建产物统一落在 `bin/`。

## 前置条件

NASM 2.x。本机装在 conda 环境里：

```sh
conda create -y -n asm nasm
conda activate asm
make            # 找不到 nasm 时 make 会直接报错并提示安装方式
```

也可以用 `make NASM=/path/to/nasm` 指定可执行文件。

## 目标

三类目标的链接方式不同，Makefile 按类别分派：

| 目标 | 源文件 | 链接方式 | 说明 |
| --- | --- | --- | --- |
| `t1` | `src/tutorial/t1_linux.asm` | `ld` | 1..10 求和，退出码 55 |
| `t2` | `src/tutorial/t2.asm` | `ld` | 调用本地函数，退出码 49 |
| `t3` | `src/tutorial/t3.asm` | `ld` | 汇编里实现 `strlen`，退出码为字符串长度 |
| `t5` | `src/tutorial/t5.asm` | `ld` | AVX2 `vphaddd` 折叠 8 个整数 |
| `t6` | `src/tutorial/t6_linux.asm` | `ld` | 写标准输出画三角形 |
| `hello` | `src/hello/hello.asm` | `ld` | `sys_write` 输出 |
| `hello2` | `src/hello/hello2.asm` | `ld` | 传统 `int 0x80` 调用 |
| `average` | `src/tutorial/average.asm` | `gcc` | 参数求平均，`make run-average ARGS="1 2 3"` |
| `fib` | `src/tutorial/fib.asm` | `gcc` | 前 90 个斐波那契数 |
| `power` | `src/tutorial/power.asm` | `gcc` | 整数幂，`make run-power ARGS="2 10"` |
| `square` | `src/tutorial/square.asm` | 仅目标文件 | 平方函数，供 `demo` 调用 |
| `mywrite` | `src/tutorial/mywrite.asm` | 仅目标文件 | `write` 包装，供 `demo` 调用 |
| `demo` | `src/tutorial/main.c` + 上面两个 `.o` | `gcc` | C 驱动调用汇编函数 |

`*_macos.asm`、`*_mac`、`t1_main.c` 是 ARM64 Darwin 版本，Linux 上不参与构建，只作对照。

## 使用

```sh
make                    # 构建全部目标到 bin/
make run-t1             # 构建并运行单个目标
make run-power ARGS="2 10"
make help               # 列出分类
make clean
```

## 两个容易踩的点

- **退出方式影响输出。** 调用过 `printf` 的程序必须从 `main` 返回（或调用 libc 的 `exit`），
  不能直接走 `sys_exit` 系统调用，否则缓冲区不刷，重定向到文件时看不到输出。
- **绝对地址与 PIE。** 教程代码用绝对地址寻址，Makefile 因此用 `gcc -no-pie` 链接；去掉它
  会得到 `R_X86_64_32S` 重定位错误。
