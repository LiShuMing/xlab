# 第 13 章 子 Agent 的执行模型

> 子 Agent 不是简单的函数调用——它有自己完整的生命周期：启动、上下文构建、工具执行、终止。理解这个生命周期是理解多 Agent 架构的基础。

---

## 13.1 runAgent()：完整的子 Agent 生命周期

```typescript
async function runAgent({
  agentDef,           // AgentDefinition
  parentContext,      // 父 Agent 的 ToolUseContext
  prompt,             // 子 Agent 的任务描述
  isolation,          // 隔离配置
}): Promise<AgentResult> {
  // 1. 构建子 Agent 的上下文
  const subagentContext = createSubagentContext({
    agentDef, parentContext, isolation
  })

  // 2. 解析工具池
  const tools = resolveAgentTools(agentDef, parentContext)

  // 3. 初始化 MCP 服务器
  const mcpClients = await initializeAgentMcpServers(agentDef)

  // 4. 构建 system prompt
  const systemPrompt = buildSubagentSystemPrompt({
    agentDef, tools, mcpClients, prompt
  })

  // 5. 进入 Agent Loop（复用主 Agent 的 query() 函数）
  for await (const message of query({
    messages: [createUserMessage(prompt)],
    systemPrompt,
    canUseTool,
    toolUseContext: subagentContext,
    maxTurns: agentDef.maxTurns ?? 50,
    // ...
  })) {
    // 记录、监控、控制
  }

  // 6. 返回结果给父 Agent
  return { output, messages, usage }
}
```

关键洞察：子 Agent **复用了主 Agent 的 `query()` 函数**。它不是在调用不同的代码路径——它只是通过不同的上下文和配置调用了相同的 Agent Loop。

---

## 13.2 上下文构建：createSubagentContext()

子 Agent 的上下文是父 Agent 上下文的"剪裁版"：

```typescript
function createSubagentContext(parentContext, agentDef) {
  return {
    ...parentContext,
    // 子 Agent 有不同的 agentId
    agentId: generateSubagentId(),
    // 子 Agent 可能有更窄的工具集
    options: {
      ...parentContext.options,
      tools: resolveAgentTools(agentDef, parentContext),
    },
    // 子 Agent 有独立的 abort controller
    abortController: createAbortController(),
  }
}
```

### 状态隔离

子 Agent 不能直接修改父 Agent 的状态：
- 独立的 `messages`：子 Agent 的消息不污染父 Agent 的消息历史
- 独立的 `readFileState`：子 Agent 的文件读取缓存独立
- 独立的 `agentId`：用于 transcript 关联

### 权限冒泡

但权限是特殊的——子 Agent 的权限弹窗需要"冒泡"到父 Agent 的终端。否则子 Agent 会被权限弹窗阻塞而用户看不到。`permissionMode: 'bubble'` 处理这个路由。

---

## 13.3 工具池解析：resolveAgentTools()

子 Agent 可用的工具由 `AgentDefinition.tools` 决定：

```typescript
function resolveAgentTools(agentDef, parentContext) {
  if (!agentDef.tools) {
    return parentContext.options.tools  // 默认：全部
  }
  // 只返回 agentDef.tools 中指定的工具
  return parentContext.options.tools.filter(t =>
    agentDef.tools.includes(t.name)
  )
}
```

这给了用户精确控制——Explore Agent 只有 Read/Glob/Grep，不会意外写入文件。

---

## 13.4 MCP 服务器初始化

子 Agent 可以有自己独立的 MCP 配置：

```typescript
async function initializeAgentMcpServers(agentDef) {
  if (!agentDef.mcpServers || agentDef.mcpServers.length === 0) {
    return []  // 默认：无 MCP 服务器
  }
  return await initializeMcpClients(agentDef.mcpServers)
}
```

这允许子 Agent 访问主 Agent 不需要的 MCP 服务——例如部署 Agent 可能有 CI/CD 工具的 MCP 访问权限而主 Agent 没有。

---

## 13.5 同步 vs 异步执行

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| 同步（默认） | 父 Agent 等待子 Agent 完成 | 需要立即使用子 Agent 的结果 |
| 异步（`run_in_background`） | 父 Agent 不等待，继续工作 | 独立探索、后台检查 |

异步模式的子 Agent 结果通过 `TaskOutput` 工具获取。

---

## 13.6 Transcript 侧链

每个子 Agent 有自己的 transcript（对话记录）：

```typescript
// recordSidechainTranscript()
// 子 Agent 的 transcript 与父 Agent 的 transcript 关联但独立
{
  parentTranscriptId: 'session_xxx',
  subagentTranscripts: [
    { agentId: 'sub_1', transcriptId: 'sidechain_1', summary: '...' },
    { agentId: 'sub_2', transcriptId: 'sidechain_2', summary: '...' },
  ]
}
```

侧链 transcript 支持 `/resume`——用户可以直接恢复子 Agent 的会话继续工作。

---

## 本章小结

子 Agent 的执行模型体现了"**复用而非重复**"的设计原则：

- 复用 `query()` Agent Loop（不写第二个 while(true)）
- 复用 `ToolUseContext` 结构（上下文剪裁而非重建）
- 复用 `buildSystemPromptBlocks()`（缓存策略一致）

新代码只添加在"差异点"——隔离逻辑、权限冒泡、transcript 侧链。这保证了子 Agent 的行为与主 Agent 一致（压缩、重试、流式执行等复杂逻辑全部复用），同时保持了独立性。

下一章，我们将探讨 Fork 模式——一种更激进的上下文共享策略。
