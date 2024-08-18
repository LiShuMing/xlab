---
chapter: D
part: 附录
title: Rust内核开发入门
source_anchor:
  - rust/
  - rust/kernel/
status: todo
---

# 附录D Rust内核开发入门

## 概述

Linux 7.0已支持Rust内核模块开发，本附录提供Rust内核绑定的快速入门。

## rust/目录结构

```
rust/
├── kernel/          # 内核Rust绑定
│   ├── lib.rs       # 模块入口
│   ├── prelude.rs   # 预导入
│   ├── device.rs    # 设备抽象
│   ├── driver.rs    # 驱动抽象
│   ├── platform.rs  # 平台驱动
│   ├── pci.rs       # PCI驱动
│   ├── gpu.rs       # GPU/DRM抽象
│   ├── block.rs     # 块设备抽象
│   ├── fs.rs        # 文件系统抽象
│   ├── mm.rs        # 内存管理抽象
│   ├── sync.rs      # 同步原语
│   ├── workqueue.rs # 工作队列
│   ├── irq.rs       # 中断抽象
│   ├── net.rs       # 网络抽象
│   ├── task.rs      # 任务抽象
│   └── ...          # 其他绑定
├── macros/          # 过程宏
├── pin-init/        # 安全初始化
├── bindings/        # 自动生成的C绑定
└── helpers/         # C辅助函数
```

## 最小Rust内核模块示例

```rust
// SPDX-License-Identifier: GPL-2.0

//! 最小Rust内核模块示例

use kernel::prelude::*;

module! {
    type: HelloModule,
    name: "hello_rust",
    author: "shuming.lsm",
    description: "A minimal Rust kernel module",
    license: "GPL",
}

struct HelloModule;

impl kernel::Module for HelloModule {
    fn init(_module: &'static ThisModule) -> Result<Self> {
        pr_info!("Hello from Rust kernel module!\n");
        Ok(HelloModule)
    }
}

impl Drop for HelloModule {
    fn drop(&mut self) {
        pr_info!("Goodbye from Rust kernel module!\n");
    }
}
```

## 关键绑定说明

| 绑定文件 | 对应C API | 用途 |
|---------|----------|------|
| `device.rs` | struct device | 设备抽象 |
| `driver.rs` | struct driver | 驱动注册 |
| `pci.rs` | struct pci_driver | PCI驱动 |
| `gpu.rs`/`gpu/` | DRM subsystem | GPU/显示驱动 |
| `block.rs`/`block/` | block subsystem | 块设备驱动 |
| `mm.rs`/`mm/` | mm subsystem | 内存管理操作 |
| `sync.rs`/`sync/` | spinlock/mutex/rcu | 同步原语 |
| `fs.rs`/`fs/` | VFS | 文件系统实现 |

## 构建Rust内核模块

```bash
# 确保安装Rust工具链
rustup default stable

# 编译内核（启用Rust支持）
make LLVM=1 menuconfig
# 启用 CONFIG_RUST=y

# 编译
make LLVM=1 -j$(nproc)
```

## 与AI加速器驱动的关系

Rust的内存安全特性特别适合AI加速器驱动开发：
- `drivers/accel/`中的新驱动可以用Rust重写
- `rust/kernel/gpu.rs`提供了GPU驱动的Rust抽象
- 减少UAF/越界等内存安全漏洞
