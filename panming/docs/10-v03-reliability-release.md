# 盘铭 v0.3 · 可靠性内核交付

2026-10-07。按 v0.3 → v0.4 → v0.5 → v0.6 顺序推进，本次交付第一阶段的可运行版本。AI 归纳、自动订阅与知识章节重构尚未实现，不把后续路线写成已交付能力。

## 1. 本版解决什么

以原件不可变、引用可追溯、人工内容受保护为验收原则：

- PM-A01–12 全部转成普通通过的回归测试，已无 xfail 掩盖。
- PM-W01–05 在隔离浏览器重新验证：窗口草稿隔离、冲突处理、旧引用、旧证据继续写作、文件导入默认模式。
- 新增完整 workspace backup/verify/restore、只读原件完整性检查和服务启动互斥。
- 原有 PostgreSQL 表、对象 ID、修订、原件与用户正文保留。只增加 fingerprint 查询索引，没有强制重写既有知识。

正式服务地址仍为 <http://127.0.0.1:8788>，health 返回 version=0.3.0。旧浏览器页面可以自行刷新以加载新前端；升级没有操作已有页面里的未提交表单。

## 2. 草稿和冲突

[DraftStore](../web/src/drafts.ts) 每个编辑器实例生成独立 editor_id，保存 `panming.draft.v3.<blog_id>.<editor_id>`。记录包含基础版标题/正文/revision、当前稿、草稿 revision 与更新时间。

- 保存成功只清理当前 editor 的、内容完全匹配的已提交分支；后续输入不会被旧请求响应清除。
- 其他窗口的分支不清理。刷新/重开后显示可恢复备份，**不会自动用另一窗口的稿替换服务器正文**。
- 恢复是复制为新的窗口分支，原备份继续保留。v0.2 的单槽草稿也作为 legacy 备份展示，不静默删除。
- 409 打开基础版/本机稿/服务器版对照。可下载本机稿、保留本机内容基于新版继续、使用服务器内容但保留本机备份、另存独立文章。
- “基于新版继续”只更新编辑基础，仍需手动合并并保存；服务器再次变化时继续 CAS 拦截。
- localStorage 不可用/配额满时显示警告；正文仍在页面，可下载或保存到服务器。服务器/网络错误不会清理本机稿。

这是三方文本对照与人工处理，不是自动语义 merge。恢复备份和副本会增加本机分支数量；自动保留期/安全清理还需后续实现。**工作空间 ZIP 不包含浏览器未保存草稿**，重要草稿需另行下载。

## 3. 来源与导出

服务端 SourceRef 当前包含 `material_id / material_revision / blob_hash`，通过指定的不可变修订解析正文并校验 hash。摘录行号仍在 digest 中；稳定 chunk anchor 属于后续消化流水线。

- Report、Blog、Proposal、Entry 新产物携带冻结来源；Blog 创建也接受明确 source_refs，所有入口一致。
- 正文链接带 `?revision=N`；读取素材页面按指定 revision 加载，不默默换成 head。
- 旧正文的无版本内部链接，若对象已有 source_snapshots，在展示/导出时绑定该快照；**不覆写用户存储的正文**。
- 早期没有 source_snapshots 的体验文章/条目显示“未冻结来源”的限制，不伪造历史快照。没有已保存证据的历史无法靠升级凭空补回。
- 通用 export 支持 revision 与 auto/raw/markdown。素材 auto/raw 按原件字节导出，BOM、二进制不变；无正文的 markdown 请求明确拒绝。
- CLI 原件下载校验 SHA-256，原子写入新文件；目标已存在时拒绝覆盖。

```bash
.venv/bin/panming export material_<id> --revision 1 --format raw --output ./exports/original.bin
.venv/bin/panming export report_<id> --revision 1 --format markdown --output ./exports/report-v1.md
```

## 4. Report 输入与异常边界

素材创建、正文修订、反馈和 Report 冻结共享输入提交屏障。获得屏障后记录 cutoff、读取输入 head 并保存 manifest；排在之后的写入属于下一版。协议名称为 `input_commit_barrier_v1`，**不是分布式 sequence/长任务 Worker 协议**。

选题每组最多 30 份素材，31/50/100 份分别分组；Blog API 总上限 100，分组不静默丢材料。前日未覆盖的新正文也进入 Web 未纳入计数。

另外修复：标题 trim、NUL、异常 URL/Origin、typed accept/proposal、设置首次写锁、落盘前主题校验、二进制 NUL 文件作为 stored_only、常见反引号/波浪线/缩进代码过滤。RevisionConflict 与普通输入错误分开。提取器有 quality_state，但仍是提取式整理，不是完整 Markdown AST 或语义事实校验。

## 5. 备份与恢复

[backup.py](../src/panming/backup.py) 导出内容包括：

- pm_objects 当前 head、pm_revisions 全部历史、pm_idempotency 重试账本；
- 当前与历史快照引用到的全部原件；
- format/schema_version、文件 SHA-256 manifest 与数量。

不包含数据库密码、runtime.json、环境变量、日志、未保存本机稿。ZIP **没有加密**，可能包含个人资料，请保存在可信位置，不上传公共仓库。

应用事务共享 workspace gate，备份/恢复使用排他 gate；备份也锁住领域表写入，校验每份原件后生成 ZIP。恢复先校验结构、日期、全部修订、关系、路径、数量和 hash，再进入事务；只接受空工作空间，拒绝覆盖已有内容。ZIP 不直接解压路径，重复/越界路径、缺失/损坏原件、不支持版本均拒绝。

本版限制：ZIP ≤128MiB，展开 ≤256MiB，文件数量 ≤10,000。大工作空间应使用数据库级一致备份方案。备份在短暂排他窗口内完成，尚无流式后台备份/定期备份/RPO SLA；数据库提交失败后可能留下无引用的内容寻址原件，完整性检查只报告、不自动删除。

```bash
.venv/bin/panming workspace backup --output ./backups/workspace-2026-10-07.zip
.venv/bin/panming workspace verify ./backups/workspace-2026-10-07.zip
# 对空工作空间服务执行，不是当前非空工作台：
.venv/bin/panming --server http://127.0.0.1:5178 workspace restore ./backups/workspace-2026-10-07.zip
```

Web 设置页提供下载、完整性检查与空工作空间恢复入口。当前非空工作空间禁用恢复；没有“强制覆盖”按钮。

升级前实际备份：`data/backups/pre-v03-2026-10-07.zip`。12 个对象、17 个修订、6 份原件。已在独立临时 schema/目录恢复，再次导出并比较全部元数据完全相同；临时恢复副本已清理。升级后正式数据再次比较不变，原件缺失/损坏/未引用均为 0。

## 6. 启动和验证

[server.py](../src/panming/server.py) 持有进程生命周期锁，成功绑定 loopback 端口后才登记 PID；重复启动/端口被占用不会覆盖有效 PID，退出后只清理自己的 PID。实现使用 POSIX flock，本轮验证 macOS；Windows 不是已验证目标。

```bash
./scripts/run.sh
./scripts/check.sh
# 浏览器隔离验收，退出时清理专用测试 schema/原件，不动正式数据库：
.venv/bin/python scripts/audit_server.py
```

本轮结果：**76 项 PostgreSQL/CLI/启动/备份测试 + 5 项 DraftStore 单元测试全部通过，0 xfail**。Ruff、TypeScript、生产构建通过。重复 ZIP 条目的构造用例有预期警告；TestClient/httpx 弃用警告仍需后续依赖维护。

浏览器验证：

1. A/B 开同一 v1，A 保存 v2，B 冲突出现三方对照。
2. A 确认 v3，B 刷新仍有备份；恢复 B、基于新版继续后保存 v4。
3. A 的旧稿可另存独立文章，原文章不覆盖。
4. 素材改 v2，旧博客正文链接和继续写作仍读 v1。
5. Report v2 中选择 v1，实际下载文件也是版本 1。
6. 隔离服务停止时保存失败，正文仍在；新建隔离服务并从 ZIP 恢复后，刷新可找回草稿并保存。
7. 导入按钮直接文件模式；正式设置页原件完整性通过。

截图/合成下载在 `data/v03-verification/`，gitignored。浏览器 E2E 当前为桌面实际回归，尚未接无头 CI 运行器；自动门禁覆盖存储算法、API/CLI 和构建，不冒充浏览器 CI 已完成。未做断电、磁盘满、长期 soak、全量 WCAG 验收。

## 7. 下一步

v0.4 的首个工作包仍按 [路线](09-iteration-roadmap.md)：持久 Job + 版本化 chunk/claim + Provider adapter + policy/budget + 有引用 Digest/Topic Delta。默认保持 local_only；在实际模型服务与允许处理的素材范围确定之前，不静默外发、不调用付费模型。

v0.5 的增量订阅、v0.6 的知识重构/修订/复习按依赖顺序保留。v0.3 没有通过新功能名称假装完成这些能力。
