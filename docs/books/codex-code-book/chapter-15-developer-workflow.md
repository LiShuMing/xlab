# 第15章：开发者工作流——从使用者到贡献者

> 源码版本：2026-05-04
> 关键文件：`AGENTS.md`, `docs/`, `cli/src/main.rs`（debug 子命令）, `.github/`

---

## 15.1 AGENTS.md：开发指引的宪法

`/Users/lism/work/codex/AGENTS.md` 是 Codex 项目的开发指引文档，包含了所有关键约定：

### Rust 编码规范

- **模块大小限制**：<500 LoC（超过 800 必须拆分）
- **Crate 命名**：必须以 `codex-` 为前缀
- **可见性**：模块默认 private，通过 `pub use` 显式导出
- **弱引用**：遇到循环引用时使用 `Weak` 而非 `Arc`
- **无单次使用辅助方法**：如果某个方法只被调用一次，内联它

### TUI 风格

- 遵循现有 ratatui 组件模式
- 颜色和样式通过 `style.rs` 统一管理
- 新组件添加到对应的子目录（`chatwidget/`, `bottom_pane/` 等）

### App Server API 开发

- API 开发在 app-server v2 路径下进行
- **协议优先**：先定义 wire format（`#[ts(export_to)]`, `#[serde(tag = "type")]`），再实现业务逻辑
- 保证跨语言（Rust ↔ TypeScript）的兼容性

---

## 15.2 Debug 子命令：开发者的工具箱

```rust
// cli/src/main.rs — debug 子命令
codex debug prompt-input "test query"   // 查看实际发送到 LLM 的 prompt（不发起 API 调用）
codex debug clear-memories              // 清除记忆
codex debug sandbox                     // 沙箱调试工具
codex debug config                      // 查看当前配置
codex debug features                    // 查看功能开关状态
```

这些 debug 命令对开发者和高级用户至关重要：
- `prompt-input`：不发起 API 调用，只输出构造好的 prompt JSON。这让你可以在不消耗 API 配额的情况下查看 System Prompt 的完整内容
- `sandbox`：沙箱相关的调试命令，帮助排查沙箱拦截问题
- `config`：显示所有配置来源及其优先级（非常适合于排查"为什么这个设置没生效"）

---

## 15.3 功能开关（Feature Flags）

```rust
// cli/src/main.rs — --enable/--disable
codex --enable experimental-feature-x
codex --disable deprecated-feature-y
```

Codex 支持运行时功能开关，用于：
- 灰度发布新功能
- A/B 测试
- 紧急关闭有问题的功能

启用了实验性功能的 Client 在连接 App Server 时会带上能力声明，App Server 根据 Client 声明的能力决定发送哪些事件、暴露哪些 API。

---

## 15.4 测试策略

### 测试金字塔

```
        ┌──────┐
        │ E2E  │  少量：完整 CLI 流程
        ├──────┤
        │ 集成  │  中等：多 crate 协作场景
        ├──────┤
        │ 单元  │  大量：单函数/单模块行为
        └──────┘
```

测试文件命名约定：`<module>_tests.rs` 放在对应模块旁边。

### 关键测试模式

```rust
// 内联测试模块（使用 #[path] 属性）
#[cfg(test)]
#[path = "exec_policy_tests.rs"]
mod tests;
```

测试被放在独立文件但通过 `#[path]` 属性关联，这样既保持了源文件的简洁，又不会丢失测试代码与源代码的关联。

---

## 15.5 发布流程

```rust
// tui/src/update_action.rs + tui/src/updates.rs
// 检查更新 → 下载新版本 → 替换当前二进制 → 通知用户重启
```

Codex 有内建的自更新机制：检查 GitHub Releases → 下载新版本 → 替换当前二进制（通过 `self_replace` crate）。

---

## 15.6 版本注入

```rust
// tui/src/version.rs
// 编译时通过环境变量注入版本信息
// CODEX_VERSION, CODEX_GIT_HASH, CODEX_BUILD_DATE
```

版本信息在编译时注入，避免了运行时读取文件的复杂性。CI 系统在构建时设置这些环境变量。

---

## 15.7 本章要点

1. **AGENTS.md 是开发指引的宪法**：模块大小、命名规范、可见性规则。
2. **协议优先**：先定义 wire format，再实现业务逻辑，保证跨语言兼容。
3. **debug 子命令**：prompt-input、sandbox、config 等是开发者的核心工具。
4. **功能开关**：支持灰度发布和 A/B 测试。
5. **测试金字塔**：单测（大量）+ 集成（中等）+ E2E（少量）。
6. **自更新机制**：检查 GitHub Releases → 下载 → self_replace。
