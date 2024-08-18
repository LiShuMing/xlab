# 第 4 章 Agent Loop：while(true) 的哲学

> Agent 的本质是一次"思考→行动→观察"的循环。单次 API 调用只产生一个"思考"，而 `while(true)` 将单次思考串联为持续行动。这一章拆解循环的完整机制。

---

## 4.1 三层抽象：QueryEngine → query → queryModel

Claude Code 的调用链由三层抽象组成，每层有明确的职责边界：

```
QueryEngine.submitMessage()      ← 会话管理、用户交互、SDK 消息产出
    ↓
query()                          ← Agent Loop、工具编排、压缩调度
    ↓
queryModel()                     ← API 请求构建、流式处理、重试降级
```

这种分层体现了**关注点分离**：

| 层 | 职责 | 输入 | 输出 |
|---|------|------|------|
| QueryEngine | 会话生命周期、用户输入处理、消息转换 | 用户输入字符串 | `AsyncGenerator<SDKMessage>` |
| query() | 循环控制、工具结果显示、压缩触发 | 消息历史 + system prompt | `AsyncGenerator<Message>` |
| queryModel() | HTTP 请求、流式解析、缓存管理 | 标准化消息 + 工具列表 | `AsyncGenerator<StreamEvent \| AssistantMessage>` |

### 类比：数据库查询引擎

```
QueryEngine  ≈ JDBC Connection  — 管理会话、提交 SQL
query()      ≈ Query Executor   — 执行计划、迭代器模型
queryModel() ≈ Storage Engine   — 实际的数据读写
```

---

## 4.2 主循环结构：while(true) 中的状态机

`query()` 的核心是一个 `while(true)` 循环——1729 行的文件中，循环本身横跨 1500+ 行：

```typescript
// src/query.ts (简化)
export async function* query(params: QueryParams): AsyncGenerator<Message> {
  const deps = params.deps ?? productionDeps()
  const config = buildQueryConfig()

  let state: State = {
    messages: params.messages,
    toolUseContext: params.toolUseContext,
    turnCount: 1,
    // ...
  }

  // eslint-disable-next-line no-constant-condition
  while (true) {
    let { toolUseContext } = state
    const { messages, turnCount, ... } = state

    // 1. 压缩预处理（snip → microcompact → autocompact）
    // 2. 模型调用（deps.callModel）
    // 3. 工具执行（如果有 tool_use）
    // 4. 终止条件检查
    // 5. continue / break
  }
}
```

### 循环的五个阶段

```
while(true) 的每次迭代
  ┌─────────────────────────────────────────┐
  │ 阶段 1: 压缩预处理                       │
  │ snip → microcompact → autocompact       │
  │ → boundary_message                      │
  └─────────────────────────────────────────┘
  ┌─────────────────────────────────────────┐
  │ 阶段 2: 模型调用                         │
  │ callModel(messages, systemPrompt, tools)│
  │ → AssistantMessage (含 text/thinking/   │
  │    tool_use blocks)                      │
  └─────────────────────────────────────────┘
  ┌─────────────────────────────────────────┐
  │ 阶段 3: 工具执行                         │
  │ runTools(toolUseBlocks, context)         │
  │ → UserMessage (含 tool_result blocks)   │
  └─────────────────────────────────────────┘
  ┌─────────────────────────────────────────┐
  │ 阶段 4: 终止条件检查                      │
  │ needsFollowUp? stop_reason? maxTurns?    │
  └─────────────────────────────────────────┘
  ┌─────────────────────────────────────────┐
  │ 阶段 5: 状态转换                         │
  │ state = { ...newState }                 │
  │ continue / break / return               │
  └─────────────────────────────────────────┘
```

### continues 站点的设计

循环中有多个 continue 站点——每个都是一个"不调用 API 但需要重新进入循环"的路径。状态更新通过一次性对象赋值完成：

```typescript
// 7 个 continue 站点都遵循这个模式
state = {
  ...state,
  messages: messagesForQuery,
  toolUseContext,
  // ... 其他可变字段
}
continue
```

为什么用对象整体赋值而非逐一修改属性？因为这样能确保 TypeScript 的类型收窄正确处理，同时让状态转换可审计——每个 continue 站点显式声明自己改变了哪些字段。

---

## 4.3 State 对象：跨迭代可变状态

`State` 是一个包含 9 个字段的结构体，封装了循环中所有跨迭代的可变状态：

```typescript
let state: State = {
  messages: params.messages,               // 消息历史（不断增长）
  toolUseContext: params.toolUseContext,   // 工具执行上下文
  maxOutputTokensOverride: undefined,      // 恢复重试覆盖值
  autoCompactTracking: undefined,          // 压缩后的追踪状态
  stopHookActive: undefined,               // stop hook 是否激活
  maxOutputTokensRecoveryCount: 0,         // 该错误的恢复计数
  hasAttemptedReactiveCompact: false,      // 是否尝试过响应式压缩
  turnCount: 1,                            // 当前迭代编号
  pendingToolUseSummary: undefined,        // 待处理的工具调用摘要
  transition: undefined,                   // 状态转换标记
}
```

### 为什么要封装为 State？

在早期的实现中，这些字段是循环中的独立 `let` 变量。随着 continue 站点的增加（从 2 个增长到 7 个），每次 continue 前需要手动更新所有可变字段——容易遗漏。`State` 对象统一了更新路径。

在循环顶部解构 `State`：

```typescript
let { toolUseContext } = state
const { messages, autoCompactTracking, ..., turnCount } = state
```

`toolUseContext` 是唯一用 `let` 解构的——因为在一次迭代内它会被多次重新赋值（queryTracking 更新、messages 更新等）。其余字段在迭代内只读。

---

## 4.4 依赖注入：QueryDeps 与 productionDeps

`query()` 通过依赖注入实现可测试性：

```typescript
// src/query/deps.ts
export interface QueryDeps {
  uuid: () => string
  microcompact: (messages, toolUseContext, querySource) => Promise<MicrocompactResult>
  callModel: (params) => AsyncGenerator<...>
  recordThought: (messages, ...) => Promise<void>
}

export function productionDeps(): QueryDeps {
  return {
    uuid: randomUUID,
    microcompact: microcompactConversation,
    callModel: queryModelWithStreaming,
    recordThought: recordThought,
  }
}
```

在测试中，可以注入 mock 实现：

```typescript
// 测试中
query({ ..., deps: { ...productionDeps(), callModel: mockCallModel } })
```

这个模式的价值不在于单元测试覆盖——LLM 调用的确定性很低。它的价值在于**异常路径测试**：可以注入一个总是抛出 `PromptTooLongError` 的 `callModel`，验证恢复逻辑的正确性。

---

## 4.5 配置快照：buildQueryConfig

```typescript
const config = buildQueryConfig()
```

`buildQueryConfig()` 在循环入口处执行一次，快照所有环境变量、feature flags、session 状态。这确保了一次用户输入对应的整个 Agent Loop 中，配置保持一致。

哪些配置需要快照？

- **环境变量**：`isEnvTruthy` 检查的各类开关
- **Feature gates**：`feature()` 检查的 GrowthBook 配置
- **Session 状态**：permission mode、fast mode
- **Gates 集合**：`streamingToolExecution`、`fastModeEnabled`、`isAnt`

哪些**不需要**快照？`tool_choice`——它在每次迭代中根据工具执行结果动态变化；`maxOutputTokensOverride`——它是恢复逻辑的一部分，需要在迭代间可变。

---

## 4.6 终止条件：何时 break，何时 continue

Agent Loop 的核心判断是 `needsFollowUp`——它决定循环继续还是终止：

```typescript
let needsFollowUp = false

// 在工具执行后设置：
if (toolUseBlocks.length > 0) {
  needsFollowUp = true   // 有工具调用 → 执行后继续
}

// 在循环底部：
if (!needsFollowUp) {
  break  // 无工具调用 → 本轮结束
}
```

但 `needsFollowUp` 不是唯一的终止条件。完整的终止判断包括：

1. **无工具调用**：assistant 的 `stop_reason` 是 `end_turn`，且没有 tool_use block
2. **达到最大轮数**：`turnCount >= maxTurns`（防止无限循环消耗资源）
3. **用户中断**：`abortController.signal.aborted`
4. **模型返回错误**：无法恢复的 API 错误
5. **Blocking limit**：上下文超出硬性限制，需要手动 `/compact`
6. **stop hook 触发**：用户配置的 stop hook 返回终止信号

这些条件分布在循环的多个位置，形成了"高内聚、声明式"之外的另一种代码组织方式——分散在 1500 行循环中的多处判断点。这不是设计缺陷，而是复杂状态机的自然形态。

---

## 4.7 异常恢复路径

Agent Loop 中嵌入了多条异常恢复路径。这些不是为了优雅降级，而是为了**保证 Agent 在异常后仍能继续工作**。

### 路径 1：max_output_tokens 恢复

当 API 返回 `max_output_tokens` 超出的错误，恢复策略是：

```
工具输出太长 → 超出 max_output_tokens → 自动提升限制 → 重试
```

```typescript
if (error.error === 'max_output_tokens') {
  maxOutputTokensRecoveryCount++
  if (maxOutputTokensRecoveryCount <= 2) {
    state.maxOutputTokensOverride = 根据错误信息计算新值
    continue  // 用新的限制重试
  }
}
```

最多重试 2 次——避免无限循环。

### 路径 2：prompt-too-long 恢复

这是一个更复杂的恢复链：

```
API 返回 413（prompt too long）
  → Context Collapse: drain staged collapses
    → 成功 → continue
    → 失败 → Reactive Compact
      → 成功 → continue
      → 失败 → 返回错误让用户手动 compact
```

如果 prompt-too-long 是由图片/PDF 导致的，还有**媒体移除**恢复路径——直接移除最旧的媒体附件。

### 路径 3：模型降级

当指定模型持续失败，降级到 fallback 模型：

```typescript
const fallbackModel = params.fallbackModel
// 流式失败后 → 切换 fallbackModel → 重试
```

### 路径 4：非流式降级

当流式请求本身失败（非模型问题），切换到非流式：

```
流式 10 次重试全失败 → FallbackTriggeredError → 非流式请求
```

### 异常恢复的设计原则

这些恢复路径的共同特点是**渐进性**——每一步都增加恢复力度：

```
1. 调整参数（提升 token 限制）
2. 减少上下文（snip → 折叠 → compact）
3. 更换方式（流式 → 非流式）
4. 更换模型（主模型 → fallback）
5. 终止（返回错误给用户）
```

每一步的"成本"都比上一步高——提升 token 限制增加费用，压缩减少上下文质量，降级影响用户体验。所以恢复从最便宜的方案开始尝试。

---

## 本章小结

Agent Loop 的 `while(true)` 不只是控制流——它是一种**设计宣言**：Agent 应该持续推理直到自然终止，而非预设固定的轮数或 token 数。

三个关键设计决策支撑了这个声明：

1. **State 对象封装**：9 个可变字段统一管理，7 个 continue 站点一致更新
2. **配置快照**：循环入口处一次性快照，确保整个 turn 中配置不变
3. **渐进式恢复**：5 条恢复路径从便宜到昂贵逐级尝试

**与数据库系统的类比**：Agent Loop 类似于数据库 volcano 模型的 `next()` 调用——每次调用产生一行结果，调用者通过检查是否有更多行来决定是否继续。区别在于，Agent Loop 的"行"是 (思考, 行动, 观察) 三元组，而终止条件更复杂——不仅是"没有更多行"，还包括资源约束、错误边界和用户意愿。

下一章，我们将深入 Agent 感知与行动的核心接口——工具系统。
