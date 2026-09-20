# DayLog v0.1：构建、运行与实现状态

更新于 2026-09-20。当前交付是 SwiftUI 原生 macOS 应用“刻白”：保留 C3 的窄导航、分组任务与可调详情区，改用晴白主题（清透蓝、暖白、浅杏色），支持系统深浅色。工程名和数据目录仍为 DayLog。见 [品牌与主题实现](kebai-daylight-theme.md)。

## 在当前 Mac 运行

在项目目录执行：

```bash
./scripts/run.sh
```

脚本使用 SwiftPM 构建 release，生成并 ad-hoc 签名 `build/DayLog.app`，然后启动。可直接双击生成的应用。当前是本机开发版本，没有 Developer ID、公证或 App Sandbox，不能当作公开分发版本。

只构建：`./scripts/build-app.sh`。开发时：`./scripts/build-app.sh debug`。不要用 `swift run DayLog` 替代完整应用：通知、菜单栏和登录项应在有 Bundle ID 的 `.app` 中验证。

当前机器：Apple M4 / 16 GB，macOS 26.3.2，Xcode 26.6（17F113），Swift 6.3.3。系统 `xcode-select` 仍指向 CLT，`./scripts/xcode.sh` 可自动选择本机唯一的完整 Xcode。原 SwiftPM 入口继续可用。部署下限为 macOS 14，旧系统尚未实机验证。

原生工程与调试方式见 [Xcode 开发入口](xcode-development.md)：打开 `DayLog.xcodeproj`，⌘R 运行内存演示版；正式数据仍使用原日常入口。

## 使用方式

- 今天：添加任务，选择任务后编辑标题、说明、状态、安排、步骤；标题和说明停笔 650 ms 自动保存。
- 今日重点、随记、进展和个人日记使用明确的保存按钮；未提交输入在页面切换时保留，退出时提示。
- 底栏“未保存内容”列出具体输入，可前往定位或逐项保存；Cmd+S 一次保存全部。提醒时间和例外日期草稿切页保留。全部保存先校验，任何一项无效都不部分提交。
- 完成任务后可以撤销，保留之后的标题、说明和步骤编辑；撤销作用于最近一次状态操作。步骤完成不会自动把任务标记完成。
- 跨日后，未完成任务进入“待安排”，按需加入今天。历史保留关日快照。
- 菜单栏提供快捷新增、完成和打开主窗口；关闭主窗口不退出进程。
- AI 回顾选择今天或近 7 个自然日，生成后可编辑、保存、采纳到工作记录；个人日记不会进入模型，也不会因其未保存草稿阻塞回顾。相关工作输入需先提交。
- 回顾默认显示 Markdown 阅读态，支持标题、列表、强调和代码；可切换编辑。采纳后长内容默认折叠，点击“展开完整回顾”查看。
- 有未提交输入时，导出明确选择“保存全部并导出”或“仅导出已提交内容”；后者保留草稿，并提示遗漏数量。保存全部也会提交私人日记，回顾文字仅保存草稿，不自动采纳。
- 设置页读取或导入模型配置、测试连接、设置工作周/调休/提醒、导出 Markdown 或完整 JSON、恢复备份。
- 登录启动默认关闭；通知默认关闭。用户开启后由系统处理授权。

## 实际代码结构

| 位置 | 当前职责 |
| --- | --- |
| `Package.swift` | DayLogCore 库、DayLog App、DayLogChecks 可执行检查 |
| `DayLog/Core/Domain.swift` | Codable 领域模型、跨日归档、版本检查、回顾输入与幂等采纳、备份校验 |
| `DayLog/Core/ReminderSchedule.swift` | 纯函数工作日和日期例外排期 |
| `DayLog/Core/LLM.swift` | Dotenv、配置校验、HTTPS Chat Completions、超时、取消和错误脱敏 |
| `DayLog/App/AppStore.swift` | MainActor 共享状态、编辑缓冲、保存事务、模型请求生命周期、备份恢复 |
| `DayLog/App/Drafts.swift` | 草稿清单、来源过滤、定位、原子批量提交与不可变导出快照 |
| `DayLog/Core/ReviewMarkdown.swift` | 轻量 Markdown 分块与安全行内格式 |
| `DayLog/App/DayLogApp.swift` | Window、MenuBarExtra、Settings、通知回调、跨日/唤醒协调 |
| `DayLog/Features/` | 今日/任务详情/AI 回顾/历史/个人日记/设置的 SwiftUI 页面 |
| `DayLog/Services/LocalStore.swift` | Core Data + SQLite 原子文档存储 |
| `DayLog/Services/ConfigStore.swift` | 完整配置 profile 的 Keychain 读写 |
| `DayLog/Services/ReminderService.swift` | 串行通知协调，替换未来 14 天的本应用请求 |

### 与前期技术设计的差异

实测 CLT SDK 提供 SwiftData 接口，但缺少 `SwiftDataMacros.PersistentModelMacro` 插件；`@Model` 编译失败。因此首版改用 Core Data 的程序化模型，无需 `.xcdatamodeld` 或 Xcode 宏插件。UI 和纯 Swift 领域模型不依赖该选择。

数据库不是每个业务类型一张实体表，而是一个 WorkspaceDocument：唯一 key + 版本化 JSON payload。AppStore.commit 在主线程接受领域修改并提交不可变快照；SaveQueue 防抖合并，LocalStore actor 在后台校验、编码、写入。UI 根据实际落盘进度显示保存中/已保存/失败。失败保留可见修改供重试或导出，正常退出等待落盘；不把进入内存当成已经持久化。

详见 [高优先级修复与回归](persistence-fix-2026-09-18.md)。仍是完整文档写入，长期增量存储优化后续进行。

模型与服务首版集中在少量文件，没有照设计稿预先拆出全部 Service/Provider 类型。使用一个实测通过的 Chat Completions 客户端；AppStore 支持测试注入生成器以验证输入边界，没有面向用户的 MockProvider、多协议选择或自动重试。

### 数据位置与恢复

- 日记：`~/Library/Application Support/DayLog/DayLog.sqlite`，由 Core Data 管理 WAL 文件。
- 恢复前自动备份：同目录下 `Backups/before-restore-<UUID>.json`。
- 界面外观：应用 UserDefaults。
- 导入的完整模型配置：Keychain，service `app.daylog.llm`。不进入数据库或导出备份。

JSON 备份包含私人日记；Markdown 只导出工作日记。本地数据库已移除误用的 50 MB 读取限制；外部备份文件导入仍限制 50 MB。恢复校验版本、ID、引用、日期边界、任务与提醒配置，确认后才替换，替换前保存当前 JSON。schemaVersion 为 1；未来版本需要明确迁移，目前未知版本拒绝恢复。

## 验证

```bash
./scripts/check.sh          # 无网络：领域、持久化、工作流检查 + 跨进程 SQLite 恢复
./scripts/check.sh --llm    # 额外读取现有配置，发送固定 Reply OK，不发送日记
```

原 CLT 工作流使用遇错非零退出的可执行检查。新增 `./scripts/xcode.sh test` 在完整 Xcode 上复用同一套断言，已实际通过 `xcodebuild test`；跨进程 SQLite 检查仍由原脚本覆盖。检查覆盖午夜快照、状态撤销基础、版本冲突、计划去重、日记上下文隔离、回顾幂等与过期、JSON 关联校验、dotenv、工作日例外、DST，以及普通/超过 50 MB 工作空间的跨进程 SQLite 恢复、20 项保存队列/失败/退出检查、30 项撤销与回顾范围检查，以及 31 项统一草稿、导出范围和 Markdown 阅读检查。见 [中等优先级修复](workflow-fix-2026-09-18.md)。

UI 验证可使用内存演示模式：先退出正常实例，再执行：

```bash
open build/DayLog.app --args --demo
```

演示模式使用虚构任务、内存存储，重新启动就重置；不会给真实日记写入测试任务。演示模式中手动“重新读取”配置后可以测试真实模型，发送的仍是演示内容。外观偏好与正常应用共用，模型导入等设置也仍是实际系统操作。

## 尚待验证和后续工作

- 本轮不自动开启通知或登录项；系统通知交付、点击冷启动、跨睡眠与长期 14 天补排需要授权后的实际运行验证。
- Keychain 导入和移除已实现，未用真实密钥反复写入测试；沙盒签名、沙盒导入权限未验收。
- 当前只自动提交任务标题/说明；其余明确提交。后台落盘有状态提示，正常退出等待落盘；强制终止时未提交草稿和尚未落盘的修改仍可能丢失。
- 无全局快捷键；当前提供应用内 Cmd+N、Cmd+S。无任务自动拆分和任务删除流程。
- AI 为自由文本草稿，提示模型用任务标题和记录日期标注来源，但未提供结构化引用校验/跳转。事实须用户核对，来源变更后禁止采纳。
- 近 7 天只汇总已有记录；长历史上下文尚未分块或预算裁剪。
- 普通中文文本输入已验证；真实拼音输入法组词、VoiceOver、所有窗口尺寸与旧版 macOS 仍需专门验收。
- Xcode 已接入构建、XCTest 和 Preview；Instruments 本轮采样状态见 [Xcode 开发与验收](xcode-development.md)。正式签名/公证和自动 UI 测试仍未完成。

已完成：19 项核心检查、非法保存保护、两个独立进程的 SQLite 恢复、固定提示真实连接，以及原生 UI 中演示数据的生成/编辑/采纳。深浅色、中文文本新增、标题修改、完成/撤销、个人日记、历史浏览、关窗后 Cmd+N 重开已检查。

本轮草稿与阅读修复详情、原生截图和验证边界见 [修复报告](draft-fixes-2026-09-18.md)。

构建通过或 API 测试通过不能替代剩余运行验收。
