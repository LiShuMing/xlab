# 盘铭 v0.2 · 当前实现与运行说明

> 此文保留初版实现记录。当前已升级 v0.3，草稿、版本、备份及测试结果以 [v0.3 交付说明](10-v03-reliability-release.md) 为准。

2026-10-07。此文描述实际代码；01–06 保留为目标设计。本版是一套本机单 owner 的可操作产品原型，真实数据写入 PostgreSQL，并提供可编辑的 Web 与 HTTP CLI。

## 1. 启动与停止

```bash
cd /Users/lism/xwork/xlab/panming
./scripts/setup.sh
./scripts/run.sh
```

浏览器打开 <http://127.0.0.1:8788>。API 文档在 <http://127.0.0.1:8788/docs>。开发模式可单独 `npm --prefix web run dev`，访问 5178，代理同一个 API。

setup 创建独立 `.venv`、锁定 Python/Node 依赖、初始化盘铭专用 PG cluster 并构建前端。已有系统数据库不作修改。原件、数据库、随机生成的数据库凭据与运行日志在 `data/`，不会进入 Git。

`./scripts/stop.sh` 验证 PID 对应盘铭服务后停止，并停止本项目的专用 PG cluster；不停止外部 `PANMING_DATABASE_URL` 数据库。Ctrl+C 也可以停止前台 API，专用数据库仍可运行；再次 run 会复用已有数据。

如果没有 PostgreSQL，可安装官方/PostgreSQL 包管理器版本，或配置 `PANMING_DATABASE_URL`。本机已验证 Homebrew PostgreSQL 17。setup/run 默认 API 8788、PG 55432；端口冲突会报告，不能停止未知服务来占用。

## 2. 已可使用的闭环

1. **收集**：右上角保存笔记、网页链接、粘贴对话或上传文件。文件上限 8MiB；可解析文本上限 50 万字符。不支持的原件仍保存，显示“仅存原件”。
2. **阅读**：素材详情显示原文摘录、行号、主题和保存原因；可以标有价值/已知/稍后读。链接无正文时显示待补正文，详情可“补充正文”创建新版本。
3. **Report**：今日页手动生成，按三类初始主题归集摘录；生成后新输入显示未纳入，更新创建 v2，版本入口可读旧快照。
4. **写作**：从 Report 或素材生成写作框架；Markdown 编辑/预览、保存/导出，人工修改以 revision CAS 保护。本机草稿自动暂存，不冒充服务器已保存。
5. **入馆**：先保存并确认文章，再查看整理提案，点击“采纳入馆”。提案绑定博客 revision；重复采纳返回同一条目。
6. **复习**：图书馆保存正文和来源；自评能解释/模糊/忘记后，更新 30/7/3 天后的复习日期。

主题页按数据库与系统、AI 与工具、思考与方法三个初始主题整理；全局搜索在已加载的素材、博客、知识正文中关键词过滤。自定义主题、书籍目录重排、语义搜索尚未实现。

关注页面保存手动清单，打开原站；设置页面保存名称和习惯整理时间。页面明确告知没有自动轮询/定时任务，保存时间偏好不会启用后台工作。

## 3. 当前归纳方式

使用确定性提取：按原始行号提取最多三个非代码正文段落，保留来源，不调用外部模型。Report 的“选题”是按主题生成的问题框架；博客产物是包含原文证据的写作框架，未测量结果与个人判断留给用户填写。

这不是完整语义归纳、事实核验或自动研究。AI 对话示例明确包含用户/助手角色，但本版还没有 claim 级事实/推断 schema。文本处理器、Provider 及引用支持性审查按原设计后续加入。

## 4. CLI

```bash
.venv/bin/panming capture note --title "一个新问题" --text "需要进一步验证的理解。"
.venv/bin/panming capture file ./templates/blog-brief.md
.venv/bin/panming capture url https://example.org/article --title "待阅读文章"
.venv/bin/panming report --date 2026-10-07
.venv/bin/panming export report_<id> --output ./exports/report.md
.venv/bin/panming demo
```

CLI 与 Web 使用相同 API。最后一条命令加入五份体验素材、一份示例 Report/博客/知识条目；素材和示例文章标记 is_demo，重复操作不重复创建。测试验收笔记另以“浏览器验收”标题标明。

## 5. 持久化与版本

- `pm_objects`：当前对象，kind 区分 Material/Report/Blog/Entry/Proposal/Source/Settings。
- `pm_revisions`：不可变对象快照；当前 head CAS 更新。
- `pm_idempotency`：capture retry key 与 body hash。
- `data/blobs/<hash前缀>/<hash>`：按内容寻址的原件，写入后 fsync/rename。

这是原型的对象存储 schema，尚未展开成 04 中全部领域表。Report、Blog 的 source snapshots 保留精确内容版本；素材新正文不会改写旧报告。以后迁移到规范化 schema 时需要保留对象 ID、revision 和原件 hash。

capture 会按类型/标题/URL/原件 hash 识别重复；并发使用事务 advisory lock。文件/笔记更新用新素材版本；阅读反馈目前也形成对象 revision，未来会与语义 source revision 分离。

所有任务当前在请求内完成，没有 durable Worker、checkpoint、scheduler、outbox；不能把原型的短事务归纳扩为长模型任务而不补这些设施。Report 的 cutoff 是事务执行时，尚无设计中的输入 sequence 水位协议。

## 6. 访问范围与限制

默认仅绑定 127.0.0.1，API 检查 loopback client、Host 与写操作 Origin，Markdown 不渲染原始 HTML、外部图片不自动加载。PG host 使用随机密码和 SCRAM；Unix socket 位于 owner-only 目录。

本版没有账号、团队权限、云模型策略执行器、自动下载、OCR/ASR、外部发布、删除/完整遗忘、定期备份、规模化分页。用于本机体验；公网部署必须先实现原设计的认证/授权/任务/备份边界。

## 7. 已验证

自动测试使用真实 PG 的独立临时 schema，测试结束删除该 schema：

- capture 重试及 request body mismatch；
- 原件导出一致；
- Report 输入冻结与 v1/v2 历史；
- 博客人工正文与并发版本冲突；
- 博客确认、图书馆提案和重复采纳；
- 复习日期与记录；
- URL 不冒充已读取；跨站写入/不安全协议拒绝；
- 体验数据标记与重复导入；
- source 更新后旧 Report 写作与原件版本可回溯。

浏览器实测：保存“浏览器验收”笔记 → Report 更新 v2 → 创建博客 → 编辑保存 → 确认 → 提案采纳 → 复习 → 刷新，所有数据仍在。

```bash
./scripts/check.sh
```

运行态截图保存在忽略目录 `data/screenshots/`，不是源码。当前目标是收集实际使用反馈，再决定优先接入真实 LLM、自动关注或自定义知识目录。

## 8. 扩展审计（同日）

后续边界与并发审计扩展到 53 个自动用例：41 passed、12 xfailed，另在隔离浏览器复现 5 个问题。已知缺陷尚未修复；`check.sh` 的成功退出不能解释为“全部功能无漏洞”。请先阅读 [完整审计](08-functional-audit-2026-10-07.md)，特别是双窗口本机草稿丢失、历史导出错版、旧来源写作漂移及同主题 >30 份素材的写作限制。

下一版的可靠性与功能优先级在 [迭代路线](09-iteration-roadmap.md)。本轮没有改动业务实现，也没有修改正式工作台已有内容。
