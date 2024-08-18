# 第12章：TUI 渲染引擎——终端中的 GUI

> 源码版本：2026-05-04
> 关键文件：`tui/src/app.rs`, `tui/src/chatwidget.rs`, `tui/src/markdown_render.rs`, `tui/src/streaming/`, `tui/src/bottom_pane/`, `tui/src/tui/`

---

## 12.1 TUI 的架构全景

Codex 的 TUI（Terminal User Interface）不是简单的命令行输出，而是一个完整的终端 GUI 框架，基于 ratatui（Rust 的 TUI 库）构建。代码分布在 `tui/src/` 下的 150+ 源文件中，组织为三个核心层次：

```
┌─────────────────────────────────────┐
│          App (app.rs)              │
│   顶层状态机 + 事件分发中枢         │
├─────────────────────────────────────┤
│         ChatWidget                  │
│   主对话区域的复杂 Widget 组合       │
│   ├─→ 消息渲染 (markdown_render)   │
│   ├─→ 流式输出 (streaming/)        │
│   ├─→ 子组件 (side, skills...)    │
│   └─→ 中断/交互处理               │
├─────────────────────────────────────┤
│         BottomPane                  │
│   底部交互区的控制面板              │
│   ├─→ chat_composer (输入框)       │
│   ├─→ approval_overlay (审批弹窗)  │
│   ├─→ selection_popup (选择器)     │
│   └─→ footer (状态栏)             │
└─────────────────────────────────────┘
│                                     │
│   基础设施层：                       │
│   frames.rs (帧缓冲区管理)          │
│   tui.rs (事件流 + 帧率控制)        │
│   markdown.rs (Markdown → 终端行)   │
│   keymap.rs (按键绑定系统)          │
│   streaming/ (流式输出协调)         │
└─────────────────────────────────────┘
```

---

## 12.2 App：顶层状态机

```rust
// tui/src/app.rs
impl App {
    pub async fn run(&mut self) -> AppExitInfo {
        loop {
            // 1. 拉取 TUI 事件（键盘、鼠标、粘贴、终端 resize）
            let event = self.tui.next().await;

            // 2. 排空 App Server 消息 channel
            while let Ok(event) = self.app_server_rx.try_recv() {
                // 处理后台的模型响应、审批请求、通知等
            }

            // 3. 事件分发 → 状态更新
            self.dispatch_event(event);

            // 4. 渲染到终端缓冲区
            self.draw_frame(&mut terminal)?;
        }
    }
}
```

事件循环遵循经典的"事件 → 更新状态 → 渲染"模式。关键要点：

- **两个事件源**：TUI 本地事件（按键/鼠标/paste/resize）和 App Server 远程事件（模型响应/审批请求），通过 `try_recv` 非阻塞消费
- **帧率控制**：`frame_rate_limiter.rs` 限制渲染频率（~30-60fps），不是每个 TextDelta 都触发重绘
- **job_control**：通过 `JobControl` 管理 SIGTSTP（Ctrl-Z 挂起）等 Unix 作业控制信号

### AppEvent：TUI 的所有本地事件

```rust
// tui/src/app_event.rs
pub enum AppEvent {
    ChatMsg(String),                      // 用户提交文本
    Interrupt,                            // 用户中断（Ctrl-C/Esc）
    Approve { ... },                      // 审批操作
    Reject { ... },                       // 拒绝操作
    Command(AppCommand),                  // 命令模式操作
    Resize { width, height },             // 终端大小变化
    Paste(String),                        // 粘贴文本
    // ...
}
```

---

## 12.3 ChatWidget：核心显示区

`ChatWidget` 是主对话区域的视图层，负责：

1. **消息历史渲染**：将 `HistoryCell` 列表渲染为可滚动的对话流
2. **流式文本显示**：接收 SSE TextDelta 事件，实时追加到正在显示的消息中
3. **交互组件集成**：side panel、skills 面板、goal menu、plan mode 显示等

### HistoryCell：历史消息的单元

```rust
// tui/src/history_cell.rs
pub struct HistoryCell {
    // 封装了一条消息的完整渲染状态
    // 包括文本内容、渲染高度、折叠状态等
}
```

`HistoryCell` 是 TUI 渲染的核心抽象。每条消息（用户消息、assistant 消息、tool call 结果）都被展开为一个 `HistoryCell`，其中包含了该消息渲染所需的所有信息——文本内容（已格式化的）、渲染行数、是否被折叠、是否包含 diff 等。

### 流式输出的协调

```rust
// tui/src/streaming/controller.rs
// StreamingController 管理流式输出的生命周期：
// - 接收 TextDelta → 追加到渲染缓冲区
// - 合并相邻 TextDelta（减少渲染次数）
// - 控制 commit_tick（提交到持久化层的频率）
```

三个流式组件：
- **chunking.rs**：将连续的 TextDelta 分块，控制每块的粒度
- **commit_tick.rs**：定期触发 "commit"（将已渲染文本持久化），不是每个字符都存盘
- **controller.rs**：协调上述两者的调度

---

## 12.4 Markdown 渲染：从 Markdown 到终端行

```rust
// tui/src/markdown_render.rs
// tui/src/markdown.rs
// tui/src/markdown_stream.rs
```

这是 TUI 中最复杂的渲染子系统。它将 LLM 输出的 Markdown 格式文本转换为终端的 ANSI 转义序列：

```
Markdown 输入              终端渲染
─────────────────────────────────────────
# Heading 1          →  粗体 + 下划线（256色高亮）
**bold text**        →  ANSI Bold 序列
`inline code`        →  反色背景高亮
```code block```     →  独立区域 + 语法高亮
- list item          →  "  • list item"
1. numbered          →  "  1. numbered"
[link](url)          →  带颜色的文本（终端无超链接）
```

关键实现点在 `markdown_render.rs`：
- 使用 pulldown-cmark 解析 Markdown AST
- 递归遍历 AST 节点，为每种节点类型生成对应的 ANSI 格式化文本
- 处理代码块的语法高亮（通过 `render/highlight.rs`）
- 处理长行换行（`line_truncation.rs` / `wrapping.rs`）

### 流式 Markdown 的特殊处理

```rust
// tui/src/markdown_stream.rs
// 流式 Markdown 渲染器：处理"不完整"的 Markdown
// 例如：```code 块开了但还没关闭，必须缓存并等待闭合
```

流式 Markdown 是比静态 Markdown 更难的问题——渲染器收到的不是完整文档，而是增量片段。解析器必须处理：
- 未闭合的代码块（缓存到闭合标签出现）
- 被截断的格式标记（如 `**bold` 只有一半）
- 表格的逐行到来

---

## 12.5 BottomPane：控制面板

`bottom_pane/` 目录包含所有底部交互组件，形成一个"控制面板"：

### ChatComposer：输入框

```rust
// tui/src/bottom_pane/chat_composer.rs
// 多行文本编辑器，支持：
// - @mention 语法（@plugin, @tool, @skill）
// - Bracketed Paste 处理
// - 文件路径拖放
// - 历史搜索
// - Ctrl-R 反向搜索
```

输入框实现了完整的文本编辑功能：光标移动、选择、删除、undo/redo。`@` 触发 `mention_codec.rs` 解析，弹出来源选择器（MCP servers/tools/skills/files）。

### ApprovalOverlay：审批弹窗

```rust
// tui/src/bottom_pane/approval_overlay.rs
// 当 Agent 请求执行需要审批的操作时，
// 弹出覆盖层显示操作详情，等待用户输入
```

审批弹窗是模态的——它覆盖在输入区域上方，用户必须做出决定（批准/拒绝/始终批准此类型）后才能继续。

### 其他关键组件

- **file_search_popup.rs**：文件搜索弹窗（模糊匹配）
- **skill_popup.rs**：Skill 选择器
- **selection_popup.rs**：通用列表选择器
- **footer.rs**：底部状态栏（显示当前模型、token 使用、Agent 状态）

---

## 12.6 帧渲染管线

```
1. App 状态更新完成
   │
2. draw_frame() 被调用
   │
3. ratatui::Terminal::draw(|frame| {
   │   // 在 frame 闭包内：
   │   ├─→ chatwidget.render(frame, area_top)
   │   │     ├─→ 遍历可见的 HistoryCell
   │   │     ├─→ 滚动到最新消息
   │   │     └─→ 渲染流式文本的最后一帧
   │   │
   │   └─→ bottom_pane.render(frame, area_bottom)
   │         ├─→ 渲染输入框（或审批弹窗覆盖）
   │         └─→ 渲染状态栏
   })
   │
4. ratatui 将缓冲区 diff 到 stdout
   │
5. 终端 ANSI 序列写入 → 屏幕更新
```

关键优化：ratatui 内部维护一个"屏幕状态缓冲区"，只输出变化的部分（类似于 React 的 Virtual DOM diff）。

---

## 12.7 终端能力探测与适配

```rust
// tui/src/terminal_probe.rs
// 启动时探测终端能力：
// - 是否支持 true color（24-bit）？
// - 是否支持 kitty keyboard protocol？
// - 是否支持 bracketed paste？
// - 是否支持 OSC 9（桌面通知）？
// - 终端尺寸是多少？
```

`terminal_probe.rs` 在启动时运行，探测结果决定后续渲染策略——例如不支持 true color 时回退到 256 色调色板。

---

## 12.8 类比：GUI 框架

| GUI 框架概念 | Codex TUI |
|-------------|----------|
| Component / Widget | ChatWidget, BottomPane |
| Event Loop | App::run() — crossterm 事件流 |
| Render / Paint | draw_frame → ratatui::Frame |
| Style Sheet | style.rs, theme_picker.rs |
| List Virtualization | HistoryCell 可见性计算（只渲染可视区） |
| Modal Dialog | ApprovalOverlay 覆盖层 |
| Input Method | ChatComposer + keymap 系统 |
| Resize / Layout | resize_reflow.rs + layout constraints |

---

## 12.9 本章要点

1. **TUI 是三层的 GUI 框架**：App（状态机）→ ChatWidget / BottomPane（视图组件）→ ratatui（渲染引擎）。
2. **双事件源**：crossterm 本地事件 + App Server 消息 channel，通过 try_recv 非阻塞消费。
3. **帧率控制**：不是每个 TextDelta 都渲染，frame_rate_limiter 限制在 30-60fps。
4. **Markdown 渲染是最复杂的子系统**：pulldown-cmark 解析 → ANSI 格式化 → 流式未闭合标签的特殊处理。
5. **ChatComposer 是完整的文本编辑器**：支持 @mention、历史搜索、bracketed paste。
6. **渲染管线**：状态更新 → draw_frame → ratatui diff → stdout ANSI。
7. **终端能力探测**：启动时检测 true color / kitty / paste 等特性，决定渲染策略。
