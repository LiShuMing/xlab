# 可执行检查

CLT 环境下使用 DayLogChecks，不依赖完整 Xcode 的 XCTest 运行时。

在项目目录运行 ./scripts/check.sh：先编译，运行 19 项领域/配置/排期检查，再用独立进程验证普通和超过 50 MB 的 SQLite 保存/恢复，并运行 20 项后台保存队列、失败恢复和退出等待检查，以及 30 项状态撤销、回顾输入范围和私人内容隔离检查。另有 31 项草稿事务、导出范围、定位与 Markdown 安全渲染检查；合计 100 项断言和 4 项跨进程 SQLite 保存/恢复结果。任何失败返回非零退出码。

可单独运行 ./scripts/check-workflows.sh 验证两个 P2 修复；使用隔离 SQLite 与捕获提示词的生成器，不读取真实配置或联网。

./scripts/check-drafts.sh 单独验证统一草稿流程，覆盖批量保存失败不部分提交、冲突后重试、SQLite 重读与私人内容隔离。

./scripts/check.sh --llm 额外只向现有配置发送固定 Reply OK，不发送工作日记、不打印配置值。

界面使用 --demo 内存模式手动验证。已验收项目和未覆盖边界见 [实施清单](../TASKS.md)。

## Xcode

`./scripts/xcode.sh test` 或 Xcode ⌘U 运行 `DayLogRegressionTests`。XCTest 直接复用 `CoreChecks.swift` 与 `qa/` 下三个 suite；`XCODE_TESTING` 仅屏蔽命令行 `@main` 入口，保留相同断言。另有演示数据隔离检查。用例无 App 宿主，存储和模型均隔离。完整用法见 [Xcode 开发入口](../docs/xcode-development.md)。
