# 第 7 章 权限系统：自主性与安全性的连续谱

> Agent 的自主性与安全性是一对永恒的矛盾。完全自主意味着任何操作都能执行，完全安全意味着需要人工确认每步操作。Claude Code 的权限系统在这两个极端之间构建了一条连续谱，让用户根据自己的风险偏好选择位置。

---

## 7.1 权限模式谱系：从完全确认到完全自主

```
bypassPermissions  →  acceptEdits  →  default  →  plan
─────────────────────────────────────────────────────
   完全自主              接受编辑        默认询问      只读规划
```

| 模式 | 文件写入 | Bash 命令 | 网络访问 | 其他工具 |
|------|---------|----------|---------|---------|
| `default` | 每次询问 | 每次询问 | 询问 | 询问 |
| `acceptEdits` | 自动允许 | 询问 | 询问 | 询问 |
| `bypassPermissions` | 自动允许 | 自动允许 | 自动允许 | 自动允许 |
| `plan` | 禁止 | 禁止 | 禁止 | 只读 |

### 为什么是连续谱而非二元开关？

如果只有"安全/自主"两个极端，每个用户都不得不在"太烦人"和"太危险"之间二选一。`acceptEdits` 这个中间档位解决了一个具体痛点：大多数用户信任 Agent 修改文件，但不信任它执行任意 shell 命令。通过提供连续谱，用户可以在安全性和便利性之间找到自己的最佳位置。

---

## 7.2 规则引擎：alwaysAllow / alwaysDeny / alwaysAsk

在权限模式之上，用户可以通过 `settings.json` 定义精确的规则：

```json
{
  "permissions": {
    "allow": [
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(npm test:*)",
      "Read(/Users/lism/work/*)"
    ],
    "deny": [
      "Bash(rm:*)",
      "Bash(sudo:*)",
      "Bash(curl:*)",
      "Write(/etc/*)"
    ]
  }
}
```

### 规则匹配

规则使用 `toolName(parameter:pattern)` 格式，`*` 是通配符。规则匹配遵循精确优先原则：

```
Bash(git diff:*)     → 允许所有 git diff 命令
Bash(rm -rf:*)       → 拒绝所有 rm -rf 命令
Read(/home/*)        → 允许读取 /home 下的所有文件
Write(/etc/*)        → 拒绝写入 /etc 目录
```

规则引擎在每次工具调用前运行——它是权限检查的第一层，最快、最可预测。

---

## 7.3 自动分类器：Haiku 对 Bash 命令的安全分类

当规则引擎没有匹配时，`bashClassifier.ts` 使用小的 Haiku 模型自动判断 Bash 命令的安全性：

```
规则引擎未匹配 → 分类器判断
  ├── safe → 自动允许（如果权限模式允许）
  ├── unsafe → 交互式确认
  └── unknown → 交互式确认
```

为什么用 Haiku 而非 Opus？因为速度——需要 < 200ms 的分类才能不影响用户体验。Haiku 对于"判断命令安全性"这个狭窄任务足够胜任，同时足够快。

---

## 7.4 Hook 扩展：PreToolUse / PostToolUse 的 shell 脚本接口

Hooks 是权限系统的可编程扩展。每个 hook 是一个 shell 脚本，通过 JSON 协议与 Claude Code 交互：

```
PreToolUse 钩子：
  input:  { tool_name, tool_input, ... }
  output: { decision: 'allow'|'deny'|'ask', reason?: string }

PostToolUse 钩子：
  input:  { tool_name, tool_input, tool_output, ... }
  output: { modified_output?: string, ... }
```

Hook 类比于 Linux 的 LSM（Linux Security Modules）——它们是可插拔的安全策略，在代码路径的核心位置注入策略检查点。

---

## 7.5 交互式决策：权限弹窗

当规则引擎和分类器都无法自动决策时，系统会弹出交互式权限弹窗：

```
┌─────────────────────────────────────┐
│ Claude wants to run:                │
│                                     │
│   git push origin main              │
│                                     │
│ [Allow] [Deny] [Always Allow]      │
└─────────────────────────────────────┘
```

用户可以选择：
- **Allow**：本次允许
- **Deny**：本次拒绝
- **Always Allow**：永久允许（相当于动态添加规则）

"Always Allow"会自动写入 session 级别的权限缓存，不会修改 `settings.json`——这防止了 Agent 自身通过权限弹窗修改配置的风险。

---

## 7.6 拒绝追踪：连续拒绝后的降级策略

权限系统追踪连续拒绝的次数：

```typescript
// denialTracking.ts (概念)
if (consecutiveDenials > THRESHOLD) {
  // 降级策略：
  // 1. 建议用户切换到更开放的权限模式
  // 2. 建议用户添加规则来减少摩擦
  // 3. 不再尝试类似操作
}
```

连续拒绝是一个重要信号——它意味着 Agent 的策略与用户的期望不一致。降级策略的目的是打破这个循环：而不是让 Agent 不断被拒绝、不断重试。

---

## 7.7 文件系统权限：路径验证

文件系统的权限检查有额外的安全层：

- **工作目录限制**：默认只能访问项目根目录内的文件
- **scratchpad 目录**：Session 级临时目录，自由读写，不需要权限
- **安全关键路径**：`/etc`、`~/.ssh` 等有额外保护

scratchpad 目录是一个聪明的设计——它给了 Agent 一个"沙盒"。Agent 可以在这里自由创建和修改文件，而不会污染用户的项目。

---

## 本章小结

权限系统是一个多层次的**自主性梯度**：

```
静态规则（settings.json）
  → 自动分类器（Haiku 模型）
  → 交互式弹窗（用户决策）
  → Hook 脚本（自定义策略）
```

每一层都是独立可插拔的，用户可以选择性地启用。这种设计反映了 LLM Agent 安全的一个核心理念：**安全性不应该被定义为"低自主性"，而应该被定义为"可控的自主性"**。
