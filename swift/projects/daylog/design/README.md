# UI 评审与工具流程

## 交付物

**新增提案（2026-09-19）：`daylog-research-v1.html`。** 主题订阅与每日调研的局部增量，沿用 C / Graphite Studio。可从今日待阅入口进入简报、预览摘记或待办、创建订阅并演示试跑，也可查看无更新/失败期次。宿主设计控件可比较紧凑入口与摘要卡，以及部分覆盖、错过执行等状态。所有资料、连接和运行均为演示；不读取真实模型配置、不执行工具或创建后台任务。详见 [产品与实现设计](../docs/research-subscriptions-design.md)。本轮未作原生实现或浏览器自动化验收。

**当前版本：`daylog-studio-v3.html`。** 用户已选择 C 为基线；本轮增加任务分组、侧边编辑、步骤、进展关联和日级回顾。依据与范围见 [v0.3 迭代说明](../docs/studio-v3.md)。

以下 v0.2 稿件保留用于回看：

- `daylog-glass.html`：A · Liquid Glass 空间层次。
- `daylog-expressive.html`：B · Material 3 Expressive。
- `daylog-studio.html`：C · Graphite Studio。

比较与原生实现约束见 [视觉方向说明](../docs/design-directions.md)。三版均可操作，最终只实现选定方向。

`daylog-ui.html` 是可编辑的交互设计稿，使用演示任务和记录。可在 Codex 对话里查看与操作；页面内数据刷新后重置。

设计稿与实现的区别：设计稿是浏览器界面，用于比较布局和交互；最终应用用 SwiftUI 实现，不把该页面嵌入正式 App。

## 如何共同敲定

1. **方向比较**：使用设计调整面板切换“温暖纸感 / 原生极简 / 轻松活泼”，再切换浅深模式和舒展/紧凑密度。
2. **操作评审**：新增一项→勾选完成→修改标题/备注→记一笔→展开回顾→采纳。点击顶部 DayLog 查看菜单栏；点击侧栏看历史、日记和设置。
3. **定位反馈**：可使用当前宿主支持的批注能力，或直接说明页面、元素和期望，例如“今日页：把随记移到右侧”。宿主没有设计控件时，告诉我偏好的样式即可。
4. **记录决策**：更新 `docs/decisions.md` 和 `docs/ui-spec.md`，保留用户尚未确认的选项。
5. **原生校验**：用 Xcode + SwiftUI Preview 实现 TodayView、MenuBarView 和 TaskRow，再真机检查窗口、中文输入法、焦点、滚动和通知。

用户最初选择简约现代，随后要求更多方向并选定 C。当前在 C 上细化交互，不再重复要求选择 A/B/C。设计确认是对可见布局和交互的反馈，不要求你先学习设计工具。

## 工具选择

| 工具 | 这一阶段的作用 |
| --- | --- |
| Codex 内交互设计稿 + Tweak | 快速比较样式和操作，无需安装额外设计软件 |
| 浏览器预览 | 检查布局；必要时用 Computer Use 操作和截图 |
| Xcode + SwiftUI Preview | 后续验证原生控件、尺寸和系统行为 |
| Figma | 需要跨团队协作或长期组件库时再引入；本轮未连接或创建 Figma 文件 |
| 图片生成 | 后续可用于图标/插画探索，不替代可操作的界面设计稿 |

当前原型不用远程字体、外部图片和网络 API。设计调整通过宿主提供的 Tweak helper；缺少 helper 时默认版本仍能操作。示意图标由宿主提供，正式 SwiftUI 使用 SF Symbols。

如需独立浏览器预览，可使用当前环境已安装的 visualize 渲染脚本（此路径随插件升级可能变化）：

```bash
python3 /Users/shuming.lsm/.codex/plugins/cache/openai-bundled/visualize/1.0.32/skills/visualize/scripts/render.py \
  /Users/shuming.lsm/work/xlab/swift/projects/daylog/design/daylog-ui.html \
  /Users/shuming.lsm/work/xlab/swift/projects/daylog/design/daylog-preview.html
```

生成的 `daylog-preview.html` 是派生预览文件；源设计稿保持为 `daylog-ui.html`。普通浏览器没有 Codex 的设计调整/批注控件。

## 覆盖范围

已设计：今日、菜单栏、历史、个人日记、提醒设置、回顾草稿。原型不验证系统通知授权、真实持久化、模型质量、签名、快捷键注册、窗口拖动/缩放和应用性能。
