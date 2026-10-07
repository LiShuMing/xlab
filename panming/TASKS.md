# 盘铭实施清单

2026-10-07 · 设计 v0.1 / 运行版本 v0.4.1。v0.2 原型、v0.3 可靠性内核、v0.4 证据任务与既有 LLM API 已交付。M0–M4 的完整目标继续保留，不能替代生产验收。实际状态见 [v0.4.1 API 接入](docs/12-v041-existing-llm-api.md)。

## v0.2 · 本机产品原型

- [x] 一键准备与运行，专用 PostgreSQL，运行数据忽略。
- [x] 今日/素材/Report/主题/写作台/图书馆/关注/设置页面。
- [x] 文字、链接、Markdown/TXT/对话导入，原件与新正文版本保留。
- [x] 原文摘录与行号、手动 Report、历史快照与更新提示。
- [x] 博客框架、Markdown 编辑/预览、本机草稿与 CAS 保存。
- [x] 确认文章、图书馆整理提案、重复采纳保护与复习。
- [x] 全局本地检索、Markdown/原件导出、HTTP CLI。
- [x] 显式体验数据、处理方式/手动关注/未启用日程说明。
- [x] PostgreSQL 工作流自动测试与生产前端构建。

## v0.3 · 本轮测试驱动的优先迭代

历史证据见 [08](docs/08-functional-audit-2026-10-07.md)，路线见 [09](docs/09-iteration-roadmap.md)，交付见 [10](docs/10-v03-reliability-release.md)。勾选仅表示该项已验证，不扩大到未实现的目标。

- [x] 扩展到 53 个自动用例；12 个已知缺陷显式 strict xfail。
- [x] 隔离环境浏览器闭环、双窗口草稿、旧证据与实际下载验证。
- [x] 依赖审计、250 份素材探针、功能审计与迭代方案沉淀。
- [x] P1：窗口级草稿保存/所有权；不清除其他窗口草稿（PM-W01）。
- [x] P1：409 三方对照/基于新版继续/副本/下载/保留备份（PM-W02）。
- [x] P1：统一 SourceRef、正文链接和旧证据写作冻结（PM-W03/W04）。
- [x] P1：历史导出 revision + 二进制 raw CLI 按字节写（PM-A02/A03）。
- [x] P1：31/50/100 份素材选题分组，前后端限制一致（PM-A01）。
- [x] P2/P3：标题/正文/URL/Origin/ID DTO 与错误分类（PM-A04–08）。
- [x] P2：首次 Settings 并发初始化（PM-A09）。
- [x] P2：常见反引号/波浪线/缩进代码过滤与提取质量状态（PM-A10）。
- [x] P2：Report 提交屏障/manifest/准确 cutoff、跨日补录提示（PM-A11）。
- [x] P2：落盘前校验、只读孤儿/缺失/损坏诊断（PM-A12）。
- [x] P3：导入按钮默认文件模式（PM-W05）。
- [x] 草稿存储失败单测、断网/重启/跨窗口浏览器实测回归。
- [x] 最小 workspace export/verify/restore：修订、关系、原件 hash 校验。
- [x] 启动互斥/端口与 PID 成功登记；重复启动不会覆盖有效 PID。
- [x] 对应 P1 全关闭，12 个 xfail 已移除；76 后端 + 5 草稿用例通过。
- [ ] 浏览器回归接入无头 CI、更多视口和可访问性矩阵。
- [ ] 原件 staging/崩溃恢复、审慎孤儿 GC；当前只报告不删除。
- [ ] 草稿分支保留期/手动清理、磁盘满/断电/长期 soak。

## v0.4–v0.6 · 后续执行顺序

- [x] v0.4 基础：持久 Job/租约/fence/checkpoint、幂等交付/手动重试/取消。
- [x] v0.4 基础：固定 revision/chunks/claims、严格引用校验、原件 hash 校验、无人工正文覆盖。
- [x] v0.4 基础：离线 mock/Provider Protocol、local_only 保护、字符额度 reservation/usage（非真实账单）。
- [x] v0.4 基础：Web/CLI 任务入口、证据卡/导出、Report 手动纳入与交付截止屏障。
- [x] v0.4 基础：schema 2 备份、旧 schema 1 兼容、恢复任务暂停、146 后端 + 5 草稿测试。
- [x] v0.4：既有 LLM_* / Chat Completions adapter，完整配置选择与脱敏；一次真实合成素材请求通过。
- [x] v0.4：有界调用、续租/取消、实际 token/attempt 账本、不确定用量保守占用与请求上限。
- [x] v0.4：真实 Digest、来源陈述/推断、Web/CLI 策略、原文引用和 Report 更新；180 Python + 5 草稿测试。
- [x] v0.4：schema 3 调用账本备份/恢复；默认 local_only，授权绑定具体服务/模型。
- [ ] v0.4：价格/金额预算和供应商账单校准。
- [ ] v0.4：Topic Delta 新增/重复/冲突、真实授权语料人工评估与试用省时验证。
- [ ] v0.5：RSS/GitHub Releases connector、cursor、来源健康、轮询/日报 occurrence 与补录。
- [ ] v0.6：Entry revision、Book/Chapter 重构、合并提案、源变更影响、复述/实验型复习。

## 设计交付

- [x] 产品定位、用户、四层契约与每日闭环。
- [x] 交互/视觉、页面/状态/移动与可访问性。
- [x] 三端架构、存储、任务恢复、日程、隐私和备份。
- [x] 数据实体、版本与引用、API、事件、CLI/导出契约。
- [x] 输入矩阵、LLM 流水线、Report/博客/图书馆质量与成本。
- [x] 分期、风险、验收矩阵、14 天试用与内容模板。

## M0 · 基础与归档

- [ ] Python package、TS Web 骨架、开发配置与迁移。
- [ ] owner/workspace/auth/scoped CLI token。
- [ ] BlobStore staging/hash/rename/原子归档。
- [ ] Material/revision/capture/duplicate identity。
- [ ] durable jobs、租约 fence、checkpoint 与取消。
- [ ] CLI capture file/note/url 与 server/API。
- [ ] Web 素材列表/原件详情/错误与 stored_only。
- [ ] 幂等、崩溃点、文件路径/大小、出站 SSRF 验收。

## M1 · Layer1 与 Report

- [ ] Markdown/网页/AI 对话导入、chunk anchors。
- [ ] provider adapter、policy 检查、预算 reservation/usage。
- [ ] digest/classification/引用验证与模型 mock。
- [ ] Report manifest/high watermark/覆盖状态/补录账本。
- [ ] scheduler/timezone/occurrence/catch-up。
- [ ] 今日/Report/原文对照/证据抽屉。
- [ ] Markdown export、SSE/轮询、outbox。
- [ ] partial/no_updates/晚到/重试/取消/预算与隐私验收。

## M2 · 博客与图书馆

- [ ] Brief/Outline/Draft suggestion 与选题合并。
- [ ] 人工 Markdown revision/CAS/diff/草稿恢复。
- [ ] accepted blog/series/book/chapter/concept。
- [ ] integration proposal/acceptance/lineage。
- [ ] simple review/full-text search。
- [ ] 回收站/引用 source_removed，最小备份恢复。
- [ ] 手改保护、重复采纳、引用完整性和端到端验收。

## M3 · 持续关注与维护

- [ ] RSS/GitHub Release 调度、cursor、capability/health。
- [ ] 主题新旧知识对照、偏好/噪声反馈、weekly review。
- [ ] source update 影响图、needs_review、lint。
- [ ] 可选 embedding namespace/权限/换模型索引。
- [ ] 完整 purge/缓存与索引清除/tombstone replay。
- [ ] 一致备份、RPO/RTO、故障与权限恢复演练。
- [ ] 14 天真实试用评估与下一轮范围调整。

## M4 · 按价值选扩展

- [ ] PDF/OCR/字幕 ASR 的输入质量与成本验证。
- [ ] 浏览器收集入口与更多对话格式。
- [ ] 受限平台授权 adapter 可用性验证。
- [ ] 博客发布 connector 与公开导出审核。
- [ ] 多用户权限与团队协作专项设计。
