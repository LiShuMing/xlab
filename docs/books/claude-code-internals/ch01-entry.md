# 第 1 章 入口：从终端到请求

> 当用户在终端键入 `claude` 并按下回车，到第一次 LLM API 请求发出，中间经历了什么？这个看似简单的问题，涉及一个 50 万行系统的启动、初始化与请求构建的完整链路。

---

## 1.1 CLI 启动流程

Claude Code 的二进制入口是 `src/entrypoints/cli.tsx`。这个文件刻意保持精简——它的核心职责只有一个：**快速分流**。

```typescript
// src/entrypoints/cli.tsx
async function main(): Promise<void> {
  const args = process.argv.slice(2)

  // Fast-path for --version/-v: zero module loading needed
  if (args.length === 1 && (args[0] === '--version' || args[0] === '-v')) {
    console.log(`${MACRO.VERSION} (Claude Code)`)
    return
  }

  // 所有其他路径，动态加载
  const { profileCheckpoint } = await import('../utils/startupProfiler.js')
  profileCheckpoint('cli_entry')

  // --dump-system-prompt、--claude-in-chrome-mcp、--daemon-worker
  // 等快速路径依次判断...

  // 最终：加载完整的 CLI
  const { run } = await import('../main.tsx')
  await run()
}
```

这个设计遵循一个重要原则：**最小化模块加载**。Bun 的 `import()` 是动态的——只有真正需要时才会加载对应模块。`--version` 路径零模块加载，耗时 < 50ms；而完整的 CLI 加载可能需要数百毫秒。

### 三条主要路径

从 `cli.tsx` 出发，系统分化为三条主要路径：

```
cli.tsx
  ├── REPL 模式（交互式终端）  → main.tsx → launchRepl()
  ├── Print 模式（-p 一次性）  → main.tsx → print()
  └── SDK 模式（程序化调用）   → entrypoints/agentSdkTypes.ts
```

**REPL 模式**是大多数用户接触的形态——一个带颜色、自动补全、Vim 键绑定的交互式终端。它由 React + Ink 驱动，`src/screens/REPL.tsx` 是主屏幕组件（5006 行，项目中最大的单文件组件之一）。

**Print 模式**（`claude -p "fix the bug"`）是无头模式——没有 UI，直接输出文本结果。它使用 `QueryEngine` 而非 REPL 组件。

**SDK 模式**是 Claude Code 作为库被其他程序调用时的路径。`QueryEngine` 是其核心——一个封装了完整会话状态的类，通过 `AsyncGenerator<SDKMessage>` 流式产出结果。

### 为什么 Print 模式和 SDK 模式用 QueryEngine 而非 REPL？

REPL 是一个 React 应用——它需要终端渲染、键盘事件、权限弹窗。这些在无头/SDK 场景下不可用。`QueryEngine` 是 REPL 中 `ask()` 函数的核心逻辑提取——它只做"提交用户消息→流式产出结果"，不涉及任何 UI。

这是一个典型的**关注点分离**：Agent 的核心逻辑（推理、工具执行、上下文管理）与 UI 渲染完全解耦。核心逻辑通过 `AsyncGenerator` 产出消息流，UI 层（或 SDK 层）决定如何消费这个流。

---

## 1.2 会话初始化

当用户启动一个新会话，系统需要完成大量初始化工作。`src/entrypoints/init.ts` 中的 `init()` 函数是初始化的枢纽：

```
init()
  ├── 设置全局错误处理
  ├── 初始化遥测系统（analytics）
  ├── 加载配置（settings、CLAUDE.md）
  ├── 验证 API 密钥
  ├── 初始化 MCP 服务器
  └── 启动性能追踪
```

### 全局状态单例：bootstrap/state.ts

`src/bootstrap/state.ts` 是一个进程级全局单例，存储了会话级别的关键状态：

```typescript
// 关键状态（简化）
let sessionId: string           // 会话唯一标识
let projectRoot: string         // 项目根目录
let originalCwd: string         // 启动时的工作目录
let totalCost: number           // 累计 API 费用
let totalApiDuration: number    // 累计 API 耗时
let fastModeState: ...          // 快速模式状态
let thinkingClearLatched: ...   // thinking 清除标记（缓存稳定性）
let promptCache1hEligible: ...  // 1h 缓存 TTL 资格
```

**为什么用全局单例而非 React Context？** 因为这些状态需要在**任何地方**访问——包括 React 组件之外的工具执行、API 调用、钩子脚本。React Context 只在组件树内可用，全局单例则没有这个限制。

**与数据库系统的类比**：这类似于数据库的 `pg_stat_*` 系统视图——进程级统计信息，任何后端进程都可以访问，不需要传递上下文。

### 配置加载

配置系统是分层的：

```
全局配置 (~/.claude/settings.json)
  ← 项目配置 (.claude/settings.json)
    ← 本地配置 (.claude/settings.local.json)
      ← 环境变量 (CLAUDE_CODE_*)
        ← 运行时覆盖 (--model, --permission-mode)
```

每一层覆盖上一层。`getGlobalConfig()` 返回合并后的最终配置。`enableConfigs()` 在启动时调用，确保配置文件被读取和缓存。

配置加载有一个微妙的问题：**配置可能在运行时改变**。用户可以编辑 `settings.json`，Claude Code 通过文件监听检测变化并热加载。但热加载不能影响正在进行的 API 请求——否则会导致缓存键不一致。因此，每个 query 循环在开始时快照一次配置，循环内使用快照值。

---

## 1.3 用户输入处理管线

当用户在 REPL 中按下回车，输入经过一个多阶段处理管线：

```
用户输入字符串
    ↓
processUserInput()
    ↓
┌───────────────────────────────────┐
│ 1. 识别输入类型                    │
│    - 以 / 开头 → 斜杠命令          │
│    - 以 ! 开头 → Bash 命令         │
│    - 其他 → 文本提示               │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 2. 执行 UserPromptSubmit 钩子      │
│    - 可以阻塞输入（拦截）           │
│    - 可以修改输入                   │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 3. 构建消息                        │
│    - 文本内容                      │
│    - 图片附件                      │
│    - IDE 选区注入                  │
│    - Memory 附件                   │
│    - Skill 附件                    │
└───────────────────────────────────┘
    ↓
┌───────────────────────────────────┐
│ 4. 返回 ProcessUserInputBaseResult │
│    - messages: 消息数组            │
│    - shouldQuery: 是否需要调用 API  │
│    - allowedTools: 允许的工具      │
│    - model: 模型（可能被命令改变）  │
└───────────────────────────────────┘
```

### 输入类型的三路分发

`processUserInput()` 的核心逻辑是一个三路分发：

```typescript
// src/utils/processUserInput/processUserInput.ts (简化)
export async function processUserInput({input, mode, ...}): Promise<Result> {
  const result = await processUserInputBase(input, mode, ...)

  if (!result.shouldQuery) {
    return result  // 斜杠命令已处理，不需要 API 调用
  }

  // 执行 UserPromptSubmit 钩子
  const hookResult = await executeUserPromptSubmitHooks(...)

  return result
}
```

**斜杠命令**（如 `/compact`、`/clear`、`/model`）是本地执行的——它们直接操作会话状态，不调用 LLM。`processSlashCommand()` 处理这些命令，设置 `shouldQuery: false`。

**Bash 命令**（以 `!` 开头）直接在终端执行，结果以 `<local-command-stdout>` 标签注入消息流。同样不调用 LLM。

**文本提示**是唯一触发 API 调用的输入类型。`processTextPrompt()` 将文本封装为 `UserMessage`，设置 `shouldQuery: true`。

### 附件注入

一个容易被忽略但至关重要的步骤是**附件注入**。在文本提示被发送给 LLM 之前，系统会自动附加多个上下文附件：

```typescript
// src/utils/attachments.ts (简化)
const attachmentMessages = await getAttachmentMessages(context, messages)
// 可能包含：
// - CLAUDE.md 内容（项目规则、约定）
// - 之前读取过的文件内容（readFileState 缓存）
// - Skill 发现结果（相关技能列表）
// - Deferred tools delta（延迟加载工具的增量通知）
// - MCP 指令 delta（MCP 服务器说明的增量更新）
```

这些附件不是消息的一部分——它们是 `AttachmentMessage`，在 API 调用前被合并到 `messages` 数组中，但在 API 层面表现为普通的 `user` 消息。附件的内容会在压缩后自动重新注入，确保 Agent 不会丢失关键上下文。

---

## 1.4 消息的诞生

所有用户输入最终都通过 `createUserMessage()` 转换为内部消息类型：

```typescript
// src/utils/messages.ts
export function createUserMessage({
  content,           // string | ContentBlockParam[]
  toolUseResult?,    // 工具执行结果文本
  imagePasteIds?,    // 图片粘贴 ID
  uuid?,             // 消息唯一标识
  isMeta?,           // 是否为系统生成的隐藏消息
  isCompactSummary?, // 是否为压缩摘要
  sourceToolAssistantUUID?,  // 关联的 tool_use 消息 ID
  mcpMeta?,          // MCP 协议元数据
}): UserMessage
```

### 消息类型系统

Claude Code 内部定义了丰富的消息类型联合：

```typescript
type Message =
  | AssistantMessage       // LLM 响应（含 text/thinking/tool_use 块）
  | UserMessage            // 用户输入或 tool_result
  | SystemMessage          // 系统消息（compact_boundary、api_error 等）
  | ProgressMessage        // 工具执行进度
  | AttachmentMessage      // 上下文附件（文件内容、skill 列表等）
  | StreamEvent            // 流式事件（message_start/delta/stop）
  | RequestStartEvent      // 请求开始信号
  | TombstoneMessage       // 墓碑消息（标记已删除的消息）
  | ToolUseSummaryMessage  // 工具调用摘要
```

这些类型不是随意设计的——每一种都有明确的消费者和生命周期：

| 消息类型 | 生产者 | 消费者 | 是否发送给 API |
|----------|--------|--------|---------------|
| AssistantMessage | queryModel() | QueryEngine/REPL | 是（双向） |
| UserMessage | processUserInput/runTools | QueryEngine/REPL | 是（双向） |
| SystemMessage | compact/retry | QueryEngine/REPL | 否 |
| ProgressMessage | toolExecution | REPL（UI 进度条） | 否 |
| AttachmentMessage | attachments.ts | QueryEngine | 部分（作为 user 消息） |
| StreamEvent | queryModel() | QueryEngine（usage 追踪） | 否 |
| TombstoneMessage | query.ts（回退/降级） | REPL（UI 清理） | 否 |

**TombstoneMessage** 特别值得注意。当 LLM 流式输出了部分 assistant 消息但随后发生降级（FallbackTriggeredError）时，这些部分消息需要从 UI 中移除——TombstoneMessage 就是"删除标记"。它告诉 UI："删除引用的这个消息"。

这个设计类似于数据库中的 **MVCC（多版本并发控制）**——不直接删除数据，而是标记删除，让消费者自行决定何时清理。

### 从内部消息到 API 消息

内部消息类型丰富，但 Anthropic API 只认两种角色：`user` 和 `assistant`。`normalizeMessagesForAPI()` 负责这个映射：

```
内部类型                    → API 类型
─────────────────────────────────────
AssistantMessage           → { role: "assistant", content: [...] }
UserMessage (纯文本)       → { role: "user", content: "..." }
UserMessage (tool_result)  → { role: "user", content: [{type:"tool_result",...}] }
AttachmentMessage          → 合并为 user 消息的一部分
ProgressMessage            → 丢弃
SystemMessage              → 丢弃
StreamEvent                → 丢弃
TombstoneMessage           → 丢弃
```

这个映射不是简单的类型转换。它需要处理多种边界情况：

- **tool_use / tool_result 配对**：API 要求每个 `tool_use` 都有对应的 `tool_result`，否则返回 400 错误。`ensureToolResultPairing()` 在发送前修复配对。
- **thinking 块保留**：如果一个 assistant 消息包含 thinking 块，它所在的整个"轮次"都必须保留 thinking 块。
- **图片块位置**：API 对 `is_error: true` 的 `tool_result` 只接受文本内容，图片块需要提升到顶层。

---

## 1.5 从 QueryEngine 到第一次 API 调用

让我们把整个链路串起来，从 `QueryEngine.submitMessage()` 出发：

```typescript
// src/QueryEngine.ts (简化)
async *submitMessage(prompt: string): AsyncGenerator<SDKMessage> {
  // 1. 构建系统提示词
  const { defaultSystemPrompt, userContext, systemContext } =
    await fetchSystemPromptParts({ tools, mainLoopModel, mcpClients, ... })

  // 2. 处理用户输入
  const { messages: messagesFromUserInput, shouldQuery } =
    await processUserInput({ input: prompt, ... })

  // 3. 将用户消息追加到会话历史
  this.mutableMessages.push(...messagesFromUserInput)

  // 4. 进入 Agent Loop
  for await (const message of query({
    messages: this.mutableMessages,
    systemPrompt,
    canUseTool: wrappedCanUseTool,
    toolUseContext,
    ...
  })) {
    // 5. 将内部消息转换为 SDK 消息并产出
    yield normalizeMessage(message)
  }
}
```

步骤 1-3 是**准备阶段**：组装提示词、处理输入、构建消息历史。

步骤 4 是**核心阶段**：进入 `query()` 的 `while(true)` 循环——这就是我们将在第 4 章深入分析的 Agent Loop。

步骤 5 是**输出阶段**：将内部消息流转换为 SDK 消息流，供上层消费。

### 时间线

一个典型的首次 API 调用，各步骤的耗时分布：

```
[0ms]     CLI 入口
[10ms]    模块加载完成
[50ms]    初始化完成（配置、认证、MCP）
[100ms]   REPL 渲染完成，等待用户输入
          ... 用户输入并回车 ...
[1ms]     processUserInput() 完成
[5ms]     fetchSystemPromptParts() 完成
[2ms]     normalizeMessagesForAPI() 完成
[1ms]     getAnthropicClient() 创建客户端
          ... 网络请求 ...
[300ms]   第一个流式 chunk 到达（TTFB）
[5000ms]  完整响应流完成
```

注意：提示词构建（~8ms）远快于网络延迟（~300ms TTFB）。这是为什么 Claude Code 在提示词构建上做了大量缓存优化——8ms 的构建时间允许被优化到 2ms，但 300ms 的网络延迟无法被客户端优化。

---

## 本章小结

从终端到第一次 API 请求，数据经历了如下变换：

```
终端输入 → processUserInput → UserMessage[]
                                 ↓
                          fetchSystemPromptParts → SystemPrompt[]
                                 ↓
                          normalizeMessagesForAPI → BetaMessageParam[]
                                 ↓
                          getAnthropicClient → Anthropic SDK Client
                                 ↓
                          anthropic.beta.messages.create({stream: true})
                                 ↓
                          Stream<BetaRawMessageStreamEvent>
```

这个管线的每个环节都有明确的设计动机：

- **动态加载**是为了启动速度
- **全局单例**是为了跨组件状态共享
- **三路分发**是为了区分本地命令和 LLM 请求
- **附件注入**是为了自动提供上下文
- **消息标准化**是为了弥合内部类型和 API 类型的鸿沟

下一章，我们将深入管线中最重要的一环——System Prompt 的动态组装，理解 Claude Code 如何通过提示词工程定义 Agent 的行为边界。
