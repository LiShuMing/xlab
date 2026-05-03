# 第 6 章 工具执行管线：从 tool_use 到 tool_result

> 当 LLM 返回 tool_use block，Agent 的工作才刚刚开始。工具执行管线是 Agent 从"思考"到"行动"的关键桥梁——它负责验证输入、检查权限、执行工具、处理结果。这一章拆解这个管线的每一环。

---

## 6.1 编排层：runTools() 的并发调度

`runTools()` 是工具执行的总编排器。它的核心逻辑是**并发安全分区**：

```
输入: toolUseBlocks = [tool_A, tool_B, tool_C]
      其中 tool_A 和 tool_C 是并发安全的，tool_B 不是

分区结果:
  Group 1: [tool_A, tool_C]  → 并发执行
  Group 2: [tool_B]          → 在 Group 1 完成后串行执行
```

```typescript
// src/services/tools/toolOrchestration.ts (简化)
function partitionToolCalls(toolUseBlocks, tools) {
  const groups: ToolUseBlock[][] = []
  let currentGroup: ToolUseBlock[] = []

  for (const block of toolUseBlocks) {
    const tool = findToolByName(tools, block.name)
    if (tool?.isConcurrencySafe(toolInputFromBlock(block))) {
      currentGroup.push(block)  // 安全的加入当前组
    } else {
      if (currentGroup.length > 0) {
        groups.push(currentGroup)  // 当前组结束
        currentGroup = []
      }
      groups.push([block])  // 不安全工具单独一组
    }
  }
  if (currentGroup.length > 0) groups.push(currentGroup)
  return groups
}
```

### 分区 = 最大化并行度

关键洞察：**并发安全工具按"连续段"分组**，不是按"总体"。这样一段连续的并发安全工具可以同时执行，最大化吞吐。

```
[tool_safe_1, tool_safe_2, tool_unsafe, tool_safe_3]

分区：
  Group 1: [tool_safe_1, tool_safe_2]  ← 并发（两个同时跑）
  Group 2: [tool_unsafe]                ← 串行（等 Group 1 完成）
  Group 3: [tool_safe_3]                ← 串行（等 Group 2 完成）
```

tool_safe_3 不能和 tool_safe_1/2 并发——因为 tool_unsafe 在中间，tool_safe_3 可能依赖 tool_unsafe 的结果。保守分区的代价是失去了一些潜在的并行性，但它保证了**安全性**——绝不会并发执行两个非安全工具。

---

## 6.2 单工具执行：runToolUse() 的完整流程

每个工具调用经历一个精确的多阶段管线：

```
runToolUse() 的完整流程
  ┌──────────────────────────────────────┐
  │ 1. 查找工具                          │
  │    findToolByName(tools, name)       │
  │    → Tool 对象（不存在则错误）        │
  └──────────────────────────────────────┘
  ┌──────────────────────────────────────┐
  │ 2. 输入验证                          │
  │    tool.inputSchema.safeParse(input) │
  │    → 验证通过 / schema 错误           │
  └──────────────────────────────────────┘
  ┌──────────────────────────────────────┐
  │ 3. 前置钩子 (PreToolUse)             │
  │    → 可能拦截、修改输入、注入权限决策 │
  └──────────────────────────────────────┘
  ┌──────────────────────────────────────┐
  │ 4. 权限检查                          │
  │    canUseTool(tool, input, context)  │
  │    → allow / deny / ask             │
  └──────────────────────────────────────┘
  ┌──────────────────────────────────────┐
  │ 5. 工具执行                          │
  │    tool.call(input, context)         │
  │    → Output + 进度事件               │
  └──────────────────────────────────────┘
  ┌──────────────────────────────────────┐
  │ 6. 后置钩子 (PostToolUse)            │
  │    → 可修改输出、注入 MCP 透传       │
  └──────────────────────────────────────┘
  ┌──────────────────────────────────────┐
  │ 7. 结果处理                          │
  │    processToolResultBlock()          │
  │    → 截断、格式化、预算控制           │
  └──────────────────────────────────────┘
```

---

## 6.3 输入验证：为什么模型经常生成无效输入？

```typescript
const parsed = tool.inputSchema.safeParse(input)
if (!parsed.success) {
  // 模型生成了无效输入——返回友好错误
  return { isError: true, output: formatZodError(parsed.error) }
}
```

### Zod 验证失败的两个常见场景

1. **缺字段**：模型忘记提供必填参数——尤其是在复杂嵌套 schema 中
2. **类型错误**：模型提供了错误类型的参数（字符串 vs 数字）

Zod 的错误信息会作为 `tool_result` 返回给模型，让它**自我修正**。这种"错误驱动修复"是 Agent 的一个重要工作模式——模型看到错误信息后在下一轮生成正确的输入。

### 为什么不用 JSON Schema 验证？

JSON Schema 验证缺少友好的错误信息。Zod 的 `safeParse` 返回的错误更具可读性，能帮助模型理解和修正。

---

## 6.4 前置钩子：runPreToolUseHooks()

前置钩子在执行工具**之前**运行，可以实现三个功能：

1. **拦截**：阻止工具执行（返回 `permissionDecision: 'deny'`）
2. **修改输入**：在验证后、执行前修改 input
3. **注入权限决策**：hook 脚本可以指定 `allow` 而不用弹窗

钩子是 shell 脚本，通过文件系统与 Claude Code 交互——脚本从 stdin 读 JSON，向 stdout 写 JSON。这种设计的价值在于：**用户可以用任何语言编写，只要遵守 JSON in/out 协议**。

---

## 6.5 权限检查：三级决策链

权限检查在 `canUseTool()` 中完成，是一个三级决策链（详见第 7 章）：

```
规则引擎（settings.json 中的 alwaysAllow/alwaysDeny）
  → 无匹配 → 自动分类器（Haiku 模型判断安全性）
  → 不确定 → 交互式弹窗（用户手动 allow/deny）
```

---

## 6.6 工具调用：tool.call(input, context)

```typescript
const result = await tool.call(parsedInput, toolUseContext)
```

这里的 `toolUseContext` 是一个包含 35 个字段的上下文对象——它给了工具访问整个 Agent 状态的"上帝视角"：

| 字段 | 用途 |
|------|------|
| `abortController` | 用户 Ctrl+C 中断信号 |
| `messages` | 完整消息历史 |
| `readFileState` | 已读文件缓存 |
| `getAppState` | 获取全局 UI 状态 |
| `options.tools` | 所有可用工具列表 |
| `options.mcpClients` | MCP 服务器列表 |
| `agentId` | 当前 Agent 标识 |

这个 35 字段的"上帝对象"看似违反单一职责原则，但它服务于一个实际需求：工具开发者不应该猜测上下文——他们应该能直接访问所需的任何信息。

---

## 6.7 结果处理：输出预算控制与截断

```typescript
function processToolResultBlock(result, tool, options) {
  // 1. 计算输出大小
  const outputSize = estimateTokens(result.output)

  // 2. 是否超出工具的输出预算？
  if (outputSize > maxOutputBudget) {
    result.output = truncateWithHint(result.output, maxOutputBudget)
  }

  // 3. 格式化为 API tool_result 块
  return {
    type: 'tool_result',
    tool_use_id: result.toolUseId,
    content: [{ type: 'text', text: result.output }],
    is_error: result.isError,
  }
}
```

工具的 `maxResultSizeChars` 定义了每小时工具的最大输出预算——防止一次工具调用产生 100MB 输出填充整个上下文窗口。

---

## 6.8 后置钩子：runPostToolUseHooks()

后置钩子在工具执行**之后**运行，可以实现：

1. **修改输出**：sanitize 敏感信息、添加注释
2. **自动记录操作**：将工具调用记录到操作日志
3. **MCP 透传**：将结果透传给 MCP 系统

后置钩子看不到原始的 tool_use block——它们看到的是执行后的结果。这个设计基于一个正确性考量：验证工具的**实际输出**比验证**预期输入**更重要。

---

## 6.9 流式工具执行：StreamingToolExecutor

这是工具系统中最巧妙的优化——**在 LLM 还在流式输出后续 tool_use blocks 时，已完成的 tool_use block 就可以开始执行**：

```
时间轴：
t0: LLM 开始流式输出
t1: tool_use_A block 完成（content_block_stop）
t2: StreamingToolExecutor 开始执行 tool_A
    LLM 同时流式输出 tool_use_B 的 input_json_delta
t3: tool_use_B block 完成
t4: tool_A 完成，开始执行 tool_B
    LLM 同时流式输出最终的 text block
```

这相当于 CPU 的**流水线**——指令取指、解码、执行的流水线并行。区别在于，CPU 流水线的 stage 是固定的（取指→解码→执行→写回），而 Agent 流水线的 stage 由 LLM 动态决定。

StreamingToolExecutor 的最大价值不是减少单次工具调用的延迟——而是**减少总体端到端时间**。在 Agent 需要调用 5+ 个工具时，流水线执行可以缩短 30-50% 的总时间。

---

## 本章小结

工具执行管线是 Agent 从"推理"到"行动"的桥梁。它的设计体现了三个核心原则：

1. **流水线化**：StreamingToolExecutor 让工具执行与 LLM 输出重叠
2. **分区并发**：安全性标记驱动的自动分区，在安全边界内最大化并行度
3. **多层防护**：Zod 验证 → 前置钩子 → 权限检查 → 后置钩子，每层独立、可插拔

与数据库的类比：这类似于查询执行的 pipeline breaker 概念。Hash Join 的 build 阶段是 pipeline breaker——它必须完成才能进入 probe 阶段。类似地，`isConcurrencySafe: false` 的工具也是 pipeline breaker——必须等它完成后才能继续后续工具。而并发安全工具则像 pipelineable 算子——数据流可以连续通过。

下一章，我们将深入 Agent 安全模型的核心——权限系统。
