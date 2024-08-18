# 第 15 章 Coordinator 与 Swarm：分布式 Agent 架构

> 当任务庞大到单个 Agent 无法应对，我们需要的不只是一个子 Agent，而是一群 Agent 协同工作。Coordinator 模式和 Swarm 架构代表了 Agent 分布式协作的最高形态——一个主 Agent 指挥多个 Worker，共享状态、并行执行、自动协调。

---

## 15.1 Coordinator 模式

Coordinator 是一个特殊的 Agent 角色——它自己不执行具体任务，而是**分解任务、分发给 Worker、收集结果、合并汇报**：

```
用户请求: "Rewrite the auth module and update all tests"
                ↓
          Coordinator Agent
          ├── Worker A: "Rewrite auth.ts"
          ├── Worker B: "Update auth.test.ts"
          └── Worker C: "Update integration tests"
                ↓
          Coordinator: 合并结果 → 报告用户
```

### 协调逻辑

```typescript
// src/coordinator/coordinatorMode.ts (概念)
class Coordinator {
  async handleRequest(userRequest: string) {
    const subtasks = await this.decompose(userRequest)
    const workers = this.spawnWorkers(subtasks)
    const results = await Promise.all(workers.map(w => w.execute()))
    return this.merge(results)
  }
}
```

---

## 15.2 In-Process Teammate：同进程多 Agent

Teammate 模式让多个 Agent 在同一个进程中运行，共享状态：

```
进程
  ├── Agent 1 (主线程)
  ├── Agent 2 (teammate)
  └── Agent 3 (teammate)
```

优势：零序列化开销、共享内存状态、实时通信。
劣势：无隔离——一个 Agent 的崩溃影响所有。

---

## 15.3 Agent Swarm：动态集群

Swarm 是更动态的 Agent 群体：

```
Swarm Manager
  ├── spawn: 按需创建 Agent
  ├── permissions: 权限统一管理和同步
  └── leader-bridge: Leader 与 Worker 的通信桥
```

关键特性：
- **动态扩容**：任务量大时自动增加 Worker
- **权限同步**：Leader 的权限决策同步给所有 Worker
- **健康检查**：检测卡住的 Worker 并重启

---

## 15.4 消息邮箱：Agent 间异步通信

```typescript
// src/context/mailbox.tsx
interface Mailbox {
  send(to: AgentId, message: Message): void
  receive(): Promise<Message>
  // 无需锁定——Agent 单线程，邮箱自然无竞态
}
```

Agent 之间不共享内存，通过 mailbox 异步通信——这类似于 Erlang 的 actor model，但运行在 JavaScript 的单线程事件循环中。

---

## 15.5 后台任务框架

Claude Code 支持五种后台任务：

| 任务类型 | 描述 | 使用场景 |
|----------|------|---------|
| `LocalShellTask` | 本地 shell 命令 | 长时间运行的构建/测试 |
| `LocalAgentTask` | 本地 Agent 实例 | 后台代码审查 |
| `RemoteAgentTask` | 远程 Agent | CCR 会话中的远程任务 |
| `DreamTask` | 空闲状态 Agent | 持续推理、主动发现 |

`CronCreateTool` 和 `RemoteTriggerTool` 让 Agent 可以自己创建定时和触发器任务。

---

## 15.6 分布式 Agent 的挑战

分布式多 Agent 面临的关键挑战：

1. **状态一致性**：Worker 的发现如何同步？通过 leader 广播。
2. **错误传播**：一个 Worker 的失败如何影响其他？通过错误边界隔离。
3. **资源竞争**：多个 Agent 争抢同一 API key 的并发配额？通过速率限制和排队。
4. **结果合并**：多个 Worker 的冲突结果如何合并？Coordinator 做最终仲裁。

---

## 本章小结

从单体 Agent 到 Swarm，架构的演进反映了规模问题：

```
单 Agent → 工具调用
  → AgentTool（子 Agent）→ 专业化
    → Fork → 缓存共享
      → Coordinator → 任务分解
        → Swarm → 动态集群
```

每层解决上一层的瓶颈：工具调用解决"需要能力"，AgentTool 解决"需要隔离"，Fork 解决"需要速度"，Coordinator 解决"需要分解"，Swarm 解决"需要弹性"。

**与数据库的类比**：Coordinator ≈ 分布式查询中的 Coordinator 节点（如 Presto Coordinator）。它将查询分解为子任务，分发到 Worker 节点，收集结果，合并返回。Swarm ≈ 动态扩缩容的 Worker 池——类似云数据库的 serverless 实例，按需增删。
