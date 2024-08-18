# 附录A：关键 Crate 索引

> 基于 `codex-rs/Cargo.toml` workspace members

## 核心层

| Crate | 路径 | 职责 |
|-------|------|------|
| `codex-core` | `core/` | 核心引擎：Session、Agent、Tool dispatch、Context 装配 |
| `codex-protocol` | `protocol/` | 协议定义：Op、Event、SandboxPolicy、PermissionProfile、所有 wire types |
| `codex-config` | `config/` | 配置系统：ConfigLayerStack、ConfigBuilder、约束检查 |
| `codex-thread-manager` | （在 core 内） | Thread 生命周期管理：派生、Resume、关闭 |

## 平台沙箱

| Crate | 路径 | 平台 | 职责 |
|-------|------|------|------|
| `sandboxing` | `sandboxing/` | All | SandboxManager、SandboxType 选择、沙箱 transform |
| `codex-linux-sandbox` | `linux-sandbox/` | Linux | bubblewrap + seccomp BPF + Landlock |
| `windows-sandbox-rs` | `windows-sandbox-rs/` | Windows | Restricted Token + WFP + ConPTY |
| `shell-escalation` | `shell-escalation/` | Unix | EXEC_WRAPPER 截获 + Escalation Server |

## 网络与 API

| Crate | 路径 | 职责 |
|-------|------|------|
| `codex-api` | `codex-api/` | OpenAI Responses API 客户端实现 |
| `codex-client` | `codex-client/` | HTTP/WS 连接管理、认证头注入 |
| `model-provider` | `model-provider/` | ModelProvider trait + 多厂商路由 |
| `model-provider-info` | `model-provider-info/` | Provider 元数据 |
| `rmcp-client` | `rmcp-client/` | MCP 协议的 Rust 客户端实现 |
| `codex-mcp` | `codex-mcp/` | MCP 连接管理、工具聚合、审批模板 |
| `network-proxy` | `network-proxy/` | HTTP/SOCKS5 代理、网络策略 |

## 持久化

| Crate | 路径 | 职责 |
|-------|------|------|
| `thread-store` | `thread-store/` | ThreadStore trait + Local/Remote/InMemory 实现 |
| `rollout` | `rollout/` | Rollout 文件读写、StateDB 操作 |

## 前端

| Crate | 路径 | 职责 |
|-------|------|------|
| `tui` | `tui/` | 终端 GUI：App、ChatWidget、Markdown 渲染、流式输出 |
| `app-server` | `app-server/` | App Server：MessageProcessor、ThreadState、RPC routing |
| `app-server-transport` | `app-server-transport/` | Transport 抽象层：stdio/UDS/WebSocket |
| `app-server-protocol` | `app-server-protocol/` | Server 端协议定义（ConfigLayer 等） |

## CLI

| Crate | 路径 | 职责 |
|-------|------|------|
| `cli` | `cli/` | CLI 入口：arg0 分发、18+ 子命令、参数解析 |
| `exec` | `exec/` | 非交互模式：直接 link core，无 TUI 开销 |

## 文件与 Shell

| Crate | 路径 | 职责 |
|-------|------|------|
| `file-system` | `file-system/` | 安全的文件操作（避免 shell injection） |
| `shell-command` | `shell-command/` | Shell 命令解析、安全/危险命令分类 |
| `apply-patch` | `apply-patch/` | Unified diff 生成 + 应用 |

## 工具与辅助

| Crate | 路径 | 职责 |
|-------|------|------|
| `codex-utils-absolute-path` | `utils/absolute-path/` | AbsolutePathBuf 类型 |
| `codex-utils-pty` | `utils/pty/` | PTY 分配和管理 |
| `codex-utils-stream-parser` | `utils/stream-parser/` | SSE 事件流解析 |
| `git-utils` | `git-utils/` | Git 操作封装 |
| `codex-login` | `login/` | 认证管理：OAuth、API Key、Agent Identity |
| `codex-execpolicy` | `execpolicy/` | ExecPolicy 规则引擎核心库 |

## 其他

| Crate | 路径 | 职责 |
|-------|------|------|
| `analytics` | `analytics/` | 遥测事件：定义、缓冲、批量上传 |
| `arg0` | `arg0/` | argv[0] 分发逻辑 |
| `hooks` | `hooks/` | Hook 系统：事件驱动的用户自定义脚本 |
| `codex-plugins` | `codex-plugins/` | Plugin 加载和管理 |
| `rollout-trace` | `rollout-trace/` | Rollout 追踪和分析工具 |
