# Linux 系统观测实验

[kernel-lens](kernel-lens/README.md) 使用 Rust 提供机器配置总览、容器资源范围、
CPU/NUMA、内存、网络和存储观测，以及主动选择后运行的短时基准测试。

需要 Linux、Rust 1.94+ 和 UTF-8 终端；默认只读观察，不自动启动基准。

```sh
make kernel-lens       # 构建
make run_kernel_lens   # release 模式启动 TUI
make test_kernel_lens  # 运行本实验测试
```

完整参数、统计范围、文件测试目录和 perf/BPF 扩展路线见实验运行指南。
