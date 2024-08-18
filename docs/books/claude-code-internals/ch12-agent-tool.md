# 第 12 章 Agent 工具：从单体到群体的跃迁

> 单体 Agent 有其极限——上下文窗口的竞争、工具集的臃肿、推理深度的受限。当任务需要并行、需要隔离、需要专业化时，使用 Agent 来调用另一个 Agent 成为必然选择。AgentTool 是这一跃迁的关键——它让 Agent 成为了自己的工具。

---

## 12.1 AgentTool 的接口设计

AgentTool 将一个 Agent 封装为另一个 Agent 可以调用的工具：

```typescript
{
  name: 'Agent',
  description: 'Launch a new agent to handle complex, multi-step tasks.',
  inputSchema: {
    subagent_type: string,    // 内置 Agent 类型或自定义 Agent 名
    prompt: string,           // 子 Agent 的任务描述
    isolation?: 'worktree',  // 隔离模式
    model?: 'sonnet'|'opus'|'haiku',  // 模型覆盖
    run_in_background?: boolean,      // 后台运行
  }
}
```

### 三个关键参数

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `subagent_type` | 选择哪个 Agent 类型 | 必填（fork 模式下可选） |
| `prompt` | 任务描述，子 Agent 将根据这个 prompt 工作 | 必填 |
| `isolation` | 隔离模式（`worktree` 用 git worktree 隔离） | 无隔离 |

---

## 12.2 内置 Agent 类型

### Explore Agent

只读搜索 Agent——代码库探索的专用工具：

```
Explore Agent
  工具: Read, Glob, Grep, Bash (只读)
  模型: 默认 Haiku（可 override）
  特性: 严格只读，适合代码调研
```

### Plan Agent

架构设计 Agent——帮助思考"怎么做"而非实际执行：

```
Plan Agent
  工具: Read, Glob, Grep, Bash, AskUserQuestion
  角色: 设计者，返回步骤计划和文件列表
  特性: 理解架构、考虑 trade-off
```

### code-reviewer Agent

代码审查 Agent——验证实现是否符合计划和规范：

```
code-reviewer Agent
  工具: Read, Glob, Grep
  角色: 审查者，对比代码与计划
  特性: 独立于实现 Agent 的视角
```

---

## 12.3 自定义 Agent：loadAgentsDir()

除了内置 Agent，用户可以通过 `.claude/agents/` 目录定义自定义 Agent：

```markdown
<!-- .claude/agents/deploy-agent.md -->
---
name: deploy-agent
description: Handles deployment and CI/CD operations
tools: Bash, Read, Write
model: sonnet
permissionMode: acceptEdits
maxTurns: 15
---
You are a deployment specialist. Your job is to...
```

`loadAgentsDir()` 解析这些文件的 frontmatter，产生 `AgentDefinition` 对象。每个 Agent 定义可以指定：
- 可用工具集（`tools`）
- 模型（`model`）
- 权限模式（`permissionMode`）
- 最大轮数（`maxTurns`）
- MCP 服务器（`mcpServers`）

---

## 12.4 Agent 定义的结构

```typescript
interface AgentDefinition {
  name: string
  description: string
  tools?: string[]           // 可用工具名列表
  model?: string             // 覆盖主 Agent 的模型
  permissionMode?: PermissionMode
  maxTurns?: number
  mcpServers?: string[]      // 专属 MCP 服务器
  systemPrompt?: string      // 额外的 system prompt
}
```

自定义 Agent 实际上是 **Code as Configuration**——通过声明式配置创建专业化的子 Agent，无需编写代码。这类似于微服务架构中的"服务定义"（Docker Compose / K8s YAML），但针对的是 Agent 而非容器。

---

## 本章小结

AgentTool 代表的是一种**递归能力**——Agent 不仅可以使用工具，还可以使用其他 Agent。这开启了几个关键可能性：

1. **专业化**：不同 Agent 负责不同类型的任务
2. **并行化**：多个 Agent 同时工作
3. **隔离**：子 Agent 的错误不影响父 Agent
4. **弹性扩展**：通过自定义 Agent 无限扩展能力

下一章，我们将深入子 Agent 的执行模型——它如何启动、运行、终止，以及结果如何与父 Agent 交互。
