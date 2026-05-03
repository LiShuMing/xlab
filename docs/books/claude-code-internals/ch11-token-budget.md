# 第 11 章 Token 预算与输出控制

> Token 是 LLM Agent 的"货币"。每一次 API 调用都在消耗 token，每一次工具执行都在产生需要消耗 token 的输出。Token 预算系统负责控制这个货币的流向——防止 Agent 在低价值操作上过度消耗，同时确保关键信息不会因空间不足而丢失。

---

## 11.1 Token 计数：客户端估算 vs 服务端 usage

Claude Code 需要两种 token 计数：

```typescript
// 1. 客户端估算（不需要 API 调用）
tokenCountWithEstimation(messages)
// 使用启发式规则和字符计数

// 2. 服务端 usage（来自 API 响应的 usage 字段）
message.usage.input_tokens
message.usage.output_tokens
```

### 为什么需要客户端估算？

服务端 usage 只在 API 响应中返回——但决策（是否压缩、是否截断）需要在实际发送前做出。客户端估算给了系统**提前预判**的能力。

### 估算误差的影响

客户端估算通常有 10-30% 的误差。但由于压缩阈值是百分比而非绝对值（"超出 80% 时压缩"而非"超出 160K tokens 时压缩"），误差的影响被缩小——10% 的估算误差只会改变压缩触发点的时间，不会导致误判。

---

## 11.2 工具结果预算：applyToolResultBudget()

工具可以产生巨大的输出——`cat large_file.log` 可能返回 50MB。`applyToolResultBudget()` 控制工具输出的 token 消耗：

```typescript
// 每个工具的默认最大结果大小
// 可通过 tool.maxResultSizeChars 配置
const DEFAULT_MAX_RESULT_CHARS = 50000
```

预算的计算是字符级别（不是 token 级别），因为 tokenization 需要实际调用 tokenizer——对于单纯的字符截断来说太过昂贵。

---

## 11.3 内容替换：processToolResultBlock()

当工具输出超过预算时，不直接丢弃——而是替换为结构化的摘要：

```
原始输出（150K chars）：
  完整日志内容...

→ 截断后：
  [Content truncated: 150,000 characters → 50,000 characters]
  [Showing first 20,000 and last 30,000 characters]
  <snip> ...中间被移除的 100,000 字符... </snip>
  后 30,000 字符...
```

关键设计：**保留头尾、截断中间**。因为信息的分布通常是——开始最重要（header/context），结尾最新（recent events），中间是重复模式。

---

## 11.4 Turn 预算：createBudgetTracker()

`TOKEN_BUDGET` 特性引入了一个数字限长锚：

```typescript
// prompts.ts
'Length limits: keep text between tool calls to ≤25 words. Keep final responses to ≤100 words unless the task requires more detail.'
```

硬性数字比"be concise"更有效——研究显示 ~1.2% 的 token 减少。模型对数字约束的响应比对话义约束的响应更一致。

当用户指定 token 目标（如"+500k"、"spend 2M tokens"）时，系统会在每轮显示剩余预算，Agent 据此规划工作。

---

## 11.5 API 侧预算：output_config.task_budget

除了客户端预算控制，API 请求可以携带 `output_config.task_budget`：

```typescript
{
  output_config: {
    task_budget: {
      total: 100000,      // 总预算
      remaining: 45000,   // 剩余（跨 compact 递减）
    }
  }
}
```

这允许服务端感知预算约束，帮助 LLM 自身在 token 消耗上做出更好的决策。

---

## 本章小结

Token 预算系统解决了两个核心问题：

1. **输入侧**：工具输出太大怎么办？（截断 + 头尾保留）
2. **输出侧**：LLM 输出太多怎么办？（数字限长锚 + 预算感知）

**与数据库的类比**：Token 预算 ≈ 查询的 `LIMIT` 子句和内存限制。`LIMIT 100` 告诉数据库"最多返回这些行"，`≤100 words` 告诉 LLM"最多输出这些词"。内存限制（`work_mem`）控制单次操作的内存使用，`maxResultSizeChars` 控制单个工具的输出上限。
