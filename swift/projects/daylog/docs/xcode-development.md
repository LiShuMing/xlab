# Xcode 开发入口

应用现名为“刻白”，工程与 Scheme 仍为 DayLog。已接入亮色图标、深浅主题和 `./scripts/xcode.sh render` 离屏验收入口，见 [晴白主题实现](kebai-daylight-theme.md)。

打开 `DayLog.xcodeproj`，选择 `DayLog` scheme 和 `My Mac`，⌘R 运行、⌘U 测试。
Debug 使用独立 Bundle ID `app.daylog.development`，强制内存演示模式；不读取真实日记或自动加载模型密钥。Release 使用正常持久化；不要同时运行多个正式版本写入同一数据库。

```bash
./scripts/xcode.sh open       # 在完整 Xcode 中打开工程
./scripts/xcode.sh run        # Debug 构建并运行内存演示版
./scripts/xcode.sh test       # XCTest 和 .xcresult
./scripts/xcode.sh release    # 只构建正式模式，不启动
```

脚本优先使用 `DEVELOPER_DIR`，其次使用 `xcode-select` 的配置；若仍指向 CLT 且 `/Applications` 只有一个 Xcode，则自动选择它。不需要 sudo 或修改全局工具链。存在多个版本时显式指定，例如：

```bash
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer ./scripts/xcode.sh test
```

`project.yml` 是工程配置源，按 [XcodeGen ProjectSpec](https://github.com/yonaskolb/XcodeGen/blob/master/Docs/ProjectSpec.md) 生成。已提供 `.xcodeproj`，日常运行不需要安装 XcodeGen；增加文件或改变 Target 后执行 `brew install xcodegen`（首次）和 `./scripts/xcode.sh generate`。不要只编辑生成的工程配置。

## 工程结构

- `DayLog`：原生 macOS App Target，包含 App、Features、Services 和仅 Xcode 编译的 Preview。
- `DayLogCore`：共享领域模型 framework，仍与 SwiftPM 使用同一份源码。
- `DayLogRegressionTests`：无 App 宿主的 XCTest Target，复用既有核心、保存队列、工作流和草稿检查；用临时 SQLite 或内存存储运行，不发送 LLM 请求。
- `DayLogPreviews/WorkspacePreviews.swift`：浅色/深色 Preview，使用隔离的演示数据。

XCTest 用可抛错的 suite 入口承接旧断言，失败会显示在对应测试方法下。原 `./scripts/check.sh` 仍保留 100 项断言及 4 项独立进程 SQLite 结果，后者覆盖普通和超过 50 MB 的数据恢复。

Debug 支持断点与变量检查；Profile 使用 Release 优化和 `--demo` 参数。开发签名为 ad-hoc，无需 Apple Developer 账号；公开分发签名、公证和系统通知/登录项的实机验收仍是独立工作。

完整 Xcode 安装不改变现有 Core Data/SQLite 格式，已有日记不需要迁移。

## 2026-09-20 本机验收

环境为 macOS 26.3.2、Xcode 26.6（17F113）、Swift 6.3.3，Apple Silicon。

| 检查 | 实测结果 |
| --- | --- |
| Xcode Debug 构建与 ⌘R | 成功；界面显示“演示模式 · 数据仅保存在内存” |
| Xcode Release 构建 | 成功，应用 Bundle 的 ad-hoc 签名校验通过 |
| `xcodebuild test` | 6 个测试方法通过，0 失败；复用 100 项旧断言，另检查演示数据隔离 |
| 原 `scripts/check.sh` | 100 项断言和 4 项跨进程 SQLite 结果通过，包括超过 50 MB 的数据 |
| 原生界面 | 新增任务、完整中文标题自动保存、完成和撤销通过；截图见下方 |
| SwiftUI Preview | Light 画布已实际显示演示任务；Dark 已提供入口，尚未单独截图验收 |
| Instruments | 对 Debug 演示进程完成 5 秒 Time Profiler 采样；仅验证采样链路，不构成 Release 性能结论 |

结果与图片保存在 [本轮截图画廊](../qa/evidence/2026-09-20-xcode/index.html)、[XCTest 摘要](../qa/evidence/2026-09-20-xcode/xctest-summary.txt) 和 [原脚本日志](../qa/evidence/2026-09-20-xcode/checks.log)。本机完整测试结果位于 `build/qa/xcode-test.*/Results.xcresult`，可用 Xcode 打开；采样位于 `build/qa/xcode-debug-idle.trace`，可用 Instruments 打开。原始构建产物、测试 Bundle 与采样留在忽略的 `build/` 下。

本轮遇到并解决的开发问题：

- 系统命令行仍指向 CLT：使用项目级 `DEVELOPER_DIR` 选择完整 Xcode，无需管理员权限。
- 直接打开 Package 不能提供本项目的原生 App 调试入口：新增 App Target、共享 Scheme 和测试 Target。
- 原测试脚本分三次临时拼接源码并编译：XCTest 复用这些 suite，在同一测试 Target 内增量编译；原跨进程验收仍保留。
- Preview 首次显示 “Active scheme does not build this file”：关闭同目录的旧 Package 窗口并重新打开 `DayLog.xcodeproj`、刷新 Canvas 后恢复。已确认文件在 App Target 编译源列表中。

构建包含一条 App Intents 元数据提取跳过提示，本项目没有 App Intents 功能。界面操作期间还观察到系统菜单和负尺寸布局诊断，尚未定位来源；本轮验证流程未发生崩溃，不能据此认定这些诊断已解决。

下一步应补自动 UI 场景（任务、草稿、退出保护），并针对大历史量的 Release 保存/滚动场景建立可比较的 Instruments 基准，再据热点决定性能改动。
