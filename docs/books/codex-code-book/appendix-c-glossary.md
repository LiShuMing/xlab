# 附录C：术语对照表

## Codex 核心术语

| 术语 | 英文 | 含义 | 类比 |
|------|------|------|------|
| 会话 | Session | Agent 的执行容器，管理一个完整对话生命周期 | 进程 |
| 线程 | Thread | 会话的持久化标识和隔离单元 | PID 命名空间 |
| 主线 | Turn | Agent 的一轮"思考→行动→观察"循环 | 系统调用序列 |
| 代理 | Agent | 有身份（ID+Path+Nickname）的异步执行单元 | 线程 |
| 主代理 | Root Agent | 用户直接交互的第一个 Agent | init 进程（PID 1） |
| 子代理 | Sub-Agent | 从父 Agent 派生的 Agent（新建或 Fork） | fork() 出的子进程 |
| 代理树 | Agent Tree | 层级化的 Agent 父子关系（Path: root/sub1/sub2） | 进程树 |
| 代理控制 | AgentControl | 多 Agent 协调的控制平面 | 进程调度器 |
| 注册表 | AgentRegistry | Agent 名称/路径/槽位的注册中心 | PID 分配器 |
| 上下文 | Context | LLM 的输入窗口，由 20+ Fragment 拼装 | 虚拟内存 |
| 碎片 | Fragment | Context 的独立片段（如 PermissionsInstructions） | 内存页 |
| 压缩 | Compact | 将早期对话压缩为摘要以释放 Token 预算 | GC（垃圾回收） |
| 历史 | Rollout | jsonl 格式的对话事件持久化日志 | WAL（预写日志） |
| 记忆 | Memory | 跨会话持久化知识（会话/项目/用户三级） | 文件系统 |
| 技能 | Skill | Markdown 定义的可触发扩展能力（懒加载） | 动态库 (.so/.dylib) |
| 工具 | Tool | Agent 与外部世界交互的接口 | 系统调用 |
| 外壳工具 | Shell Tool | 执行操作系统命令的工具 | exec() |
| 权限配置 | PermissionProfile | 定义文件系统和网络访问权限 | 文件系统权限 + 防火墙 |
| 沙箱 | Sandbox | OS 层面的安全隔离机制 | chroot / seccomp / namespace |
| 沙箱策略 | SandboxPolicy | 旧版权限枚举（正被 PermissionProfile 取代） | - |
| 执行策略 | ExecPolicy | 命令级规则引擎（.rules 文件，Allow/Prompt/Forbidden） | SELinux/AppArmor 策略 |
| 提权 | Escalation | 受控的沙箱突破（Shell Escalation） | sudo / capabilities |
| 可写根 | WritableRoot | 沙箱内的可写目录，带 protected_metadata_names | 带 ACL 的目录 |
| 批准政策 | ApprovalPolicy | 决定是否需要用户批准 Tool 调用 | 权限检查门禁 |
| 预连接 | Prewarm | WebSocket 的预热连接（generate=false） | TCP preconnect |
| 提交队列 | Submission Queue | Op 的发送通道 | 消息队列 |
| 事件队列 | Event Queue | Event 的接收通道 | 消息队列 |
| 消息处理器 | MessageProcessor | App Server 的 RPC 路由层 | API Gateway |
| 传输 | Transport | 进程间通信方式（stdio/UDS/WebSocket） | 网络传输层 |
| 线程管理器 | ThreadManager | Thread 的创建、查找、关闭的总入口 | 进程管理器 |
| 线程存储 | ThreadStore | Thread 持久化的抽象接口 | 存储引擎 |
| 模型客户端 | ModelClient | LLM API 调用的封装（HTTP + WS） | 网络 I/O 子系统 |
| 连接管理器 | McpConnectionManager | MCP Server 连接的管理和聚合 | 服务注册中心 |

## 计算机系统类比索引

| Codex 概念 | OS 类比 | 数据库类比 |
|-----------|---------|-----------|
| Context 装配 | 虚拟内存管理 | 查询优化（Cost-based Optimization） |
| Context Fragment | 内存页 | 表分区 |
| Agent 派生 | fork() | 并行查询（Scatter-Gather） |
| Agent 间通信 | 进程间通信 (pipe/signal) | Exchange (Shuffle) |
| Tool 调用 | 系统调用 | 存储过程调用 |
| Shell Tool | exec() | EXECUTE 语句 |
| 沙箱 | chroot/seccomp/namespace | 行级安全 (Row-Level Security) |
| ExecPolicy | SELinux/AppArmor | 访问控制列表 (ACL) |
| Rollout 持久化 | WAL (Write-Ahead Log) | Redo Log |
| Compact 压缩 | GC (Garbage Collection) | 表压缩 / 归档 |
| Model Client | 网络 I/O 子系统 | 外部数据源连接器 |
| MCP 集成 | 微服务 API Gateway | Federated Query |
| Memory 系统 | 文件系统 | 物化视图 (Materialized View) |
| WS Prewarm | TCP preconnect | 连接池预热 |
| Backpressure | 拥塞控制 | 背压 (Backpressure) |
| Resume 级联 | 进程树恢复 (criu) | 查询恢复 (Query Resume) |
