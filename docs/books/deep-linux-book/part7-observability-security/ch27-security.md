---
chapter: 27
part: 第七篇 可观测性、安全与调试 —— 让系统透明
title: 安全子系统
source_anchor:
  - security/security.c
  - security/selinux/
  - security/bpf/hooks.c
  - security/apparmor/
  - security/landlock/
  - security/ipe/
  - arch/x86/coco/
  - arch/x86/coco/sev/
  - arch/x86/coco/tdx/
status: done
---

# 第27章 安全子系统

## 写作目标

理解Linux安全子系统的架构，从LSM框架到SELinux到机密计算，掌握安全模块堆叠与机密计算基础。

## 章节大纲

### 27.1 LSM框架

- **精读** `security/security.c`：
  - LSM(Linux Security Module)框架
  - 安全模块堆叠：多个LSM同时生效
  - 钩子函数的调用链
  - `security/lsm.h`/`security/lsm_init.c`
- 主要LSM模块：
  - SELinux：`security/selinux/`
  - AppArmor：`security/apparmor/`
  - BPF LSM：`security/bpf/hooks.c`
  - Landlock：`security/landlock/`——非特权用户的安全沙箱
  - IPE(Integrity Policy Enforcement)：`security/ipe/`
  - Smack：`security/smack/`
  - TOMOYO：`security/tomoyo/`
  - LoadPin：`security/loadpin/`
  - Yama：`security/yama/`

### 27.2 SELinux

- `security/selinux/`概览
  - 安全上下文与策略
  - AVC(Access Vector Cache)
  - 类型强制(Type Enforcement)模型
- *数据库视角*：数据库进程的SELinux策略配置

### 27.3 密钥管理

- `security/keys/`：内核密钥环
  - 用户/会话/进程/线程密钥环
  - 密钥类型与操作

### 27.4 机密计算

- **精读** `arch/x86/coco/`：
  - `core.c`：机密计算通用基础设施
  - AMD SEV/SEV-ES/SEV-SNP：`arch/x86/coco/sev/`
    - 加密虚拟机的内存隔离
    - SNP的完整性保护
  - Intel TDX：`arch/x86/coco/tdx/`
    - 可信域(Trust Domain)
    - CPU状态的加密保护
- 机密计算的安全模型与攻击面
- *AI视角*：推理服务多租户场景的安全隔离——机密计算 + cgroup

## 关键源文件清单

| 文件/目录 | 关注点 |
|-----------|--------|
| `security/security.c` | LSM框架核心 |
| `security/selinux/` | SELinux实现 |
| `arch/x86/coco/sev/` | AMD SEV |
| `arch/x86/coco/tdx/` | Intel TDX |

## 跨章依赖

- 依赖第25章（eBPF）：BPF LSM是LSM框架的模块之一
- 依赖第13章（内存安全）：KASAN/KFENCE与安全防护的互补
