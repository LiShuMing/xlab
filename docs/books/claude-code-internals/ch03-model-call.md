# 第 3 章 模型调用：流式请求的构建与执行

> 从 System Prompt 组装完成到第一个 token 到达终端，中间经过了一个精密的请求构建与流式处理管线。这一章拆解这个管线中的每一个环节。

---

## 3.1 客户端工厂：四个后端的统一抽象

Claude Code 支持四种 API 后端：Anthropic 直连、AWS Bedrock、Azure Foundry、Google Vertex AI。所有这些后端通过 `getAnthropicClient()` 统一返回 `Anthropic` 类型——调用方完全不感知底层差异。

```typescript
// src/services/api/client.ts
export async function getAnthropicClient({
  apiKey, maxRetries, model, fetchOverride, source,
}): Promise<Anthropic> {
  // 公共逻辑：构建 headers
  const defaultHeaders = {
    'x-app': 'cli',
    'User-Agent': getUserAgent(),
    'X-Claude-Code-Session-Id': getSessionId(),
    // ... container、remote session、SDK client app
  }

  // 后端选择
  if (isEnvTruthy(process.env.CLAUDE_CODE_USE_BEDROCK)) {
    const { AnthropicBedrock } = await import('@anthropic-ai/bedrock-sdk')
    return new AnthropicBedrock({ awsRegion, ...ARGS })
  }
  if (isEnvTruthy(process.env.CLAUDE_CODE_USE_FOUNDRY)) {
    const { AnthropicFoundry } = await import('@anthropic-ai/foundry-sdk')
    return new AnthropicFoundry({ azureADTokenProvider, ...ARGS })
  }
  if (isEnvTruthy(process.env.CLAUDE_CODE_USE_VERTEX)) {
    const { AnthropicVertex } = await import('@anthropic-ai/vertex-sdk')
    return new AnthropicVertex({ region, googleAuth, ...ARGS })
  }
  // 默认：直连
  return new Anthropic({ apiKey, authToken, ...ARGS })
}
```

### 动态加载的 SDK 模块

注意 Bedrock/Foundry/Vertex 的 SDK 导入使用了动态 `import()`，而非静态 `import`。这是因为：

1. **避免强制依赖**：不是所有用户都安装了 `@anthropic-ai/bedrock-sdk`。静态导入会让 `npm install` 强制安装所有后端 SDK。
2. **减小启动体积**：在确定后端类型之前，不需要加载任何特定 SDK。

### 四种后端的差异

| 后端 | 认证方式 | 模型参数 | 特殊约束 |
|------|---------|---------|---------|
| Anthropic 直连 | API Key 或 OAuth | 标准 model ID | 支持所有 beta 功能 |
| AWS Bedrock | AWS IAM 或 Bearer Token | ARN 格式 | 不支持 `defer_loading` advance-tool-use，需 tool-search-tool |
| Azure Foundry | API Key 或 Azure AD | 标准 model ID | 需 azureADTokenProvider |
| Google Vertex | Service Account / ADC | 标准 model ID | 需 projectId 和 region；特殊处理 metadata server 超时 |

### Vertex 的 Metadata Server 超时问题

Vertex 后端有一个值得注意的细节——`GoogleAuth` 在没有项目 ID 环境变量、没有 credential 文件时，会尝试访问 GCE metadata server（`169.254.169.254`），这在非 GCP 环境下会导致 12 秒超时：

```typescript
const googleAuth = new GoogleAuth({
  scopes: ['https://www.googleapis.com/auth/cloud-platform'],
  // 只在用户没有配置其他认证方式时使用 ANTHROPIC_VERTEX_PROJECT_ID
  ...(hasProjectEnvVar || hasKeyFile
    ? {}
    : { projectId: process.env.ANTHROPIC_VERTEX_PROJECT_ID }),
})
```

这个优化对不同后端环境的用户体验至关重要——12 秒的额外等待会很明显。

---

## 3.2 请求参数构建：从多源输入到统一参数

`queryModel()` 是流式请求的入口函数，签名中的参数来源分散在整个系统：

```typescript
// src/services/api/claude.ts (简化)
async function* queryModel(
  messages: Message[],        // 来自 query.ts 的消息历史
  systemPrompt: SystemPrompt, // 来自 getSystemPrompt() 的数组
  thinkingConfig: ThinkingConfig, // 用户配置 / 模型检测
  tools: Tools,               // 来自 assembleToolPool()
  signal: AbortSignal,        // 用户 Ctrl+C 或超时
  options: Options,           // 大量运行时配置
): AsyncGenerator<StreamEvent | AssistantMessage | SystemAPIErrorMessage>
```

### 请求前的处理管线

在发出 API 请求之前，`queryModel()` 执行了一系列预处理：

```
queryModel() 内部管线
  ├── 检查 off-switch（tengu-off-switch GB 配置）
  ├── 解析模型名（ARN → 实际 model ID）
  ├── 收集 beta headers
  ├── 工具 schema 过滤：
  │   ├── tool_search 开关判断（isToolSearchEnabled）
  │   ├── 区分 defer_loading 工具和常规工具
  │   └── 从消息历史中提取已发现的工具名
  ├── 构建工具 schema（toolToAPISchema）
  ├── 消息标准化（normalizeMessagesForAPI）
  ├── 配对修复（ensureToolResultPairing）
  ├── advisor/server_tool_use 处理
  ├── 媒体数量裁剪（stripExcessMediaItems）
  ├── 指纹计算（computeFingerprintFromMessages）
  ├── system prompt 前缀拼接（attribution header + sysprompt prefix）
  └── system prompt block 构建（buildSystemPromptBlocks）
```

这十几个步骤可以分为四组：**安全检查**（off-switch）→ **工具准备**（schema 构建、过滤、defer）→ **消息准备**（标准化、配对修复、媒体裁剪）→ **缓存优化**（beta headers、system prompt blocks）。

### 工具发现机制

当 `tool_search` 启用时，`queryModel()` 会从消息历史中**提取已发现的工具名**，只将这些工具的完整 schema 发送给 API：

```typescript
const discoveredToolNames = extractDiscoveredToolNames(messages)
filteredTools = tools.filter(tool => {
  if (!deferredToolNames.has(tool.name)) return true        // 常规工具：始终发送
  if (toolMatchesName(tool, TOOL_SEARCH_TOOL_NAME)) return true  // ToolSearch 本身
  return discoveredToolNames.has(tool.name)                  // 已发现的延迟工具
})
```

这意味着即使你有 50 个 MCP 工具，第一次 API 调用时可能只发送 5 个核心工具。ToolSearchTool 允许模型按需发现和加载其他工具。这个设计解决了工具数量膨胀的问题——每个工具 schema 的 token 消耗是固定的，但总 token 数是可变的。

---

## 3.3 工具 Schema 生成：Zod → JSON Schema

`toolToAPISchema()` 负责将内部的 `Tool` 对象转换为 API 所需的 `BetaToolUnion` 格式。这个转换不是简单的序列化——它涉及缓存、条件特性注入、kill switch：

```typescript
// src/utils/api.ts (简化)
export async function toolToAPISchema(tool, options): Promise<BetaToolUnion> {
  const cacheKey = 'inputJSONSchema' in tool
    ? `${tool.name}:${jsonStringify(tool.inputJSONSchema)}`
    : tool.name
  const cache = getToolSchemaCache()
  let base = cache.get(cacheKey)
  if (!base) {
    base = {
      name: tool.name,
      description: await tool.prompt({...}),
      input_schema: 'inputJSONSchema' in tool
        ? tool.inputJSONSchema
        : zodToJsonSchema(tool.inputSchema),
    }
    // 条件特性注入
    if (strictToolsEnabled && tool.strict && modelSupportsStructuredOutputs(model)) {
      base.strict = true
    }
    if (FGTS_enabled) {
      base.eager_input_streaming = true
    }
    cache.set(cacheKey, base)
  }

  // Per-request overlay（不修改缓存的 base）
  const schema = { ...base }
  if (options.deferLoading) schema.defer_loading = true
  if (options.cacheControl) schema.cache_control = options.cacheControl

  // 实验特性 kill switch
  if (isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS)) {
    // 剥离所有不在 allowlist 中的字段
  }
  return schema
}
```

### 三层缓存设计

工具 schema 的构建分三层：

1. **Session 级缓存**（`getToolSchemaCache()`）：name、description、input_schema——这些在一次会话中不变。用工具名做 key 缓存。
2. **Feature flag 注入**（strict、eager_input_streaming）：在 base 构建时注入，但受 feature gate 控制——gate 在会话期间不会翻转（latch），所以缓存安全。
3. **Per-request overlay**（defer_loading、cache_control）：每次 API 调用可能不同。通过拷贝 base 后覆盖，不污染缓存。

### Zod → JSON Schema 的转换

Claude Code 内部使用 Zod 做运行时验证，但 API 需要 JSON Schema。`zodToJsonSchema()` 负责这个转换。工具也可以直接提供 `inputJSONSchema` 来跳过这个转换——这主要用于 MCP 工具，它们的 schema 已经以 JSON 格式存在于 MCP 协议中。

### Kill Switch 机制

`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` 作为一个"终极保险"，会在所有字段构建完成后剥离所有不在 allowlist 中的字段：

```typescript
if (isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS)) {
  const allowed = new Set(['name', 'description', 'input_schema', 'cache_control'])
  // 剥离 defer_loading、strict、eager_input_streaming
}
```

这个设计是防御性的——当某个 beta 字段导致代理/LB 返回 400 时，可以立即通过环境变量全局剔除。

---

## 3.4 消息标准化：内部类型到 API 类型的映射

第 1 章已介绍了消息类型系统。这里聚焦于 `normalizeMessagesForAPI()` 的具体实现细节：

```
内部消息 → API 消息 的转换规则
────────────────────────────────
AssistantMessage       → { role: "assistant", content: ContentBlock[] }
UserMessage            → { role: "user", content: string | ContentBlock[] }
AttachmentMessage      → 丢弃（内容已被合并为 user message）
ProgressMessage        → 丢弃（不发送给 API）
StreamEvent            → 丢弃（只在客户端使用）
SystemMessage          → 丢弃（compact_boundary 等仅用于内部）
TombstoneMessage       → 丢弃（墓碑消息不发送）
```

### 四个关键的后处理步骤

标准化之后还有四个修复步骤：

1. **工具搜索字段剥离**（`stripToolReferenceBlocksFromUserMessage`）：当模型不支持 `tool_search` 时，移除 `tool_reference` 块——否则 API 返回 400。

2. **tool_use/tool_result 配对修复**（`ensureToolResultPairing`）：对于孤立的 `tool_use`（没有对应 `tool_result`），插入合成的 error `tool_result`。对于孤立的 `tool_result`（引用不存在的 `tool_use`），直接移除。这防止了 resuming remote/teleport 会话时的 400 错误。

3. **Advisor 块剥离**（`stripAdvisorBlocks`）：当 advisor beta header 未启用时，移除 `server_tool_use` 和 `advisor_tool_result` 块。

4. **媒体数量裁剪**（`stripExcessMediaItems`）：API 限制每请求最多 100 个 media 块。超过时静默丢弃最旧的，而非报错。

### 为什么要有配对修复？

这个问题源于会话的持久化和恢复。当 remote session 从磁盘恢复时，消息历史可能处于不完整状态——最后一条 assistant 消息的工具调用还未执行、或其结果丢失。直接发送不配对的消息会导致 400 错误，而 400 在 Agent Loop 中是致命的——它无法通过重试自然恢复。

配对修复是一个**防御性设计**：它接受"状态可能不完美"这个前提，通过自动修复保证 API 调用不会因此失败。

---

## 3.5 缓存断点：cache_control 的精确放置

`addCacheBreakpoints()` 是控制 prompt cache 行为的核心函数。它的任务是在消息数组中精确放置 `cache_control` 标记：

```typescript
// src/services/api/claude.ts (简化)
export function addCacheBreakpoints(
  messages, enablePromptCaching, querySource, useCachedMC, ...
): MessageParam[] {
  // 精确一个 message-level cache_control marker
  // 两个 marker 会阻止 mycro 的 turn-to-turn eviction
  const markerIndex = skipCacheWrite
    ? messages.length - 2    // fork: 最后一个共享前缀点
    : messages.length - 1    // 正常: 最后一条消息

  const result = messages.map((msg, index) => {
    const addCache = index === markerIndex
    return msg.type === 'user'
      ? userMessageToMessageParam(msg, addCache, ...)
      : assistantMessageToMessageParam(msg, addCache, ...)
  })

  // cache_edits 插入（microcompact 优化）
  // cache_reference 标记（tool_result 去重引用）
}
```

### 为什么只有一个 marker？

注释中解释了关键的设计决策：

> Exactly one message-level cache_control marker per request. Mycro's turn-to-turn eviction frees local-attention KV pages at any cached prefix position NOT in cache_store_int_token_boundaries. With two markers the second-to-last position is protected and its locals survive an extra turn even though nothing will ever resume from there — with one marker they're freed immediately.

简单来说，Anthropic 的服务端缓存系统（内部代号 mycro）在每个 cache_control 标记处保护 KV cache 页。如果放两个 marker，第二个 marker 处的 local attention 页会被"过度保护"——没有请求会从那里继续，但它们占用了缓存空间。一个 marker 确保只保护真正需要的位置。

### cache_edits 和 cache_reference

`cache_edits` 是 microcompact（第 9 章详细介绍）的关键机制——它允许在缓存层面替换 tool_result 内容而不破坏前缀缓存。`cache_reference` 则是标记 tool_result 的唯一标识，用于服务端去重。

---

## 3.6 Beta Header 管理：会话级 Latch 策略

`queryModel()` 管理着一组 beta headers，每个都采用了特殊的 **latch**（锁存）策略：

```typescript
// 每个 header 独立 latch
let afkHeaderLatched = getAfkModeHeaderLatched() === true
if (!afkHeaderLatched && isAgenticQuery && isAutoModeActive()) {
  afkHeaderLatched = true
  setAfkModeHeaderLatched(true)
}

let fastModeHeaderLatched = getFastModeHeaderLatched() === true
if (!fastModeHeaderLatched && isFastMode) {
  fastModeHeaderLatched = true
  setFastModeHeaderLatched(true)
}

let thinkingClearLatched = getThinkingClearLatched() === true
if (!thinkingClearLatched && isAgenticQuery) {
  if (Date.now() - lastCompletion > CACHE_TTL_1HOUR_MS) {
    thinkingClearLatched = true
    setThinkingClearLatched(true)
  }
}
```

### Latch 的目的

为什么用 latch 而非每次查询直接检查条件？因为 **prompt cache 的 key 包含 headers**。如果在会话中途 header 从"无"变为"有"（或反过来），cache key 就变了——之前缓存的内容全部失效，需要重新传输整个 prompt。

Latch 的核心逻辑是"**一旦开启，永不关闭**"（在 `/clear` 或 `/compact` 之前）。这样：

- 第一次 API 调用：检查条件，如果满足就设置 header，开启 latch
- 后续 API 调用：直接从 latch 读取，不再检查条件，header 保持稳定
- `/clear` 或 `/compact`：清除所有 latch，重新评估

### Latch 的清理

```typescript
export function clearSystemPromptSections(): void {
  clearSystemPromptSectionState()
  clearBetaHeaderLatches()  // 清除所有 header latch
}
```

每次 compaction 后，所有 header 重新评估——因为 compaction 改变了消息历史，cache 本身就重新开始了。

---

## 3.7 流式响应处理：事件驱动状态机

流式响应的处理是一个完整的事件驱动状态机：

```typescript
// src/services/api/claude.ts (简化)
for await (const part of stream) {
  // 流式 stall 检测
  if (lastEventTime !== null) {
    const gap = now - lastEventTime
    if (gap > STALL_THRESHOLD_MS) {
      stallCount++
      logEvent('tengu_streaming_stall', { stall_duration_ms: gap })
    }
  }

  switch (part.type) {
    case 'message_start':
      partialMessage = part.message
      ttftMs = Date.now() - start
      usage = updateUsage(usage, part.message?.usage)
      break

    case 'content_block_start':
      contentBlocks[part.index] = part.content_block
      break

    case 'content_block_delta':
      // 增量拼接 text/thinking/tool_use input
      contentBlocks[part.index].delta += part.delta
      break

    case 'content_block_stop':
      // content block 完成，缝合到部分消息
      break

    case 'message_stop':
      // 消息完成，产出 AssistantMessage
      yield assistantMessage
      break
  }
}
```

### 五种事件类型

| 事件 | 含义 | 处理逻辑 |
|------|------|---------|
| `message_start` | 消息开始 | 记录 TTFB、初始化 usage、保存 research 元数据 |
| `content_block_start` | 内容块开始 | 创建 block（text/thinking/tool_use/server_tool_use），初始化空内容 |
| `content_block_delta` | 增量内容 | 追加 text/thinking/json_delta/signature_delta |
| `content_block_stop` | 内容块完成 | 标记 block 完成 |
| `message_stop` | 消息完成 | 组装 AssistantMessage，从 stop_reason 判断是否需要 follow-up |

### SDK 的"重复文本"问题

代码中有一段值得注意的注释：

```
// awkwardly, the sdk sometimes returns text as part of a
// content_block_start message, then returns the same text
// again in a content_block_delta message. we ignore it here
```

这是一个实际遇到过的 SDK 行为问题：有时 `content_block_start` 携带了文本内容，`content_block_delta` 又重复发送。Claude Code 的处理方式是在 `content_block_start` 时将文本初始化为空字符串，强制从 delta 开始计数——牺牲了 SDK 提供的初始文本来换取一致性。

### 流式 Stall 检测

```typescript
if (lastEventTime !== null) {
  const timeSinceLastEvent = now - lastEventTime
  if (timeSinceLastEvent > STALL_THRESHOLD_MS) {
    stallCount++
    logEvent('tengu_streaming_stall', { stall_duration_ms: timeSinceLastEvent })
  }
}
```

流式 stall 检测是一项可观测性优化。它不干预请求处理，只是记录——用于分析后端性能和容量问题。

---

## 3.8 内容块积累：四种块的差异处理

API 返回的 content block 有四种主要类型，每种有独特的拼接规则：

### text 块

最直接——文本增量追加：

```
delta.text = "Hello"
delta.text = " world"
→ "Hello world"
```

### thinking 块

与 text 类似，但多了 `signature` 字段（用于验证 thinking 内容的完整性）：

```
content_block_start: { thinking: "", signature: "" }
signature_delta: { signature: "abc..." }
thinking_delta: { thinking: "Let me analyze..." }
```

注意 `signature` 被初始化为空字符串——确保即使 `signature_delta` 从未到达，字段也存在。

### tool_use 块

最复杂——输入是 JSON 的增量片段：

```
content_block_start: { id: "toolu_xxx", name: "Bash", input: "" }
input_json_delta: { partial_json: "{\"command\":" }
input_json_delta: { partial_json: "\"ls -la\",\"description\":" }
input_json_delta: { partial_json: "\"list files\"}" }
→ input = '{"command":"ls -la","description":"list files"}'
```

`input` 字段在整个流式期间保持为字符串——JSON.parse 在 `content_block_stop` 时才执行。这是为了避免解析不完整的 JSON 导致的错误。

### server_tool_use 块

与 `tool_use` 类似，但用于服务端工具（如 advisor）。关键差异：`server_tool_use` 的 `input` 是一个 object 而非 string：

```typescript
case 'server_tool_use':
  contentBlocks[part.index] = {
    ...part.content_block,
    input: '' as unknown as { [key: string]: unknown },
  }
```

这是 SDK 层面的类型差异——`server_tool_use` 的结构定义与 `tool_use` 不完全一致。

---

## 3.9 重试与降级：withRetry 的指数退避

`withRetry()` 是 API 调用的韧性层。默认最多 10 次重试，基础延迟 500ms：

```typescript
// src/services/api/withRetry.ts (简化)
const DEFAULT_MAX_RETRIES = 10
export const BASE_DELAY_MS = 500

// 前景查询源才会在 529 时重试
const FOREGROUND_529_RETRY_SOURCES = new Set([
  'repl_main_thread', 'sdk', 'agent:custom', 'compact',
  'hook_agent', 'verification_agent', 'side_question',
  'auto_mode', 'bash_classifier',
])

function shouldRetry529(querySource) {
  return querySource === undefined || FOREGROUND_529_RETRY_SOURCES.has(querySource)
}
```

### 错误分类与处理策略

| 错误类型 | HTTP 状态 | 处理策略 |
|----------|----------|---------|
| Overloaded (529) | 529 | 前景查询：指数退避，最多 3 次；背景查询：立即放弃 |
| Rate Limit (429) | 429 | 指数退避，读取 Retry-After header |
| Auth (401) | 401 | OAuth 刷新，清除 API key cache，重试 |
| Connection Error | - | 指数退避，检查是否需要 credential 刷新 |
| Fallback Triggered | - | 触发非流式降级 |
| User Abort | - | 直接抛出，不重试 |
| AWS Credential Error | - | 清除 credential cache，重试 |

### 529（Overloaded）的分级策略

529 被特殊对待——只有"前景"查询才重试。"前景"意味着用户正在等待这个结果。背景查询（摘要、标题、分类器）立即放弃：

> Foreground query sources where the user IS blocking on the result — these retry on 529. Everything else bails immediately: during a capacity cascade each retry is 3-10x gateway amplification, and the user never sees those fail anyway.

这个设计体现了一个重要的工程原则：**在负载高峰期间，放弃低优先级的请求来保护高优先级请求的资源**。每个 529 重试都会增加 API 网关的压力（3-10 倍的放大效应），所以在容量 cascade 时放弃背景任务是理性的选择。

### 持久化重试模式

Claude Code 还支持 `CLAUDE_CODE_UNATTENDED_RETRY` 模式——用于无人值守会话（ant-only），它对 429/529 进行**无限期重试**：

```
重试间隔上限：5 分钟
重置时间上限：6 小时
心跳间隔：30 秒（防止宿主环境将 session 标记为空闲）
```

心跳通过 yield `SystemAPIErrorMessage` 实现——这是一个 stopgap 方案，直到有专用的 keep-alive 通道。

### 非流式降级（Fallback）

当流式请求反复失败时，`withRetry()` 会触发 **非流式降级**：

```
流式失败 → FallbackTriggeredError → onStreamingFallback() → queryModelWithoutStreaming()
```

非流式路径使用 `executeNonStreamingRequest()`，它调用 `anthropic.beta.messages.create({stream: false})`，等待完整响应后一次性返回。这个降级路径的 timeout 在 remote session 中设为 120s（常规 300s），以适配 container 的 idle-kill 约束。

降级不只是换了 API 调用方式——它还意味着整个 Agent Loop 的执行模型从"流式交互"退回到"批量响应"。用户体验会变差，但至少 Agent 能继续工作。

### 指数退避的实现

```
尝试 1: 500ms
尝试 2: 1000ms
尝试 3: 2000ms
尝试 4: 4000ms
...
尝试 10: 256,000ms (≈ 4.3 分钟)
```

每次重试前会检查 `signal.aborted`——如果用户在等待期间按了 Ctrl+C，重试立即中断。

---

## 本章小结

从客户端工厂到流式响应处理，模型调用管线展现了 LLM Agent 架构的另一个核心主题：**接口适配的复杂度**。

一个看似简单的"调用 API"操作，实际需要处理：

1. **四种后端**的统一抽象（Anthropic/Bedrock/Foundry/Vertex）
2. **消息标准化**的复杂映射（10 种内部类型 → 2 种 API 角色）
3. **缓存断点**的精确放置（一个 marker 的设计哲学）
4. **Beta header** 的 latch 策略（稳定性的代价）
5. **流式事件**的状态机处理（5 种事件的差异拼接）
6. **重试降级**的分级策略（前景 vs 背景、流式 vs 非流式）

这些不是"复杂度 accidental"，而是与外部系统交互的**必然成本**。每个 API 提供商有不同的认证机制、不同的参数限制、不同的错误语义。统一这些差异的代码本身就是系统设计的重要组成部分。

**与数据库系统的类比**：这类似于数据库的存储引擎适配层。MySQL 的 InnoDB、PostgreSQL 的 heap、MongoDB 的 WiredTiger——它们在"存储和检索数据"这个抽象上一致，但具体的行为、错误模式、性能特征完全不同。数据库通过 storage engine interface 统一这些差异，Claude Code 通过 `getAnthropicClient()` + `Anthropic` 类型做到同样的事。

下一章，我们将进入本书最核心的一章——Agent Loop 的 `while(true)` 主循环，理解"思考→行动→观察"如何在代码层面实现。
