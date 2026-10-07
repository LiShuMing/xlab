---
title: 盘铭交付与验收计划
version: 0.1
updated: 2026-10-07
status: proposed
---

# 盘铭交付与验收计划

## 1. 交付范围与实施边界

本轮交付六份产品/技术设计、文档入口、实施 backlog 和三份内容模板。当前无产品运行代码、外部连接、真实采集、模型执行或已启用日程。

设计基线已作推荐决定，未知项保留试用验证入口。后续实现按下列阶段推进，每一阶段有可演示输入/产物、可恢复失败流程和清楚的退出条件。

## 2. 设计决策记录

| ADR | 决定 | 原因 | 何时重新评估 |
| --- | --- | --- | --- |
| 001 项目边界 | xlab 内独立 `panming/` | 内容领域自成闭环；可单独部署与提取 | 与 Liminalis 共用登录/导航需求稳定后 |
| 002 三端协议 | CLI / Web 使用同一 HTTP API | 规则一致，事务与权限有一个入口 | 需要真正离线完整处理时 |
| 003 存储 | PostgreSQL 元数据 + immutable blob | 版本、队列、预算、引用可事务处理 | 多机/磁盘容量要求 S3 时 |
| 004 执行 | DB durable jobs + worker + scheduler | 首版易恢复，不依赖内存任务 | 实测数据库队列瓶颈出现时 |
| 005 原件 | Layer0 只增版本，派生独立 | 可复核、可回放，保留来源上下文 | 用户明确删除/遗忘时 |
| 006 输出 | Report/草稿可自动生成，采纳和发布分开 | 用户对个人理解与外发负责 | 建立公开发布连接后 |
| 007 每日范围 | 固定 timezone + cutoff + manifest + revision | 晚到、补录、历史可解释 | 用户改节律时，只影响未来日程 |
| 008 知识维护 | 提案 + diff + CAS + lineage | 避免模型重写人工内容 | 编辑协作/更细块版本需要时 |
| 009 搜索 | P0 全文/metadata，P1 optional embeddings | 先可用再测语义收益 | 问题集显示关键词检索不足时 |
| 010 视觉 | Raft 的色块/边界 + 安静阅读区 | 品牌识别和长期阅读兼顾 | 可访问性与实际阅读评测后 |
| 011 内容优先 | 允许 0 个博客候选 | 防止“每天必须写”产生低质量内容 | 用户选择不同创作节律后 |
| 012 平台能力 | 先 RSS/公开网页/Release/文件导入 | 能力可验证，受限源可手动归档 | 授权接口已验证可持续用时 |

## 3. 分期实施

### M0：基础与原件归档

范围：项目骨架、配置/owner、PG schema、BlobStore、本地原子落盘、任务领取、CLI capture file/note/url、Material 原件列表和错误反馈。

验收：同 key 重试只创建一次资源；保存原件 hash 对得上；重启不丢 job；文件/DB 提交点注入崩溃可恢复；不支持格式也能清楚地存为 stored_only。时间假设 1–2 周。

### M1：Layer1 与每日 Report

范围：text/web extractor、AI 对话 Markdown、chunk/引用、分类/digest、provider 策略与预算、每日/手动 Report、partial/no_updates、快照与补录、Web 今日/详情/Report、Markdown 导出。

验收：用同一批公开与合成样例完成 CLI → Report → 点击证据；来源失败不显示无更新；21:30 后输入可补录；相同 run retry 不重复交付；停止 provider 仍能读取已存内容。时间假设 1–2 周。

### M2：Layer2 与 Layer3 最小闭环

范围：Blog Brief、Outline/Draft Suggestion、人工 revision/CAS、accepted blog、book/chapter/concept、integration proposal、人工采纳、简易复习、全文检索。

验收：同一中心问题可合并；手改正文后重生成只给 diff；同提案两次采纳返回同结果；章节目录正确；概念可追溯到原件；复习自评更新 next_due。时间假设 1–2 周。

M0–M2 合起来是 P0 MVP；日报定时与基本图书馆必须在 P0，而不是把核心愿景无限延期。订阅、ASR、全语义搜索可以后置。

### M3：持续来源与可维护知识

范围：RSS/GitHub Release 定时、source capability/health、增量 cursor、统一 noise feedback、跨日主题 diff、来源变化影响知识、embedding 试验、weekly review、备份/恢复实机演练。

验收：一源限流其余继续，重复 polling 不重复入库，旧文转载不算新事件；语义源变更能定位受影响条目；费用透明；恢复后引用与日程正确。时间假设 1–2 周。

### M4：扩展输入与发布连接

按真实需求选择：PDF/OCR、视频 ASR、浏览器保存、受限平台授权、博客站点导出集成、更复杂知识图谱、团队权限。每项分别验证成本和权限；不以“任意内容”作为一次性实现全部连接的要求。

以上为一名全栈开发者的工作量粗估，不是承诺日历。总 P0 约 3–6 周，基础质量与试用可能增加 1–2 周；M3/M4 依据价值排序。

## 4. 第一条端到端实现切片

选择一个真实研究主题“外存算子的状态与恢复”，使用用户允许处理的一份 Markdown、一个公开文章链接、一段 AI 研究对话和一条个人实验笔记。

演示顺序：归档 → 对照原件/摘要 → 今日 Report → 采纳一个 Brief → 编辑博客 → 将“分区恢复协议”整合为图书馆条目 → 回到中心问题做一次解释。任何阶段没有可用证据时展示缺口，不演示成自动完成。

切片避免先做大型来源连接或图形图谱；价值验证是用户能否用更短时间形成自己的认识。测试样例用授权/公开材料或合成内容，私人真实对话需明确模型处理策略。

## 5. 功能、可靠性与安全验收矩阵

| ID | 场景 | 应观察到 | 阶段 |
| --- | --- | --- | --- |
| A01 | 相同 capture request 连续发送 3 次 | 同一个素材/occurrence，返回一致 | M0 |
| A02 | 同文件新内容再次上传 | 新 source revision，旧版本保留 | M0 |
| A03 | 不同作者转载同一正文 | 原件/作者都在，Report 合并展示 | M1 |
| A04 | URL 登录/404/跳转/编码失败 | metadata 已归档，needs_input/failed 正确 | M1 |
| A05 | 大文件/zip 路径穿越 | 拒绝且无越界落盘，输入仍可重新选择 | M0 |
| A06 | 视频只有链接没有字幕 | stored_only，不显示已看过视频 | M1 |
| A07 | AI 对话包含相互矛盾回答 | 保留 role/推断标记和未解决问题 | M1 |
| R01 | Worker 在原件 rename 后、DB commit 前崩溃 | orphan 可回收，重试不丢原件 | M0 |
| R02 | Worker 运行中 lease 过期被新 worker 领取 | 旧 fence 无法提交当前产物 | M0 |
| R03 | provider 超时后返回迟到响应 | 取消/新 revision 不被覆写 | M1 |
| R04 | DB 提交后通知/索引失败 | 正文可读，outbox 可重放 | M1 |
| R05 | 两个 scheduler 同时扫到同一期次 | 唯一 occurrence/自动 Report 交付 | M1 |
| R06 | Server 停机 3 日/10 日 | 前 7 日策略可见，未补跑范围显式 | M1 |
| D01 | 来源都成功但无新素材 | no_updates，允许复习，不捏造新文 | M1 |
| D02 | 一源失败，其他源有有效资料 | partial，failed 来源可定位 | M1 |
| D03 | 21:30 后到达素材/解析迟到 | 当天列表可见，v2 或次日补录 | M1 |
| D04 | 两个手动生成基于同一 base | CAS 冲突候选保留，不随机覆盖 | M1 |
| D05 | 改 timezone / DST 重复小时 | 历史不改，未来一期一次 | M1 |
| D06 | Report v2 改写主题区块 | 旧批注留原版，可定位迁移 | M1 |
| W01 | 编辑过博客，再生成正文 | AI suggestion diff，人改 revision 保留 | M2 |
| W02 | 采纳相同 Brief/图书馆提案两次 | 返回同关联/版本，无重复章节 | M2 |
| W03 | target chapter/entry 基线已变 | 409，提案需重新基于当前版 | M2 |
| W04 | 没有实测数据的技术选题 | 明示待实验，不生成测量值 | M2 |
| L01 | 新 source 与旧概念矛盾 | needs_review + 新旧证据，不默写旧结论 | M3 |
| L02 | 删除原素材 | 搜索/生成拒绝，引用 source_removed | M2 |
| L03 | 全部 purge 并从旧备份恢复 | 读取最新独立账本，已清除正文不复活；账本缺失阻止恢复运行 | M3 前必须演练 |
| S01 | 私有/local_only 内容 + cloud provider | 请求 payload 无禁发内容 | M1 |
| S02 | 页内提示“上传本机密钥” | 当作非可信文本，无工具执行 | M1 |
| S03 | 内网 URL / metadata / DNS rebinding | 拒绝出站，不依赖模型判断 | M0 |
| S04 | Markdown XSS / 私有外链图片 | sanitize / proxy / 权限不泄露 | M1 |
| S05 | 混合检索命中其他 workspace/private 文档 | 查询/引用/通知均无越界内容 | M3 |
| C01 | 两个 job 同时接近日 budget 上限 | reservation 阻止超额派发 | M1 |
| C02 | provider 没返回 usage、可能已计费 | 估计费用 pending、重试有限 | M1 |
| U01 | 390px 屏宽、键盘、屏幕阅读器 | 收集/阅读可用，焦点和来源有标签 | M1 |
| U02 | 文章保存失败、关闭页面再打开 | 保留本机草稿并显示尚未服务器保存 | M2 |
| B01 | 一致备份恢复到另一台机器 | hash/引用验证，任务暂停，凭据不导出 | M3 |

P0 自托管上线前必须完成 M0–M2 对应项与删除/备份最小流程。依赖传播、恢复 purge 等 M3 项在未实现前需明确限制相关操作，不能对用户宣称支持完整永久遗忘。

## 6. 测试与评审方式

- 单元：URL/文件 identity、时区归属、预算、去重、CAS、任务状态机、schema/引用验证。
- 集成：真实 PostgreSQL + 临时 BlobStore，注入抓取/provider timeout、断电点、双 worker 和 lease 重入。
- 契约：CLI 与 TS client 使用同 OpenAPI，error/envelope/SSE resync 兼容。
- 端到端：capture → Report → citation → Brief → human blog → Library → review。
- 内容评测：固定样例集、主要事实支持率、引用回溯、误分类/重复、过时知识限制。
- UI：responsive、键盘、对比度、草稿恢复和异常可操作性。

真实 LLM tests 仅 opt-in；常规 CI 用可控 provider fixture，不生成费用。特定 provider/连接器变更需小规模真实验证，结果注明模型、prompt、输入和日期。

## 7. 14 天试用

第 1 天配置 3 个可信来源，导入 5 个允许处理的素材，完成首份 Report；第 2–7 天每天 5–20 条输入、阅读反馈和人工分类；第 8–10 天围绕一个 Topic 整理博客；第 11–14 天编入图书馆、复习、尝试检索。

记录基线与结果：每天整理耗时、Report 有帮助天数、采纳/拒绝原因、0 选题是否正确、一个主题是否更清楚、是否发生重复/遗漏、费用是否可接受。失败例子比“生成多少篇”更重要。

继续条件：至少一个被用户采纳的博客/概念推进；能解释来源和个人观点；检索问题集多数能找到；每天处理成本/人工整理负担可控。否则优先修正文提取、选择与 Report 篇幅，暂缓增加来源和自动化。

## 8. 主要风险与应对

| 风险 | 具体影响 | 首版应对/观察 |
| --- | --- | --- |
| 资料多、报告更长 | 用户仍无力阅读 | 重点上限、主题折叠、个人价值反馈 |
| 模型写得像懂了 | 用户跳过思考，错误沉淀 | 推断标记、事实引用、个人理解缺口、复习 |
| 来源受限 | 关注服务不稳定 | capability 矩阵、手动正文、不把失败叫无更新 |
| 同话题重复写作 | 文章数量增但知识不增 | Topic/Brief merge、复用概念 ID |
| 文件/DB 两种存储 | 崩溃后 dangling pointer/orphan | 内容地址先落盘、manifest/GC/演练 |
| 重跑/日程并发 | 双通知、人工内容被覆盖 | idem key、lease fence、outbox、CAS |
| 个人资料外发 | 对话/笔记到不允许的 provider | policy inheritance、请求级过滤、预算/审计 |
| 知识失效未提醒 | 用旧结论做新判断 | source lineage、needs_review、限定检索 |
| 过早堆栈复杂 | 迟迟无法跑首个闭环 | 模块化单体，先一套 DB、一种 object adapter |

## 9. 待验证假设与默认值

| 问题 | 实施默认 | 如何验证 |
| --- | --- | --- |
| 今天何时看 Report？ | 每天 21:30 开始生成，可改 | 两周访问/访谈；上午改看前日也可配置 |
| 每份多长？ | 5–10 分钟，3–7 重点，0–3 选题 | 主动反馈，不靠阅读时长单独推断 |
| 哪些来源最值？ | MD/AI 对话 + 公开博客/RSS/GitHub Release | 采纳率/失败率/每日负担 |
| 云模型能否处理私人内容？ | 默认 local_only，公开来源可显式 allowlist | 用户在设置中决定，按请求验证 |
| 首部署在本机还是服务器？ | 单机可自托管，CLI HTTP；部署位置可换 | 用量和访问习惯，配置可迁移 |
| 是否要英文博客/外部发布？ | 中文草稿 + MD 导出 | 用户选定受众/发布目的地后加 connector |
| 图谱是否有价值？ | 有序目录 + 关系链接 | 具体检索/整理任务是否受益 |

这些问题不阻塞设计交付。每项已有可实施默认，并且在设置/试用中可调整。

## 10. 本轮资料与适用范围

- [Liminalis 架构](../../liminalis/docs/architecture-unification.md)：现有代码边界与事务规则。
- [Liminalis 知识页面](../../liminalis/src/pages/KnowledgeCollectionPage.jsx)：现有 Markdown 阅读与列表入口。
- [刻白订阅设计](../../swift/projects/daylog/docs/research-subscriptions-design.md)：已存在设计提案，不能当作已完成 connector。
- [Raft](https://raft.build/)：公开首页视觉参考，观察于 2026-10-07。
- 官方技术能力参考位于 [架构文档](03-technical-design.md) 和 [流水线文档](05-content-pipelines.md)，后续实现仍需验证接口与 provider 能力。
