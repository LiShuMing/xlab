---
chapter: C
part: 附录
title: 内核自测体系
source_anchor:
  - tools/testing/selftests/
status: todo
---

# 附录C 内核自测体系

## 概述

Linux内核在`tools/testing/selftests/`下维护了大量的自测用例，是验证内核行为的权威工具。

## 与本书相关的自测目录

| 自测目录 | 相关章节 | 说明 |
|---------|---------|------|
| `selftests/bpf/` | 第25章 | BPF程序测试 |
| `selftests/cgroup/` | 第8章 | cgroup功能测试 |
| `selftests/futex/` | 第16章 | futex功能测试 |
| `selftests/damon/` | 第11章 | DAMON功能测试 |
| `selftests/memfd/` | 第10章 | memfd_create测试 |
| `selftests/mm/` | 第9-12章 | 内存管理测试 |
| `selftests/sched/` | 第7章 | 调度器测试 |
| `selftests/filesystems/` | 第22章 | 文件系统测试 |
| `selftests/io_uring/` | 第23章 | io_uring测试 |
| `selftests/net/` | 第24章 | 网络栈测试 |
| `selftests/irqs/` | 第18章 | 中断测试 |
| `selftests/timers/` | 第19章 | 定时器测试 |
| `selftests/signal/` | 第20章 | 信号测试 |
| `selftests/kcmp/` | 第6章 | 进程比较测试 |
| `selftests/capabilities/` | 第27章 | 能力测试 |
| `selftests/fpu/` | 第6章 | FPU状态测试 |
| `selftests/proc/` | 第6章 | /proc接口测试 |
| `selftests/resctrl/` | 第2章 | Cache/内存带宽测试 |
| `selftests/cpu-hotplug/` | 第9章 | CPU热插拔测试 |
| `selftests/breakpoints/` | 第20章 | 断点测试 |

## 使用方法

```bash
# 编译所有自测
make -C tools/testing/selftests

# 编译特定子系统自测
make -C tools/testing/selftests/bpf

# 运行特定子系统自测
make -C tools/testing/selftests/bpf run_tests

# 运行单个测试
./tools/testing/selftests/mm/madv_populate
```

## kselftest框架

- `tools/testing/selftests/kselftest.h`：测试框架头文件
- 提供PASS/FAIL/XFAIL/SKIP宏
- TAP(Test Anything Protocol)输出格式
