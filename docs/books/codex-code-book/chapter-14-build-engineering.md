# 第14章：跨平台构建工程——Cargo × Bazel 双构建系统

> 源码版本：2026-05-04
> 关键文件：`Cargo.toml`（workspace）, `BUILD.bazel`, `cli/src/main.rs`（arg0 dispatch）, `codex-rs/.bazelversion`

---

## 14.1 双构建系统的设计动机

Codex 使用 Cargo 和 Bazel 两个构建系统，这在 Rust 项目中不常见。选择这种设计的原因：

- **Cargo**：Rust 生态的标准工具，开发迭代快，IDE 支持好，crate 发布方便
- **Bazel**：Google 的构建系统，适合大规模 monorepo，支持多语言混合构建，缓存和增量编译更优，适合 CI/CD

实际策略：**Cargo 是主要开发工具，Bazel 用于 CI 和正式发布构建**。Cargo.toml 中的 workspace 定义是"真理之源"，Bazel 规则从 Cargo.toml 派生。

---

## 14.2 Workspace 组织

```toml
# Cargo.toml (workspace root)
[workspace]
members = [
    # 109 个 crates...
]
```

109 个 crate 分为几大类：

| 类别 | 示例 Crate | 数量 |
|------|-----------|------|
| 核心库 | `codex-core`, `codex-protocol`, `codex-config` | ~12 |
| 平台抽象 | `codex-linux-sandbox`, `windows-sandbox-rs`, `sandboxing` | ~6 |
| 网络与 API | `codex-api`, `codex-client`, `model-provider`, `rmcp-client` | ~10 |
| 文件与 Shell | `file-system`, `shell-command`, `shell-escalation` | ~5 |
| 持久化 | `thread-store`, `rollout` | ~4 |
| 前端 | `tui`, `app-server`, `app-server-transport` | ~8 |
| CLI | `cli` | 1 |
| 工具/辅助 | `apply-patch`, `utils-*`, `git-utils` | ~25 |
| 测试与追踪 | `rollout-trace`, `thread-manager-sample` | ~5 |
| 集成与 MCP | `codex-mcp`, `codex-apps`, `codex-plugins` | ~10 |

---

## 14.3 Arg0 分发：一个二进制，多个身份

```rust
// cli/src/main.rs:730-735
fn main() -> anyhow::Result<()> {
    arg0_dispatch_or_else(|arg0_paths: Arg0DispatchPaths| async move {
        cli_main(arg0_paths).await?;
        Ok(())
    })
}
```

这类似 busybox 的设计——同一个二进制文件，通过 `argv[0]` 区分角色：

```
codex                   → 交互式 TUI（默认）
codex exec              → 非交互模式
codex app-server        → App Server 守护进程
codex-linux-sandbox     → Linux 沙箱辅助进程（当 argv[0] 匹配时自动路由）
codex-mcp-server        → MCP Server 模式
```

`arg0_dispatch_or_else` 检查 `argv[0]` 是否匹配平台相关的预定义名称（如 `codex-x86_64-unknown-linux-musl`），如果匹配就直接执行对应的子命令。这使得 Codex 可以部署为多个硬链接/符号链接，各自指向不同的功能。

---

## 14.4 Release Profile：极致优化

```toml
# Cargo.toml
[profile.release]
lto = "fat"            # 链接时优化（全程序）
strip = "symbols"      # 剥离调试符号
codegen-units = 1      # 单个代码生成单元（最大化内联）
panic = "abort"        # panic 直接中止（减小二进制大小）
```

这些设置追求的是"最小化 + 最快化"：
- `lto = "fat"`：整个 crate 图做链接时优化，显著减小二进制体积和提升运行速度（但编译时间大幅增加）
- `codegen-units = 1`：LLVM 可以将更多函数内联，但并行编译能力降低
- `strip = "symbols"`：发布二进制不含调试符号

---

## 14.5 跨平台适配

### 条件编译

Codex 大量使用 `#[cfg(target_os = "...")]` 实现平台差异：

```rust
// sandboxing/src/lib.rs
#[cfg(target_os = "linux")]
mod bwrap;
#[cfg(target_os = "macos")]
pub mod seatbelt;
#[cfg(target_os = "windows")]
// Windows 沙箱实现
```

### 平台沙箱差异总结

| 功能 | Linux | macOS | Windows |
|------|-------|-------|---------|
| 文件系统隔离 | bubblewrap | Seatbelt (sandbox-exec) | Restricted Token |
| 系统调用过滤 | seccomp BPF | Seatbelt SBPL rules | - |
| 网络控制 | seccomp + proxy | Seatbelt network rules | WFP |
| PTY 支持 | `codex-utils-pty` | 原生 PTY | ConPTY |
| WSL 检测 | `is_wsl1()` | - | - |

---

## 14.6 依赖管理策略

Codex 的依赖策略体现了"控制供应链"的思想：

- **锁定版本**：`Cargo.lock` 被提交到仓库，确保所有开发者和 CI 使用完全相同的依赖版本
- **Pin 上游**：`[patch.crates-io]` 用于覆盖有问题的上游 crate
- **最小化依赖图**：AGENTS.md 强调"避免添加不必要的依赖"，每个新依赖都需要明确的价值证明

---

## 14.7 本章要点

1. **双构建系统**：Cargo 用于开发，Bazel 用于 CI/正式发布。
2. **109 个 crate 在 workspace 中**：按功能分为核心、平台、网络、前端、工具等类别。
3. **Arg0 分发**：一个二进制，通过 argv[0] 区分身份（类似 busybox）。
4. **Release profile 极致优化**：LTO fat + 单 codegen unit + symbol strip。
5. **条件编译**：`#[cfg(target_os)]` 实现三平台差异适配。
6. **依赖管理严谨**：Cargo.lock 入库，patch 上游问题，控制新增依赖。
