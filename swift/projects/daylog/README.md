# 刻白 · 工作日记

随时记下今天要做的事，安静地提醒，留下一天的工作轨迹。

当前阶段：**v0.1 原生应用已实现，进入本机使用与验收**。SwiftUI + Core Data/SQLite，包含工作日记、历史、个人日记、菜单栏、提醒配置和真实 LLM 回顾。保留 C3 工作台布局，采用晴白主题与蓝色 / 杏色 K 图标；工程名仍为 DayLog。

Xcode 开发：打开 `DayLog.xcodeproj`，选择 `DayLog / My Mac`，⌘R 运行、⌘U 测试。Debug 默认使用隔离演示数据，详见 [Xcode 开发与验收](docs/xcode-development.md)。

日常运行：在本目录执行 `./scripts/run.sh`，或双击构建后的 `build/DayLog.app`。

验证：`./scripts/check.sh`；需要验证模型时使用 `./scripts/check.sh --llm`。

仓库保留源码、工程配置、测试、设计文档与生产图标。文档中引用的 `qa/evidence/` 截图、日志及 `design/brand/` 探索图片仅保存在本机，不随 Git 分发；新检出可运行 `./scripts/xcode.sh render build/qa/appearance` 重新生成当前界面预览。

[构建、使用与当前实现说明](docs/running.md) 是当前运行入口，包含环境限制、数据位置、验收和未完事项。

[测试报告](docs/test-report-2026-09-18.md) 记录原始问题；[高优先级修复与回归](docs/persistence-fix-2026-09-18.md) 记录数据读取、后台保存与退出保护；[中等优先级修复与回归](docs/workflow-fix-2026-09-18.md) 记录状态撤销与回顾输入范围修复。

[修复后的场景复测](docs/scenario-test-2026-09-18.md) 包含真实模型生成/采纳验收、新发现的使用问题和 [15 张测试截图画廊](qa/evidence/2026-09-18-scenarios/index.html)。

[草稿与阅读体验修复](docs/draft-fixes-2026-09-18.md) 修复设置草稿、备份范围、隐藏输入定位与 Markdown 阅读，新增 31 项自动检查及本轮验收截图。

## 从这里开始

产品名为 **刻白 / Kebai**，已采用 B 的 K 形折页并接入亮色主题：[实现与页面图集](docs/kebai-daylight-theme.md)。前期 [三组图形方案](docs/kebai-logo-design.md) 保留作设计记录。

新增设计提案：[主题订阅 / 每日调研](docs/research-subscriptions-design.md)，先确认 UI、来源、交付与日记衔接；尚未实现调研执行器或启用定时任务。交互稿为 `design/daylog-research-v1.html`。

| 文件 | 用途 |
| --- | --- |
| [产品方案](docs/proposal.md) | 最初方案、功能范围和本机环境检查快照 |
| [技术设计与实现方案](docs/technical-design.md) | 前期完整方案与当前落地说明：C3 → SwiftUI、模块、模型、保存/历史/AI/提醒、验收 |
| [LLM 配置与接口](docs/llm-configuration.md) | 使用 ~/.env 中 LLM_* 配置，明确开发加载、沙盒导入、Provider 与连接验证 |
| [UI 规范](docs/ui-spec.md) | 页面、组件、布局、交互、状态及 SwiftUI 映射 |
| [v0.2 视觉方向](docs/design-directions.md) | Liquid Glass、Material 3 Expressive、Graphite Studio 三版比较 |
| [v0.3 Studio 迭代](docs/studio-v3.md) | 当前版本：参考 Linear、Things、Notion，细化 C 的任务编辑与工作记录 |
| [早期实现约束](docs/implementation.md) | 早期补充说明；具体实现决策以技术设计主文档为准 |
| [设计决策](docs/decisions.md) | 已明确需求、推荐方案、待用户选择的事项 |
| [设计稿说明](design/README.md) | 如何用工具查看、比较、批注和冻结设计稿 |
| [实施清单](TASKS.md) | 环境准备、UI 评审和逐阶段验收 |

## 目录

```text
daylog/
├── README.md
├── TASKS.md
├── docs/
├── design/                   # 可交互界面草稿，作为 SwiftUI 实现参考
├── DayLog/
│   ├── App/                  # 应用入口和场景
│   ├── Features/             # Today、History、Journal、Settings
│   ├── Core/                 # 纯 Swift 领域模型、配置、排期
│   ├── Models/               # 预留后续模型拆分
│   ├── Services/             # 保存、提醒、模型、导出
│   └── Resources/            # 资源和本地化
└── DayLogTests/               # 可执行领域检查
```

保留 SwiftPM 与脚本打包入口，不依赖完整 Xcode 即可运行。早期 CLT 缺少 SwiftData 宏插件，因此采用 Core Data/SQLite 原子文档存储；现已接入完整 Xcode，保留原数据格式。

已通过 Xcode 构建、XCTest、Preview 和短时 Instruments 采样；公开分发签名及系统权限仍需专项验收。
