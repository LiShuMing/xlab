# DayLog：Mac 工作日记应用设计

状态：初始方案归档；2026-09-18 完成环境检查。尚未创建应用工程、安装软件或修改系统设置。最新 UI 以 [UI 规范](ui-spec.md) 为准；用户已选择简约、现代、苹果原生风格。

## 1. 产品定位

一个随时可用、安静陪伴的工作日记：先记下今天要做的事，随手更新进展，下班时形成可回顾的记录。

暂名 DayLog（中文名待定）。首版面向当前 Mac mini 单机使用，以中文界面、键盘输入、本地保存为默认。不要求登录，不部署后端。

“轻量”意味着启动快、常驻时低消耗、输入路径短；“智能”意味着基于真实记录提供草稿；“有趣”通过微动效和友好反馈表达。

## 2. 使用路径和 UI

### 菜单栏：随手记录

默认常驻菜单栏，显示一个小图标，可选显示今日完成数量。点击打开约 360 × 460 pt 的面板：

```text
┌──────────────────────────────────┐
│ ☀ 今天 · 9 月 18 日       2 / 5   │
│ [＋ 写下接下来要做的事…          ] │
│                                  │
│ ○ 分析查询回归             进行中 │
│ ○ 整理设计文档                   │
│ ✓ 完成 Code Review               │
│                                  │
│ [随手记]          [打开工作日记]  │
└──────────────────────────────────┘
```

回车新增；点击圆圈完成/撤销；点击标题编辑；详细备注在工作日记页编辑。面板打开后自动聚焦输入框。全局快捷键放在后续增强，首版使用菜单栏和应用内快捷键。

### 主窗口：今天、历史、设置

建议初始大小约 960 × 680 pt，窄窗口自动收起侧栏。

```text
┌──────────┬─────────────────────────────────────────────┐
│ 今天     │ 9 月 18 日 · 星期五               已保存    │
│ 历史     │ 今天最重要的一件事：[____________________] │
│          │                                             │
│          │ 今日 TODO                       [＋ 添加]   │
│          │ ○ 分析查询回归                 [补充进展]  │
│          │ ✓ 完成 Code Review                          │
│          │                                             │
│          │ 工作随记                                    │
│          │ 14:20 找到一个值得验证的方向……              │
│          │                                             │
│ 设置     │ [生成今日回顾]              [导出 Markdown] │
└──────────┴─────────────────────────────────────────────┘
```

主窗口与菜单栏共享同一数据源，修改即时同步。关闭主窗口后保留菜单栏；“退出应用”是独立操作。首版保留标准 Dock 行为，菜单栏独占模式后续再调整。

UI 使用系统字体、SF Symbols、浅色/深色模式、留白和单一强调色。完成任务时有可关闭的轻微动画，可用小叶子变化表达今日进展；尊重“减少动态效果”，不加入连续打卡惩罚、排行榜或持续动画。

### 日记与历史

工作随记属于每天的工作页；个人日记作为可选、单独分类的记录，在同一历史入口查看。历史按日期浏览和关键词搜索。个人日记默认不参与工作总结。

未完成任务次日显示在“待安排”区，由用户选择加入今天；不自动修改过去的计划。历史页同时区分“当日状态”和“当前状态”。

## 3. 提醒设计

建议默认时间：09:30 规划今天、18:00 回顾今天；时间和工作周均可配置，首次开启提醒时才申请通知权限。

- 默认周一至周五；提供日期例外，支持休假和调休工作日。首版不自动获取中国节假日日历。
- 支持稍后提醒、跳过今天；任务级提醒为可选能力。
- 使用系统本地通知，点击进入对应日期或任务。完成、取消、改期后撤销或重排相关通知。
- 通知默认只显示“该整理今天的工作了”，用户可选择显示任务内容。
- 通知受系统授权、专注模式和睡眠影响，不承诺精确唤醒电脑。拒绝权限时应用内显示提醒状态。
- 应用启动、唤醒和日期变化时重新核对提醒；过去的提醒合并成一次提示，避免补发风暴。
- 一般工作周可预排重复通知；带日期例外的规则预排有限未来窗口，显示已排期到哪天。应用长期未运行时，窗口后的自定义排期不能保证。

## 4. 技术方案

基线：Swift 6 语言模式，SwiftUI 原生 macOS App，最低 macOS 14；Apple Foundation Models 功能在 macOS 26+ 单独进行可用性检查。

| 层次 | 选择 | 职责 |
| --- | --- | --- |
| 界面 | SwiftUI、MenuBarExtra、Window、Settings | 菜单栏、今日工作页、历史与偏好设置 |
| 应用状态 | Observation、@MainActor | 当前日期、编辑状态、多窗口一致性 |
| 数据 | SwiftData，本地持久化 | TODO、日记、变更记录、总结草稿 |
| 系统服务 | UserNotifications、ServiceManagement | 本地提醒、可选登录启动 |
| LLM | 自定义 LLMProvider 协议、async/await | 隔离不同模型接口，支持取消和超时 |
| 密钥 | Keychain | 保存用户配置的服务凭据 |
| 导出 | Foundation、系统保存面板 | Markdown 阅读副本、JSON 可恢复备份 |

这些都是建议的模块职责，尚无已实现的类或文件。原生菜单栏面板可使用 [MenuBarExtra 的 window 样式](https://developer.apple.com/documentation/swiftui/menubarextra)。SwiftData 提供与 SwiftUI 集成的本地持久化能力，见 [Apple 持久化文档](https://developer.apple.com/documentation/swiftdata/preserving-your-apps-model-data-across-launches)。

依赖方向：View → 应用服务 → 数据存储/通知/模型适配器。首版不引入第三方架构框架、网络服务、向量数据库或嵌入式 Python。

建议后续工程结构：

```text
DayLog.xcodeproj
DayLog/
  App/
  Features/{Today,History,Journal,Settings}/
  Models/
  Services/{Persistence,Reminders,LLM,Export}/
  Resources/
DayLogTests/
DayLogUITests/
```

## 5. 数据语义：工作日记不只是任务列表

| 模型 | 核心字段与用途 |
| --- | --- |
| WorkDay | UUID、localDate、timeZoneID、focus；保存一天的归属 |
| TodoItem | UUID、title、notes、status、createdAt、updatedAt、completedAt |
| DailyPlanItem | WorkDay 与 TodoItem 的关联、排序、当日结束状态；同一任务可跨天计划 |
| TaskEvent | taskID、occurredAt、事件类型、修改前后值；保留新增、改名、状态和改期历史 |
| JournalEntry | UUID、日期归属、work/personal 分类、正文、创建/更新时间 |
| SummaryDraft | 日期范围、来源 ID、来源修订信息、模型标识、内容、生成时间、用户采纳状态 |

任务更新和对应事件在同一个保存操作中提交。保留当日计划快照及变更事件，避免今天完成某任务后，昨天的页面也显示成“昨天已完成”。跨日未运行时，在下次启动根据事件时间补齐历史状态。

事件时间保存为绝对时间；日期归属保存日历日期和记录时区。更换时区不重新划分旧日记。首版建议默认固定工作时区为 Asia/Shanghai，可在设置中修改未来记录的归属规则。

文本编辑短时防抖保存，失焦和正常退出时提交；勾选、移动任务等明确动作立即保存。显示“保存中/已保存/保存失败”，失败时保留编辑缓冲并允许重试。硬退出前尚未落盘的文字仍有丢失风险，应缩短保存窗口并实测。

数据库放在应用数据目录；启用 Sandbox 时位于应用容器内。用户日记、密钥和导出文件不放入源码仓库。JSON 备份包含 schemaVersion 和全部关系 ID；导入前校验、备份现有数据并明确重复 ID 的处理规则。Markdown 仅用于阅读，不能替代完整备份。

## 6. LLM：基于事实生成可编辑草稿

首批场景：生成今日回顾、最近一周总结、把模糊 TODO 拆成建议步骤。

处理流程：用户选择日期/任务 → 读取有限范围记录 → 构建带来源 ID 的输入 → 生成草稿 → 展示来源 → 用户编辑和采纳。

- 完成数量和任务状态由程序计算；模型负责表达和建议，不推断未记录的完成事实。
- 草稿区分“已记录事实”“建议下一步”。拆分出的任务逐项采纳后才写入数据库。
- 总结默认只读工作记录。选择云服务时，明确显示服务地址和本次发送的记录范围；个人日记需要单独选择。
- 提供生成中、取消、超时、离线、凭据无效等状态。生成失败不阻塞记录和提醒，不自动切换到云服务。
- 日记文本视为待处理内容，不作为可执行指令；模型没有修改或删除历史记录的工具权限。
- 长历史先按日期检索和分段总结，首版不做向量检索。数据更新后，既有总结标记“来源已变化”。

模型接入策略：先使用 MockProvider 验证交互，再选一个真实 Provider 打通。

| Provider | 优点 | 使用条件 |
| --- | --- | --- |
| Apple Foundation Models | 系统内置的本地推理接入 | 运行时检查 SystemLanguageModel.availability；受 Apple Intelligence 开启状态、地区与模型准备情况影响 |
| 用户指定的云端服务 | 应用无需自行加载模型 | 配置真实 endpoint、模型和凭据；接口差异由适配器处理 |
| Ollama | 可自行选择本地模型 | 后续按需安装并实测；16 GB 机器上与开发工具争用统一内存 |

优先验证 Apple 本地能力；若不可用，由用户选择配置云端或 Ollama，普通日记功能始终可用。不能仅凭 M4 硬件判定 Apple 模型可用，见 [SystemLanguageModel](https://developer.apple.com/documentation/foundationmodels/systemlanguagemodel)。首版无需下载本地大模型。

## 7. 当前环境检查与准备步骤

2026-09-18 本机观测：

| 项目 | 结果 | 含义 |
| --- | --- | --- |
| 硬件 | Mac mini、Apple M4、arm64、16 GB | 满足原生应用开发的基本硬件需要 |
| 系统 | macOS 26.3.2 | 支持本方案的 OS 基线 |
| 存储 | 当前卷约 375 GiB 可用 | 有足够空间准备开发工具 |
| Swift | Apple Swift 6.3.3 | 命令行编译器可用 |
| 当前 SDK | macOS SDK 26.5 | SDK 与实际运行系统版本不同，须设置 deployment target 并检查新 API availability |
| 开发目录 | /Library/Developer/CommandLineTools | 当前使用 CLT |
| xcodebuild | 失败，提示需要完整 Xcode | IDE 构建与 UI 测试链路尚未就绪 |
| Xcode 查找 | /Applications 常见路径和 Spotlight 未找到 | 不是全磁盘安装审计，但当前没有可用的 Xcode 配置 |
| Ollama | 当前 PATH 未发现 | 不阻塞首版 |
| 模型及通知权限 | 未验证 | 应用原型阶段做真实运行验证 |

本轮仅检查和文档落地，没有安装 Xcode、模型，也没有启用通知或登录启动。

后续准备顺序：

1. 从 Apple 官方下载与 macOS 26.3.2 兼容的正式版 Xcode。当前官方兼容表列出 Xcode 26.5/26.6 支持 macOS 26.2–26.x；安装时重新核对表格，不盲目选择最新版本。来源：[Xcode 系统要求](https://developer.apple.com/xcode/system-requirements)。
2. 首次启动 Xcode，完成许可及必要组件；只开发 Mac 应用时无需额外安装 iOS/visionOS 模拟器。
3. 优先通过进程级 DEVELOPER_DIR 使用 Xcode，暂不修改系统全局 xcode-select。
4. 创建 macOS App 工程，SwiftUI、Swift 6、deployment target macOS 14，确定稳定 Bundle ID。使用本机开发签名运行原型；对外分发的 Developer ID、公证或 App Store 配置另做。
5. 打通真实 .app 的菜单栏、主窗口、SwiftData 保存和通知测试，再加入登录启动。命令行 Swift 可用于纯逻辑试验，但不等于 .app 的系统集成验证完成。

安装到标准路径后的检查命令（本轮未执行）：

```bash
env DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -version
env DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift --version
env DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -showsdks
```

网络模型开启后配置 Sandbox 的出站网络能力；导出通过用户选择文件的位置。登录启动使用 [SMAppService.mainApp](https://developer.apple.com/documentation/servicemanagement/smappservice/mainapp)，由用户在设置页开启。提醒使用 [UserNotifications](https://developer.apple.com/documentation/usernotifications)。

## 8. 实现阶段与验收

以下为单人开发的粗略工作量，完成环境准备后计时，并非交付承诺。

| 阶段 | 预计 | 交付与验收 |
| --- | --- | --- |
| P0 环境和界面原型 | 0.5–1 天 | Xcode 可构建真实 .app；菜单栏能打开面板、输入和主窗口，深浅色可用 |
| P1 工作日记闭环 | 2–3 天 | 新增、修改、完成/撤销、历史、跨日待安排、随记；重启数据仍在，多窗口一致 |
| P2 提醒和数据可靠性 | 1–2 天 | 工作周/例外日期、拒绝权限降级、唤醒去重、导出及 JSON 恢复验证 |
| P3 智能整理 | 1–2 天 | 一个真实 Provider；日报、周报、任务拆解草稿；取消/离线不影响记录 |
| P4 个人日记和体验打磨 | 1–2 天 | 个人日记隔离、快捷键、轻动效、登录启动、性能测量 |

优先完成 P0–P2，得到无需 LLM 也能每天使用的产品。

关键测试：任务事件和历史状态不被跨日操作覆盖；周五到周一及休假/调休排期；时区变化；中文输入法组合输入；保存失败；导出导入后 ID 和关系完整；模型返回错误或不存在的来源 ID；通知点击路由。

性能目标（待测，非已实现数据）：不加载本地模型时，Release 版本冷启动约 1 秒内、菜单栏打开约 200 ms 内、空闲 CPU 接近 0%、常驻内存争取低于 100 MB。用 Instruments 和 Activity Monitor 在这台 Mac 上测量；模型服务占用需另计。

首版暂缓：iCloud 多端同步、团队协作、自动抓取屏幕/会议、日历双向同步、桌面宠物、后台主动代理。
