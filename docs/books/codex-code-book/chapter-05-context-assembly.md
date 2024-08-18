# 第5章：Context 装配——System Prompt 的构造艺术

> 源码版本：2026-05-04
> 关键文件：`core/src/context/mod.rs`, `core/src/context/*.rs`, `core/src/skills.rs`, `core/src/agents_md.rs`, `core/src/compact.rs`

---

## 5.1 Context 的本质：LLM 的"虚拟内存"

在操作系统里，虚拟内存给每个进程一个"拥有全部地址空间"的假象——实际物理内存由内核管理分页。Codex 的 Context 系统做的是同一件事：**给 LLM 一个"理解整个项目"的假象，实际只有精选的上下文被装入有限的 Token Budget。**

Context 装配就是 Codex 的分页系统：它决定"什么信息值得进入 LLM 的上下文窗口"。每一个 Token 都是稀缺资源（GPT-5 上下文窗口 ~400K tokens ≈ $2/满窗口），装配质量决定了 Agent 的输出质量。

---

## 5.2 Context 的 Fragment 架构

Context 被组织为 20+ 种 **Fragment**，每种 Fragment 是上下文的一个独立片段：

```
Context = 
    PersonalitySpecInstructions   // ★ "你是一个 AI 编程助手..."
  + PermissionsInstructions       // ★ "你有这些工具的权限..."
  + UserInstructions              // ★ CLAUDE.md / rules / 用户特定指令
  + AvailableSkillsInstructions  // "你可以触发这些 Skill..."
  + AvailablePluginsInstructions // "这些 Plugin 可用..."
  + CollaborationModeInstructions// "当前指定按合作模式工作..."
  + EnvironmentContext           // "你运行在 macOS, zsh, 当前目录..."
  + ModelSwitchInstructions      // "刚才发生了模型切换..."
  + AppsInstructions             // "这些 App 已注册..."
  + PluginInstructions           // "来自 Plugin 的指令..."
  + SkillInstructions            // "来自 Skill 的指令..."
  + RealtimeStartInstructions    // "实时语音已启动..."
  + ImageGenerationInstructions  // "图像生成规则..."
  + SubagentNotification         // "子 Agent 通知..."
  + GuardianFollowupReviewReminder // "安全审查提醒..."
  + HookAdditionalContext        // Hook 注入的额外上下文
  + UserShellCommand             // 用户 Shell 命令上下文
  + TurnAborted                  // 中断标记
  + ApprovedCommandPrefixSaved   // 已批准的指令前缀
  + NetworkRuleSaved             // 网络规则保存
  + ...
  + Conversation_History         // 之前的对话消息
```

每种 Fragment 实现 `Renderable` trait（或类似的渲染接口），产生文本内容注入到最终的系统提示词中。

### FragmentRegistration：动态注册与代理

```rust
// context/fragment.rs
pub(crate) struct FragmentRegistration { ... }
pub(crate) struct FragmentRegistrationProxy { ... }
```

Fragment 是**可动态注册**的。新的 Fragment 可以在运行时通过 `FragmentRegistrationProxy` 添加到上下文中。这意味着 Hook 或 Plugin 可以在 Session 中途注入额外的上下文指令。

---

## 5.3 CLAUDE.md / AGENTS.md 的加载机制

`UserInstructions` Fragment 负责加载"用户指令"文件。其核心逻辑：

```
加载优先级（从低到高）：
1. 全局 CLAUDE.md   — ~/.claude/CLAUDE.md
2. 全局 @规则文件     — ~/.claude/rules/*.md (如 RTK.md, work.md)
3. 项目 AGENTS.md    — <project>/.claude/AGENTS.md 或 <project>/AGENTS.md
4. 本地规则          — <project>/.claude/rules/*.md

优先级高的覆盖优先级低的（或追加在其后）
```

注意加载时机：指令不是在 Session 创建时一次性加载的，而是在每次 Turn 开始时重新加载——这样当用户编辑 CLAUDE.md 后，无需重启 Codex，下一次 Turn 就能看到更新。

如果你有 `cwd` 切换（`-C /path/to/project`），Codex 会重新加载新 cwd 下的 AGENTS.md。

---

## 5.4 Memory 系统：跨越会话的记忆

Memories 是 Codex 存储系统中的"跨会话知识"。它通过两个独立的 crate 实现：

```rust
// codex-memories-read/src/lib.rs  — 读取记忆
// codex-memories-write/src/lib.rs — 写入记忆
```

记忆分为：
- **会话级记忆**：属于特定 Thread
- **项目级记忆**：属于特定项目目录
- **用户级记忆**：属于用户（跨项目）

记忆内容在每次 Turn 开始时被注入到 Context 中。写入记忆的时机是：LLM 选择调用记忆写入工具（`memories/write`），Codex 将内容持久化到 SQLite 或文件系统。

### 记忆清理

```rust
// cli/src/main.rs:1129-1136 — `codex debug clear-memories`
// 清除 state_db 中的记忆 + 删除 CODEX_HOME 下的记忆目录
```

---

## 5.5 Skill 注入系统

Skill 是 Codex 最重要的扩展机制。Skill 注入的完整流程：

### Step 1: Skill 发现

```rust
// core/src/skills.rs
pub(crate) struct SkillsManager { ... }
pub(crate) struct SkillsLoadInput { ... }
pub(crate) struct SkillMetadata { ... }
```

Skill 文件（`.md`）分布在与 CLAUDE.md 相同的位置：
- `~/.claude/skills/` — 全局 Skill
- `<project>/.claude/skills/` — 项目 Skill
- `<plugin>/skills/` — Plugin 自带的 Skill

每个 Skill 文件有 frontmatter 元数据：

```markdown
---
name: my-skill
description: Short description of what this does
---
# Skill body content...
```

### Step 2: 元数据预算

```rust
// core/src/skills.rs
pub(crate) fn default_skill_metadata_budget(...) -> ...  // 默认展示多少 Skill 的元数据
```

在上下文窗口中，每个 Skill 只展示**元数据**（名称 + 描述），不展示 Skill 正文。正文只在 Skill 被触发时才注入。这就像一个"懒加载"设计——100 个 Skill 只占几百 Token 的描述空间。

### Step 3: 显式触发 vs 隐式触发

- **显式触发**：用户输入 `/my-skill`（最近代码中还出现了 `$SKILL_NAME` 语法）
- **隐式触发**：`maybe_emit_implicit_skill_invocation(skill_name, ...)` — 系统判断当前任务匹配某个 Skill

### Step 4: 依赖解析

```rust
// core/src/skills.rs
pub(crate) fn resolve_skill_dependencies_for_turn(...) -> ...
```

Skill 可以依赖其他 Skill。依赖在 Turn 开始前被解析，所有依赖的 Skill 正文被递归注入。

### Step 5: Skill 注入渲染

```rust
// core/src/skills.rs
pub(crate) fn build_skill_injections(...) -> SkillInjections { ... }
pub(crate) fn injection(...) -> ... // 实际注入到 Context
```

这产生的 `SkillInstructions` Fragment 包含当前 Turn 需要的所有 Skill 正文。

### Skill Watcher：文件变更热更新

```rust
// core/src/skills_watcher.rs
pub(crate) struct SkillsWatcher { ... }
pub(crate) enum SkillsWatcherEvent {
    SkillsChanged { ... },
}
```

当 Skill 文件在磁盘上被修改（通过 `notify` crate 监听），`SkillsWatcher` 发出 `SkillsChanged` 事件，触发 `skills_manager.clear_cache()`。下一次 Turn 将使用最新版本的 Skill。

---

## 5.6 权限指令生成

`PermissionsInstructions` Fragment 生成的是 LLM 用来调工具时的"安全手册"：

```rust
// context/permissions_instructions.rs
pub struct PermissionsInstructions { ... }
```

它根据 `SandboxPolicy` 和 `ApprovalPolicy` 生成：
- 哪些目录可读写
- 哪些命令需要用户批准
- 网络访问权限
- 审批策略模式（Always/Never/OnRequest）

生成的文本类似：
```
You are running with these permissions:
- Read access to: /Users/lism/work/codex
- Write access restricted by sandbox
- Network: allowed with restrictions
- Command approval: on-request
```

Context 中的 `ApprovedCommandPrefixSaved` 和 `NetworkRuleSaved` Fragment 记录了用户"记住"的权限决策，让 LLM 知道某些操作走快速通道。

---

## 5.7 Token 预算管理与 Context 压缩

### Compact：上下文的"GC"

当上下文接近 Token 预算上限时，Codex 触发 Compaction（压缩）：

```rust
// core/src/compact.rs
pub mod compact {
    pub fn content_items_to_text(...) -> ...  // 将结构化内容转为纯文本
    // Compact 核心逻辑
}
```

Compaction 的两种模式：

1. **本地 Compact**（`compact.rs`）：将早期的对话消息压缩为摘要文本
   - 保留最近的 N 轮完整内容
   - 将更早的对话压成一个简短的 summary
   - 类似于 GC 的"分代回收"——老数据被压缩，新数据保留

2. **远程 Compact**（`compact_remote.rs`）：通过 API 调用让 LLM 自己总结历史

```rust
// core/src/compact_remote.rs
// 使用 CompactionInput → API CompactClient → 返回压缩结果
```

### Thread Rollout Truncation：轮转截断

```rust
// core/src/thread_rollout_truncation.rs
pub(crate) mod thread_rollout_truncation { ... }
```

当 session rollout（jsonl 历史）超过一定长度，进行截断。这发生在持久化层面，而非 Context 层面——旧的 jsonl 事件被丢弃或归档。

---

## 5.8 类比 Query Engine 视角

作为 Query Engine 工程师，你会看到 Context 装配与查询优化（Query Optimization）的惊人相似：

| Query Optimizer | Codex Context System |
|----------------|---------------------|
| Cost-based Optimization | Token Budget Management |
| Predicate Pushdown | CLAUDE.md 多级覆盖（高优先级"覆盖"低优先级） |
| Column Pruning | Fragment 按需注入（Skill metadata vs Skill body） |
| Join Reorder | Fragment 注入顺序（重要的前置） |
| Subquery Materialization | Memory 系统（预计算的知识缓存） |
| Adaptive Query Execution | Skill Watcher（运行时发现变更并重优化） |

最有趣的对应：**Predicate Pushdown ≈ CLAUDE.md 多级覆盖**。在 SQL 里，Predicate Pushdown 把过滤条件推到离数据源最近的地方执行，减少中间结果。CLAUDE.md 的多级覆盖做同样的事——全局规则在"顶层"（用户级），项目规则在"下层"（项目级），项目规则覆盖（override）全局规则，从而"推"掉不需要的全局指令。

---

## 5.9 本章要点

1. **Context 是 LLM 的虚拟内存**：通过 Fragment 系统实现"按需装载"。
2. **20+ 种 Fragment** 组成了完整的系统提示词，每种 Fragment 是独立的渲染单元。
3. **CLAUDE.md/AGENTS.md 多级加载**：全局 → 项目 → 本地，高优先级覆盖低优先级。
4. **Memory 系统实现跨会话知识复用**：会话级/项目级/用户级三级记忆。
5. **Skill 注入五步**：发现 → 元数据预算 → 触发 → 依赖解析 → 注入渲染。
6. **Token 预算管理**：Compact（本地/远程压缩）+ Rollout Truncation（轮转截断）。
7. **Context 装配 ≈ 查询优化**：Token Budget = Cost Budget, CLAUDE.md 覆盖 = Predicate Pushdown, Memory = Materialized View。
