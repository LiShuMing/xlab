# 原生应用源码

通过上级 Package.swift 构建。当前采用 SwiftUI + Observation + Core Data/SQLite。

- App：应用场景、共享状态、事务、通知回调。
- Core：独立 DayLogCore 模块，包含领域模型、Dotenv/LLM 和提醒排期。
- Features：今日、任务详情、AI 回顾、历史、个人日记、设置。
- Services：SQLite 文档存储、Keychain 配置、系统通知协调。
- Resources：应用 Info.plist。

运行、数据位置与实现差异见 [运行说明](../docs/running.md)。
