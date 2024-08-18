# 第 5 章 工具系统：Agent 的感知与行动接口

> 工具是 Agent 感知世界和改变世界的唯一通道。工具系统定义了"Agent 能做什么"，而它的接口设计直接决定了 Agent 的能力边界和行为模式。这一章拆解 Tool 接口的全貌及其背后的设计哲学。

---

## 5.1 Tool<Input, Output, Progress> 接口全解

Claude Code 的工具不是简单的 `{name, function}` 对。`Tool` 是一个包含 35+ 方法/属性的复杂接口：

```typescript
// src/Tool.ts (核心字段)
interface Tool<Input extends ZodType, Output, Progress = unknown> {
  name: string                       // 工具名（含 MCP 前缀的完全限定名）
  inputSchema: Input                 // Zod schema，用于运行时验证
  inputJSONSchema?: object           // 原始 JSON Schema（MCP 工具直接提供）
  description(input, options): Promise<string>  // 动态描述函数
  call(input, context): Promise<Output>         // 核心执行函数
  prompt(options): Promise<string>  // API tool description 文本

  // 分类元数据
  isConcurrencySafe(input): boolean  // 是否可以与其他工具并发执行
  isReadOnly(input): boolean         // 是否不改变系统状态
  isDestructive(input): boolean      // 是否不可逆
  needsApproval(input): boolean      // 权限系统用

  // 高级特性
  shouldDefer?: boolean              // 是否延迟加载（tool search）
  alwaysLoad?: boolean               // 强制始终在 API schema 中
  strict?: boolean                   // 是否使用 structured outputs

  // 工具结果
  maxResultSizeChars?: number        // 最大输出字符数

  // MCP 元数据
  isMcp?: boolean                    // 是否为 MCP 工具
  serverName?: string                // MCP 服务器名
}
```

### 为什么 Tool 是接口而不是类？

如果用 abstract class，所有工具共享同一个继承树——这限制了组合灵活性。接口让每个工具独立决定实现哪些可选方法。`isConcurrencySafe()` 大部分工具返回 `false`——因为它们的实现从未覆盖这个方法。接口的默认值由工厂函数提供：

```typescript
// 默认实现
isConcurrencySafe: (_input?) => false,
isReadOnly: (_input?) => false,
```

### description() vs prompt()

这是两个容易混淆的方法：

- **`description(input, options)`**：返回给**模型**的文本，在 tool_use block 生成前。用于帮助模型理解如何调用这个工具。支持条件逻辑——同一工具在不同 input 下返回不同描述。
- **`prompt(options)`**：返回 API 的 tool `description` 字段，在 tool schema 构建时调用。更偏向"工具文档"。

分离两者的原因：`description()` 可能随 input 变化（例如 AgentTool 的 `subagent_type`），但 `prompt()` 的缓存需要稳定性。

---

## 5.2 工具注册与发现：三级管线

```
getAllBaseTools()      → 所有可能注册的工具（~35 个）
    ↓
getTools(permissionCtx)→ 根据权限上下文过滤（~25 个）
    ↓
assembleToolPool()     → 拼装最终工具池（+ MCP + 自定义 Agent + Skill）
```

### getAllBaseTools()

这是所有内置工具的注册表。每个工具通过 `tool()` 工厂函数注册：

```typescript
// src/tools.ts (概念上的注册表)
const ALL_BASE_TOOLS = [
  BashTool,
  FileReadTool,
  FileWriteTool,
  FileEditTool,
  GlobTool,
  GrepTool,
  TaskCreateTool,
  AgentTool,
  SkillTool,
  AskUserQuestionTool,
  // ... ~25 个其他工具
]
```

### getTools() — 条件过滤

`getTools()` 根据用户的权限上下文和 feature flags 过滤工具：

```
原始工具列表（35+）
  → 过滤：用户禁用了某些工具（settings.json）
  → 过滤：feature flag 未开启的工具
  → 过滤：平台不支持的工具（Windows 特殊路径）
  → 最终工具列表（~25 个）
```

### assembleToolPool() — 动态拼装

最后一步拼装 MCP 工具、自定义 Agent、Skill 定义的 tool 命令：

```
assembleToolPool()
  ├── getTools() → 内置工具列表
  ├── MCP clients → isMcp: true 的工具
  ├── loadAgentsDir() → AgentDefinition → AgentTool variants
  └── skillToolCommands → Command → SkillTool variants
```

---

## 5.3 工具 Schema 的双重表达

每个工具都有两个 schema 表达：

```typescript
inputSchema: z.ZodObject<...>     // Zod — 运行时验证
inputJSONSchema?: object          // JSON — API 协议层
```

### 为什么 Zod 和 JSON Schema 并存？

- **Zod** 用于运行时输入验证——`inputSchema.safeParse(input)` 在本地方便地验证模型生成的输入（模型经常生成无效输入）
- **JSON Schema** 用于 API 的 tool definition——Anthropic API 要求 JSON Schema 格式的工具定义

对于 MCP 工具，`inputJSONSchema` 是 MCP 协议自带的——直接从 MCP 服务器获取，不需要 Zod 转换。对于内置工具，先用 Zod 定义，再通过 `zodToJsonSchema()` 转换。

---

## 5.4 动态描述：description(input, options)

`description()` 是工具系统中最重要的"智能"——同一工具在不同上下文下的描述策略：

```typescript
// 示例：AgentTool 的描述随 subagent_type 变化
async description(input, options) {
  if (input.subagent_type === 'Explore') {
    return 'Fast read-only explorer for codebase search...'
  }
  if (input.subagent_type === 'Plan') {
    return 'Software architect agent for design...'
  }
  return 'General-purpose agent for multi-step tasks...'
}
```

### 三个维度的动态性

| 维度 | 来源 | 例子 |
|------|------|------|
| Input 驱动 | `input` 参数 | AgentTool 的 subagent_type |
| 环境驱动 | `options.tools` | BashTool 看到有 Glob/Grep 时建议用专用工具 |
| 特性驱动 | `options.agents` | AgentTool 列出可用的自定义 Agent |

---

## 5.5 并发安全标记

`isConcurrencySafe()` 是工具编排系统（第 6 章）的核心输入：

```typescript
isConcurrencySafe(input: z.infer<Input>): boolean
```

一个工具可以"部分安全"——基于 input 判断：

```typescript
// Bash
isConcurrencySafe(input) {
  return input.run_in_background === true  // 后台运行的 bash 是安全的
}

// FileRead
isConcurrencySafe() {
  return true  // 读文件总是安全的
}
```

并发安全工具在同一批次中并行执行；非安全工具串行执行。这是工具编排层（`runTools()`）实现分区调度算法的关键输入。

---

## 5.6 延迟加载协议：shouldDefer + ToolSearch

当工具数量过多时（30+ MCP 工具），每轮 API 调用都发送全部 tool schema 会消耗大量 token。`shouldDefer` + `ToolSearch` 解决了这个问题：

```
第一次 API 调用：
  schema: [Bash, Read, Write, Edit, ToolSearch, ...]  ← 仅核心工具 + ToolSearch
  (30 个 MCP 工具被标记 defer_loading: true，不发送完整 schema)

模型想用某个 MCP 工具：
  → 调用 ToolSearch，搜索工具描述
  → ToolSearch 返回匹配的 tool_reference

第二次 API 调用：
  schema: [Bash, Read, ..., ToolSearch, mcp__slack__send_message, ...]
  ← 发现了一个 MCP 工具，加入 schema
```

`alwaysLoad` 标记的工具不受 `shouldDefer` 影响——始终在 schema 中。这用于核心工具如 Task、Skill 等。

---

## 5.7 工具结果映射：mapToolResultToToolResultBlockParam

工具执行完成后，结果需要被转回 API 的 `tool_result` 格式：

```typescript
mapToolResultToToolResultBlockParam(result, toolUseId)
  → {
      type: 'tool_result',
      tool_use_id: 'toolu_xxx',
      content: [
        { type: 'text', text: result.output },
      ],
      is_error: result.isError,
    }
```

如果结果是图片（如截图工具），它会生成 `{ type: 'image', source: { data: '...' } }` 块。

---

## 本章小结

工具系统是 Agent 的"感知-行动"接口。35+ 方法/属性的 `Tool` 接口不是过度设计——它承载了：

1. **并发调度**（`isConcurrencySafe`）
2. **动态发现**（`shouldDefer` + ToolSearch）
3. **自适应描述**（`description(input, options)`）
4. **双层验证**（Zod + JSON Schema）
5. **权限决策**（`isReadOnly`、`isDestructive`、`needsApproval`）

这些功能分散在接口层面而非运行时层面，是因为：**接口是契约**。每个工具的开发者需要回答"这个工具能并发吗/需要延迟吗/什么输入安全吗"——接口通过方法签名强制这些决策，而非依赖运行时配置。

下一章，我们将看到这些工具如何在实际执行管线中被编排和调用。
