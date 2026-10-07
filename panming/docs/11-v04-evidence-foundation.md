# v0.4 · 证据消化的第一条可运行链路

2026-10-07。这一版交付的是 **v0.4 的离线基础切片**，不是“真实 AI 深度归纳已完成”。版本号为 0.4.0；实际模型接入与人工质量评估仍是本阶段后续工作。

后续状态：0.4.1 已接入用户的既有 LLM API，并完成真实合成素材验证，详见 [12](12-v041-existing-llm-api.md)。本文保留 0.4.0 的交付记录。

## 1. 现在能做什么

在 Web 的“消化任务”选择 1–12 份有正文的素材，或在素材详情点击“证据化消化（本地 mock）”。服务端冻结素材 revision、原件 SHA-256 和正文片段后立即返回任务，不在 HTTP 请求中等待处理。

Server 后台处理任务；关闭浏览器不取消任务。页面自动刷新状态，支持取消、手动重试和查看结果。相同输入版本、provider 和协议重复提交复用同一任务；要重新处理失败/取消的记录，使用重试，不重复预留额度。

结果分开存储来源陈述与模型推断；**当前 mock 只生成逐字来源摘录**，不生成个人判断、不识别观点冲突。证据卡可以展开摘录、片段范围、原件/片段 hash，并打开引用时的素材版本。修订素材不会更新旧证据。

完成结果不会自动修改旧 Report、Blog 或 Entry。用户手动更新 Report 时，只纳入其 manifest 完整包含的、在截止屏障前交付的 Digest；历史 Report 保持原样。结果及其来源可以导出 Markdown。

## 2. 使用方法

```bash
cd /Users/lism/xwork/xlab/panming
./scripts/run.sh

# 先用 capture 收集；material_id 从其 JSON 响应中取得。
.venv/bin/panming capture note --title 'Join 学习' --text 'Build 与 Probe 应遵守相同的分区规则，使相同键在同一分区相遇。'
.venv/bin/panming digest material_id
.venv/bin/panming digest material_id --revision 1
.venv/bin/panming jobs list
.venv/bin/panming jobs cancel job_id
.venv/bin/panming jobs retry job_id
.venv/bin/panming report --date 2026-10-07
.venv/bin/panming export digest_id --format markdown --output evidence.md
```

`material_id`、`job_id`、`digest_id` 是示意占位，使用实际响应的 ID。可一次传多个素材 ID；指定 `--revision` 时只能传一个 ID。Web 入口为 `http://127.0.0.1:8788/#/jobs`。

## 3. 任务可靠性

实现集中在 [pipeline.py](../src/panming/pipeline.py)，复用 [storage.py](../src/panming/storage.py) 的 `pm_objects` / `pm_revisions`，新增 `job` / `digest` kind，未新增第三方队列。

```text
queued → running → succeeded / failed
queued / running / paused → cancelled
failed / cancelled / paused → queued（显式重试）
running 租约过期 → 新 owner 领取 / 尝试耗尽后 failed
备份中的 queued / running → 恢复后 paused
```

- 初始 checkpoint 为 `input_frozen`；领取后为 `provider_pending`；原子交付后为 `evidence_validated`。
- 租约 30 秒；领取、取消、恢复暂停递增 fence。交付检查 running 状态、owner、fence 和租约未过期；旧 worker 的输出不能发布。
- `heartbeat()` 可续租，已有回归；当前 mock 很快完成，后台线程不自动启动长调用续租器。**真实 provider 必须补充超时、心跳与合作取消，不能直接拿此线程执行无界网络调用。**
- 最多 3 次领取尝试；租约过期自动恢复，处理失败需手动重试；不自动切换 provider。
- 生成阶段不持有数据库事务。Digest 与 succeeded Job 在同一事务交付，重复完成不生成第二份结果。
- 工作空间 shared gate 覆盖任务写入，备份/恢复仍使用 exclusive gate。Job 元数据用 schema 级 `/jobs` advisory lock 串行提交、额度判断与交付。
- Report 按 `inputs → report 日期 → jobs` 顺序取得提交屏障，然后记录 cutoff。新协议为 `input_and_delivery_commit_barrier_v2`，同时冻结素材 head 与已提交的证据交付；旧报告协议不回填。

这是单机小工作空间实现，不是分布式高吞吐任务系统。当前队列和状态接口仍会扫描对象，未交付队列索引、分页、outbox、独立 worker 进程或长时间 soak。

## 4. 证据与质量边界

输入上限 60,000 Unicode 字符；超限明确拒绝，不静默截断。每 2,000 字符形成片段，保留完整正文，采用 `unicode-offset-v1`：`offset/end` 是 Python Unicode code-point 的半开区间，**不是 UTF-8 字节偏移，也不是 JavaScript UTF-16 下标**。行号是导航提示，片段 hash/偏移是精确锚点。

每个片段包含 SourceRef、稳定 `chunk_id`、`chunk_hash`、原文、标题、主题和行范围。原件缺失或 hash 损坏时不能提交；执行前再次检查原件与当前处理策略。

`claims-v1` 使用严格 DTO，拒绝未知字段、无引用 claim、不存在的 chunk、非原文摘录、非法类别与超长输出。引用只能指向冻结输入。`source_statement` 表示“来源这样说”，**不意味着来源的内容正确**；`inference` 必须单独标记，但当前 mock 不输出该类别。

`coverage_state=complete` 只表示每份输入至少有一条摘录，不代表读完所有内容或完成深度归纳。纯代码 / 短文等没有合适摘录时，单素材任务明确失败；混合输入交付 `partial`，记录每份 `source_coverage`，在界面提示遗漏。

Topic Delta 当前只是 **原件是否曾处理过**（`first_processed` / `previously_processed`）的机械记录，不是“新知识 / 已知 / 矛盾”的语义判断。`conflict_detection=not_assessed`，所有结果需人工复核。

沿用 karpathy-llm-wiki 技能的不可变原始来源与可追溯知识原则：结果与原件分开保存，保留版本，绝不让自动归纳覆写个人正文。本次是产品实现，不执行 wiki ingest 或初始化 raw/wiki 目录。

## 5. 隐私与额度

生产应用仅注册 `MockProvider`。Provider Protocol 与测试注入点已建立，**没有启用 HTTP/云模型 adapter**；传入其他 provider 被拒绝，环境中的模型 key 也不会自动启用外发。凭据不写入任务/备份。

素材默认 `local_only`。策略检查不仅针对选定 revision，还在执行前读取当前 head。云 provider 的策略保护有合成测试，生产路径外部模型调用数为 0；这不替代未来的外发授权、敏感度、host allowlist 和 SSRF 设计。

每天上限 500,000 个字符单位；原子预留为输入长度 + 20,000 输出上限。成功结算输入 + 校验通过的 JSON 输出长度，失败按输入结算，取消释放预留；每天的已用量保留在 `usage_by_day`，跨日重试不会覆盖旧账。排队任务按提交/重试日期归属额度；取消/失联尝试尚无精确 CPU 用量计费。

这个额度是离线模拟处理的限制，**不是模型 token、真实费用预算或供应商 usage 账单**。mock 费用为 ¥0。真实模型还需要独立请求/attempt 账本、实际 token 和价格、超时后的不确定费用、取消结算及有界 reservation，不能宣称这一版已实现云账单准确性。

## 6. 备份与恢复

新导出使用 workspace schema 2，仍可读取 v0.3 schema 1。全部 Job 历史、冻结片段、Digest 与 Report 快照进入原有 ZIP；未引入凭据文件。

恢复前校验片段是否能从实际素材 revision 重建、逐字引用是否有效、Digest 是否有对应租约历史、预算/尝试次数是否有效、嵌入 Report 的 Digest 是否与其版本一致。恢复仅允许空工作空间；未完成任务统一暂停、释放预留、递增 fence，必须由用户重试后才能执行。

升级前正式工作空间另存 `data/backups/pre-v04-2026-10-07.zip`，12 对象 / 17 修订 / 6 原件，保留之前的 v0.3 备份。备份和验收截图都是运行数据，已被忽略，不进入源码。

新版实际启动后另存 `post-v04-2026-10-07.zip`，升级前后 metadata 完全相等，原件完整性检查无缺失/损坏/孤儿。同时将真实升级前 schema 1 备份恢复到临时独立工作空间，再导出 schema 2：对象/修订/幂等元数据与原件字节完全相等，未覆盖正式数据。

## 7. 验证与下一步

```bash
./scripts/check.sh
```

本轮包含 146 个 Python 用例、5 个草稿单测，以及 Ruff / TypeScript / Vite 构建。新增任务测试覆盖并发去重、额度只预留一次、取消/过期 fence、重启恢复、续租、重复交付、失败释放/跨日账本、恶意输出、私有素材禁止云 provider、原件损坏、Report 交付屏障、备份暂停/篡改拒绝和旧 schema 兼容。

引用语料的 30 个参数化机械测试使用 5 个合成模板轮转；**不是 30 份人工标注的真实 AI 质量评估**，不能据此声称摘要、冲突识别或省时效果。

隔离 PostgreSQL schema / 临时原件目录的浏览器验收验证了：两份输入提交后自动交付、证据展开、原文版本跳转、Report v1 不自动变化、手动 v2 纳入 Digest、素材改成 v2 后旧证据仍打开 v1、实际 Markdown 下载包含 v1/hash。截图与下载文件位于被忽略的 `data/v04-verification/`。测试环境清理不涉及正式对象。

390px 窄屏任务页无横向溢出；临时视口已恢复。正式服务已加载 0.4.0，已有 6 份素材保留；未提交正式素材的消化任务。浏览器自动化使用本机实际界面，不是已建立的无头 CI 测试集。

下一步仍是 v0.4，而不是跳过质量门槛直接做订阅：确定一个实际模型与允许处理的素材范围，完成有界调用/usage/策略，然后做真正的语义 Digest、Topic Delta 与人评集。v0.5 RSS/GitHub Releases 和 v0.6 知识重构保持后续顺序，尚未实现。
