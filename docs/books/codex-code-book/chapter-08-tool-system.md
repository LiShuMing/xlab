# 第8章：Tool 系统——Agent 的手和脚

> 源码版本：2026-05-04
> 关键文件：`core/src/tools/`, `tools/src/`, `core/src/exec.rs`, `core/src/mcp_tool_call.rs`, `core/src/function_tool.rs`

---

## 8.1 Tool 的本质：Agent 的 System Call

如果说 LLM 是大脑，Agent 是执行线程，那么 Tool 就是 Agent 与外部世界交互的唯一接口——恰如操作系统中的 System Call。

Codex 的 Tool 不是"辅助功能"，它是 Agent 存在的全部意义。一个没有任何 Tool 的 Agent 只能和你聊天；一个有 Tool 的 Agent 可以读文件、执行命令、搜索网页、调用远程 API。Tool 的丰富度和安全性直接决定了 Agent 的能力边界。

Tool 调用遵循严格的协议：
```
Agent (LLM)                     Codex (Tool Runtime)
    │                                │
    │ function_call("shell", {cmd})  │
    │───────────────────────────────→│
    │                                │ 1. 权限检查
    │                                │ 2. Sandbox 选择
    │                                │ 3. 执行
    │                                │ 4. 结果格式化
    │     function_call_output(...)  │
    │←───────────────────────────────│
    │                                │
```

---

## 8.2 Tool 类型体系

Codex 将 Tool 分为四个来源，每种有不同的处理路径：

| 类型 | 来源 | 定义位置 | 示例 |
|------|------|---------|------|
| Builtin | Codex 内核内置 | `core/src/tools/handlers/` | shell, read, write, edit, web_search, apply_patch |
| MCP | 外部 MCP Server | `codex-mcp/` → rmcp-client | 任何 MCP 兼容工具 |
| Skill | Skill 文件注册 | `core/src/skills.rs` | 自定义领域工具 |
| Plugin | Plugin 注册 | `core/src/plugins/` | 第三方扩展工具 |

### Tool 定义格式

Codex 使用 `rmcp` crate 的 Tool 模型（兼容 MCP 协议）：

```rust
// tools/src/ — 内部 Tool 定义
// 每个 Tool 有：name, description, inputSchema (JSON Schema)
```

Tool 定义通过 `ts-rs` 导出给 TypeScript，保证前后端对 Tool Schema 的理解一致。

### FunctionTool 接口

```rust
// core/src/function_tool.rs
pub(crate) mod function_tool { ... }
```

每种 Tool 实现一个函数式的调用接口：接收 JSON 参数，返回结果。Tool Handler 负责参数验证、执行、结果序列化。

---

## 8.3 Tool 调用生命周期

一次完整的 Tool 调用生命周期：

```
Phase 1: LLM 发起
  │ LLM 在 SSE 流中返回 function_call 事件
  │ { "name": "shell", "arguments": { "command": "ls -la", "description": "list files" } }
  │
Phase 2: 工具解析
  │ parse_turn_item() → ResponseItem::FunctionCall
  │
Phase 3: 权限检查
  │ ├─→ 该 Tool 是否需要用户批准？
  │ ├─→ 当前 ApprovalPolicy 是什么？
  │ ├─→ 是否有已批准的相同操作（ApprovedCommandPrefix）？
  │ └─→ 如果需要批准 → emit AskForApproval → 等待用户响应
  │
Phase 4: Runtime 选择与执行
  │ ├─→ Builtin: 直接调用 handler
  │ ├─→ MCP: codex-mcp → rmcp-client → MCP Server
  │ ├─→ Skill: skill invocation → 可能会触发新的 Agent Turn
  │ └─→ Plugin: plugin handler
  │
Phase 5: 结果注入
  │ call_output → 格式化 → 注入到 Context 的 conversation history
  │ → 下一轮 ModelClient::stream() 的输入中包含此结果
```

### 权限检查详解

```rust
// core/src/exec_policy.rs
pub fn check_execpolicy_for_warnings(...) -> ... {
    // 检查命令是否匹配某条 execpolicy 规则
    // 返回：允许 / 警告 / 阻止
}
```

权限检查有两个独立层次：

1. **Approval Policy**：全局策略（`AskForApproval::Always/Never/OnRequest`）
   - Always: 每次 Tool 调用都要批
   - Never: 从不（`--dangerously-bypass-approvals-and-sandbox`）
   - OnRequest: 按需（默认）

2. **ExecPolicy**：细粒度的命令级策略
   - 用户可定义规则：哪些命令需要批准，哪些自动允许
   - 支持模式匹配（glob）
   - `check_execpolicy_for_warnings()` 返回最高严重级别

### ApprovedCommandPrefix：用户"记住"的选择

```rust
// core/src/context/approved_command_prefix_saved.rs
pub(crate) struct ApprovedCommandPrefixSaved { ... }
```

当用户批准一个命令并选择"记住"，Codex 会将它保存为一个前缀规则。下次相同前缀的命令自动通过。这类似于 sudo 的 timestamp 缓存机制。

---

## 8.4 Shell Tool：连接操作系统世界

Shell Tool（`core/src/tools/handlers/shell` 目录）是 Codex 中使用频率最高、也最危险的 Tool。它相当于 `exec()` 系统调用——把 AI 的意图翻译成操作系统命令。

### 命令执行流程

```rust
// core/src/tools/runtimes/shell/ — Shell 执行运行时
// 构造 ShellCommand → 沙箱选择 → spawn 子进程 → 捕获 stdout/stderr
```

关键步骤：

1. **命令规范化**（`command_canonicalization.rs`）：标准化路径、处理相对路径
2. **Shell 检测**（`shell_detect.rs`）：确定用户 Shell（bash/zsh/fish）
3. **沙箱包装**：根据 `SandboxPolicy` 选择沙箱策略
   - Linux: `codex-linux-sandbox` 子进程包装
   - macOS: `sandbox-exec` Seatbelt 包装
   - Windows: Restricted Token
4. **执行**：通过 PTY（`codex-utils-pty`）或普通管道执行
5. **输出捕获**：截断长输出（`output-truncation`）、编码检测（`chardetng`/`encoding_rs`）

### Shell 快照

```rust
// core/src/shell_snapshot.rs
pub(crate) mod shell_snapshot {
    pub struct ShellSnapshot { ... }  // 捕获 Shell 状态
}
```

ShellSnapshot 在一轮 Shell 命令执行后捕获：
- 环境变量变化
- 当前工作目录变化
- Shell 状态（别名、函数）

这确保了 Agent 对 Shell 状态的认知与系统实际状态同步。子 Agent 从父 Agent 继承 ShellSnapshot，就像 `fork()` 后子进程继承文件描述符。

### 输出截断策略

```rust
// utils/output-truncation/ — 输出截断
// 如果命令输出超长，截断并添加省略标记
```

对于 `cat 10GB-file.log` 这种场景，Codex 不会把 10GB 内容塞给 LLM。它会截断到可管理的长度（通常是几千字节），并通知 LLM 输出已被截断。

---

## 8.5 MCP Tool 调用路径

```rust
// core/src/mcp.rs → codex-mcp/src/mcp_connection_manager.rs → rmcp-client → 外部 MCP Server
```

MCP Tool 的完整调用路径：

```
Session (Codex)
  │
  ├─→ McpManager::call_tool(server_name, tool_name, arguments)
  │
  ├─→ McpConnectionManager (codex-mcp)
  │     │
  │     ├─→ 查找/建立与 MCP Server 的连接
  │     └─→ 发送 tools/call JSON-RPC 请求
  │
  ├─→ rmcp-client (外部 MCP SDK 封装)
  │     │
  │     └─→ stdio/HTTP 传输 → MCP Server 进程
  │
  └─→ 等待响应 → 返回 CallToolResult
```

### 工具曝光策略

```rust
// core/src/mcp_tool_exposure.rs
pub(crate) mod mcp_tool_exposure { ... }
```

不是所有 MCP Server 暴露的工具都会被 Agent 使用。`mcp_tool_exposure` 控制：
- 哪些工具对主流 Agent 可见
- 哪些工具对子 Agent 可见
- 工具可见性是否受配置限制

### 审批模板

```rust
// core/src/mcp_tool_approval_templates.rs
```

某些 MCP 工具的操作需要用户批准。审批模板定义了"什么类型的 MCP 操作需要什么类型的批准"。

---

## 8.6 其他重要 Tool

### File Tools (read/write/edit)

文件操作 Tools 不直接执行 Shell 命令来读写文件，而是通过 `codex-file-system` crate 进行安全的文件操作。这避免了 shell injection 风险——AI 不能通过"文件名注入"来执行恶意命令。

### Apply Patch Tool

```rust
// core/src/apply_patch.rs
```

`apply_patch` 是 Codex 的代码修改工具。它不直接用 `sed` 或 `replace`，而是：
1. 生成 unified diff
2. 应用 diff（通过 `diffy`/`similar`）
3. 验证应用结果

这比"直接输出新文件内容"更精确、更安全——diff 只改变化的行，不会误删其他内容。

### Web Search Tool

```rust
// core/src/web_search.rs
pub fn web_search_detail(...) -> ... { ... }
pub fn web_search_action_detail(...) -> ... { ... }
```

Web Search 允许 Agent 搜索互联网获取最新信息。这是绕过 LLM 知识截止日期（cutoff date）的关键能力。

---

## 8.7 类比系统调用

| OS 系统调用 | Codex Tool |
|------------|-----------|
| `read()` / `write()` | File Read/Write/Edit Tools |
| `exec()` / `system()` | Shell Tool |
| `mmap()` | Context 注入（将 tool 结果映射到上下文窗口） |
| `ptrace()` | Shell Snapshot（监控子进程状态变化） |
| `chroot()` / seccomp | Sandbox 包装 |
| `capget()` / `capset()` | Approval Policy 检查 |
| `socket()` / `connect()` | MCP Tool（连接外部服务） |
| `ioctl()` | Web Search / Image Generation |

Tool 调用比系统调用的延迟要高好几个数量级（Shell 命令可能跑几分钟，MCP 调用可能是网络请求），所以 Tool 调用路径中大量的代码是在处理**超时、取消、结果截断**——这些在 OS 层面是"少数情况"，在 Codex 中是"常态"。

---

## 8.8 本章要点

1. **Tool 是 Agent 与外部世界的唯一接口**，等价于操作系统中的 System Call。
2. **四种 Tool 来源**：Builtin（内核内建）、MCP（外部服务）、Skill（领域工具）、Plugin（第三方扩展）。
3. **Tool 调用五阶段**：LLM 发起 → 解析 → 权限检查 → 执行 → 结果注入。
4. **权限检查有两层**：ApprovalPolicy（全局） + ExecPolicy（细粒度命令规则）。
5. **Shell Tool 是最复杂的内建 Tool**：命令规范化、Shell 检测、沙箱包装、PTY 执行、输出捕获和截断、Shell 快照继承。
6. **MCP Tool 路径**：Session → McpManager → McpConnectionManager → rmcp-client → MCP Server（跨进程调用链最长）。
