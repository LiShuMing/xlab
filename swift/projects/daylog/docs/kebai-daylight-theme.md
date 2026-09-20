# 刻白 · 晴白主题落地

2026-09-20。用户选定 B“刻面字标”，要求改为亮色调，并同步应用内部配色。本轮保留 K 形折页，采用云白、清透蓝与浅杏色，保留原 C3 的导航 / 任务 / 详情结构。

## 已实现

- 使用者可见名称改为“刻白”，开发版为“刻白 Dev”；主窗口、菜单栏标签、提醒文案及设置说明同步更新。
- 应用图标接入 Xcode 的 `AppIcon.appiconset` 和 SwiftPM Bundle 的 `Kebai.icns`，不依赖手动设置 Finder 图标。
- 新增 `Features/Design.swift`，集中维护颜色、K 形矢量、侧栏标记与外观修饰器。
- 主界面、历史、私人日记、任务详情、回顾面板、设置、草稿与菜单栏共享主题；继续支持跟随系统 / 浅色 / 深色。
- 设置页提醒时间输入增加明确的独立输入框、隐藏重复表单标签，解决标签挤压折行；例外日期保留格式提示。
- Bundle ID、SQLite 路径、Keychain service 和备份格式保持原值；Swift Target 和构建产物目录仍使用 DayLog。

## 色彩规范

| 用途 | 浅色 | 深色 |
| --- | --- | --- |
| 操作强调 | `#2464C5` | `#91BEFF` |
| 工作台背景 | `#F5F8FD` | `#171F2C` |
| 卡片 / 详情 | `#FFFFFF` | `#222D3D` |
| 导航背景 | `#ECF3FF` | `#1C293C` |
| 选中背景 | `#DCEBFF` | `#283F61` |
| 今日重点背景 | `#FFF2E5` | `#352D2A` |
| 图形杏色 | `#FFBD8A` | `#EDB489` |
| 完成状态 | `#20745A` | `#7CD5AD` |

浅蓝和杏色用于形状与背景，文字链接使用更深的蓝色。基于颜色数值计算，浅色强调文字在白色 / 选中背景上的对比度分别约 5.67:1 / 4.69:1，深色强调文字在详情背景上约 7.29:1；这不是完整 VoiceOver、增加对比度或所有系统控件的无障碍认证。

## 图标资产与来源

先用内置 imagegen 生成 [亮色材质参考](../design/brand/kebai-daylight-icon.png)，完整提示词在 [生成记录](../design/brand/kebai-daylight-prompt.txt)。生成图的透明边缘不适合直接打包，因此实际采用 `KebaiAppIcon`：用与侧栏标记共用的 `KebaiFacet` 路径绘制圆角、渐变与阴影，确定性导出 PNG。生产图标是同一设计方向的矢量实现，并非生成图的逐像素复刻。

- [实际使用的 1024 px 图标](../design/brand/kebai-daylight-production.png)
- `DayLog/Resources/Assets.xcassets/AppIcon.appiconset/`：完整 macOS 16–1024 px 多倍率资源。
- `DayLog/Resources/Kebai.icns`：SwiftPM 打包图标。
- 菜单栏使用简化单色 K，侧栏使用蓝 / 杏双色 K。

本轮交付传统 AppIcon，支持项目的 macOS 14 部署下限；尚未制作 Icon Composer `.icon` 分层资产，不声称支持原生 Liquid Glass 动态折射。

重新生成流程：

```bash
./scripts/xcode.sh render build/qa/appearance
cp build/qa/appearance/kebai-icon.png design/brand/kebai-daylight-production.png
python3 scripts/prepare-icons.py
./scripts/xcode.sh build
```

图标导出与应用 UI 都使用生产源码。常规构建使用已提交的资源文件，不需要每次运行生成器或调用图像模型。

## 验证与边界

[页面图集](../qa/evidence/2026-09-20-kebai-theme/index.html) 保留 9 张生产 SwiftUI 页面离屏渲染图和图标。`KebaiAppearanceChecks` 使用内存演示数据，单独进程和偏好，不读取真实日记或模型配置，不请求通知或开启登录项。

覆盖浅色 / 深色今日页、浅色历史 / 私人日记、浅色 / 深色设置、回顾、菜单栏内容和草稿面板。原生窗口标题栏、Dock 外观、系统菜单交互没有通过本轮离屏渲染验证。图集不能替代实际点击、输入法和退出保护的 UI 自动化。

构建与回归摘要保存在图集目录的 `checks.log`。XCTest 复用既有 100 项断言，另验证演示数据隔离；本轮没有发送真实模型请求，也没有迁移用户数据。
