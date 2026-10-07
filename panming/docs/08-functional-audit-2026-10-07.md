# 盘铭 v0.2 · 功能与可靠性审计

> 本文是 v0.2 的历史审计快照；对应问题已在 v0.3 修复并回归，当前状态见 [v0.3 交付说明](10-v03-reliability-release.md)。保留原始失败证据，不改写当时结果。

2026-10-07。对象是当前本机原型，不是 01–06 中尚未交付的目标系统。本轮仅新增测试、隔离测试工具和文档，没有修复业务代码或改变产品行为。

## 1. 结论

**正常闭环可用，但还不适合把它作为唯一的长期知识存储。** 最优先的问题不是页面数量，而是人工草稿、版本引用和导出的可信度。

- 自动测试总计 53 个用例：41 passed、12 xfailed。
- 12 个 xfailed 是已经复现、仍未修复的缺陷，不是通过。强制按正常断言运行会出现 12 failed。
- 浏览器另复现 5 个问题；合计 17 个：P1 7 个、P2 8 个、P3 2 个。
- 本轮范围未发现 P0；这不表示已完成渗透测试或生产安全认证。
- Ruff、TypeScript 检查与生产构建通过。依赖扫描未报告已知依赖漏洞，不能代替应用逻辑审计。

优先级定义：P1 = 人工内容丢失、主流程阻塞或核心版本语义失真；P2 = 异常处理、可靠性、内容质量或资源管理问题；P3 = 契约与体验问题。这里只评价当前本机用途；开放公网属于另一组上线门槛。

## 2. 方法与隔离

自动测试使用真实 PostgreSQL 17，每个测试创建独立 `panming_test_<uuid>` schema 和临时 blob 目录。测试结束删除 schema；合成原件由 pytest 临时目录保留/清理策略管理。浏览器使用 `scripts/audit_server.py`：在 127.0.0.1:5178 启动单独 schema/临时原件的同一套前后端，退出后清理。正式工作台 8788、用户素材、运行凭据均不修改。

审计采用原件不可变、证据可追溯、历史不可漂移、人工采纳受保护的知识库原则（参考 karpathy-llm-wiki）。这里检查盘铭的业务对象，不初始化或重排另外的 raw/wiki 目录。

覆盖范围：Capture/Upload、原件/版本、Report、Blog、Proposal/Entry、Review、Source/Settings、CLI、HTTP 边界、并发、数据库回滚、小规模数据增长、桌面与移动端、Markdown 安全渲染。

**未覆盖**：真实 LLM/订阅连接器（未实现）、断电/磁盘满/数据库故障注入、生产压力与长期 soak、完整备份恢复、跨平台安装、完整 WCAG/多浏览器矩阵、外网认证和授权、第三方平台真实账户。不要把下面的结果推广到这些场景。

## 3. 已验证的正常路径

| 范围 | 实际验证 | 结果 |
| --- | --- | --- |
| 收集 | 同 key 重试、同 key 不同正文、8 路并发同请求 | 同请求只有一个素材，不同正文 409 |
| 输入边界 | 超长标题/正文、未知类型/主题、危险协议、带凭据 URL | 基本拒绝为 422；无素材元数据写入 |
| 文件 | 二进制、空文件、50 万字符以上、UTF-8 BOM、8MiB+1 | 不可解析原件字节不丢失；超限 413 |
| 素材修订 | 空正文、过期 revision、不存在原件版本 | 422/409/404；已有原件不变 |
| Report | 未来日期、v1/v2、前日补录、前日素材新正文 | 范围校验、历史保存与跨日纳入正确 |
| 博客 | 6 路并发保存同 revision | 一次成功、五次 409，不覆盖赢家 |
| 入馆 | 未确认博客、失效提案、5 路重复采纳 | 受保护，重复采纳只有一个 Entry |
| 冻结 | 博客修改之后读取已采纳 Entry | Entry 正文不会自动改变 |
| 复习 | clear/fuzzy/forgot | 分别下一次 30/7/3 天，记录持久化 |
| 配置 | 手动 Source、Settings 保存/修订 | 保存成功，不假装开启后台任务 |
| 安全边界 | 非法 Host、非 loopback client、跨站 Origin | 400/403；正常页面有 nosniff、DENY |
| CLI | note/file/url/report/export/help、缺失文件/对象、网络错误 | 与实际隔离 API 联通；基本错误不静默成功 |
| 存储 | 并发同 blob 写入、数据库事务主动回滚、重新创建 App | 内容寻址去重；元数据/修订一起回滚；重开可读取 |

浏览器实际操作包括：体验数据 → 仅链接归档 → 晚到提示 → Report v2/partial → 历史 v1 → 实际下载 → 从旧报告写作 → 修改/保存/确认 → 采纳入馆 → 素材新正文 → 旧证据对照；另验证文件上传、搜索、手动 RSS 清单和设置刷新。

390×844 视口验证了素材列表无横向溢出、折叠导航不可见、展开和页面切换可操作。这不是全部移动页面的可访问性验收。

Markdown 预览测试中：原始 script/img HTML 作为文字展示，预览区 script/img 节点均为 0，javascript 链接 href 被清空，远端图片显示占位。未执行危险链接或访问外部素材站点。

## 4. 缺陷清单

### 4.1 自动复现（PM-A）

用例均位于 [test_audit.py](../tests/test_audit.py)。`xfail(strict=True, raises=AssertionError)` 只认可预期断言失败；修好后 XPASS 会令测试失败，要求同步移除标记。基础设施异常不会被当成预期失败吞掉。

| ID / 优先级 | 触发与实际结果 | 根因 / 代码坐标 | 修复验收 |
| --- | --- | --- | --- |
| PM-A01 / P1 | 同一主题 31 份有正文素材 → Report 选题包含 31 个 ID → 创建博客返回 422 | [BlogRequest](../src/panming/app.py) 限制 30；`build_report()` 不限制选题。产品设计负载是每日 10–50 条，处于正常使用区间 | 31/50/100 份可选择子集、拆分或分批形成选题；前后端上限一致，入口可完成 |
| PM-A02 / P1 | 生成 v1，添加素材生成 v2；请求 export?revision=1 仍含 v2 素材 | `export()` 只读取 head；Web 历史页也没有传 revision | 页面显示版本、实际导出版本完全一致；不存在版本 404 |
| PM-A03 / P1 | 二进制原件上传成功；通用 export 返回 200 和空字节；CLI 写出空文件并宣布成功 | `export()` 取 content；`cli.export()` 总是按文本写。Web original 接口本身保留原件，不是服务器原件已丢失 | CLI 区分原件/Markdown，二进制和 BOM 精确导出；不支持时明确拒绝，不能空文件成功 |
| PM-A04 / P2 | 纯空白标题和空笔记被 API 以 200 保存 | Capture 只限制字符串长度；Web 的 trim 校验未进入共享 API | strip 后标题非空；笔记正文非空；仅链接输入仍允许待补正文 |
| PM-A05 / P2 | 正文含 U+0000 → 500 | PostgreSQL JSONB 不接受 NUL；未做业务层校验 | 422 可读错误，无半完成元数据，无无引用 blob |
| PM-A06 / P2 | Origin=http://localhost:not-a-port → 500 | `loopback_guard()` 中 parsed.port 抛异常，发生在路由异常处理之外 | 畸形 Origin 稳定拒绝 403；合法写入不受影响。该用例没有证明可绕过 Origin 限制 |
| PM-A07 / P2 | URL=https://[ → 409，提示刷新比较版本 | `checked_url()` 的 ValueError 被全局版本冲突 handler 错认 | 畸形 URL 为 422；只有 CAS 冲突返回 REVISION_CONFLICT |
| PM-A08 / P3 | proposal blog_id 为数组 → 404，而不是类型校验 422 | Proposal/Accept 使用裸 dict，与其余 Pydantic DTO 不一致 | 全部写接口 typed DTO；非法字段、类型、枚举有稳定错误契约 |
| PM-A09 / P2 | 两窗口首次保存设置，同时读到不存在的 settings → 一个 200、一个 500 | FOR UPDATE 不能锁住不存在的行；固定 PK 并发 insert 竞争 | advisory lock/upsert/预创建设置；并发初始化没有 500，最终 revision 可解释 |
| PM-A10 / P2 | Markdown 使用 ~~~ 围栏，代码被当作自然语言证据摘录 | [excerpts()](../src/panming/content.py) 只切换三反引号状态 | 反引号/波浪线、缩进与嵌套围栏、代码为主素材有正确解析；行号仍正确 |
| PM-A11 / P2 | Report 读完素材后另一个 capture 提交；其 created_at 在 cutoff 前，却不在 sources | `cutoff_at=now()` 在读取材料以后赋值；无输入水位。运行说明已提示此原型限制 | cutoff 对应真实 manifest 水位；并发捕获可明确归入本版或晚到版本，不声称覆盖未包含输入 |
| PM-A12 / P2 | 有正文但主题非法，返回 422；磁盘已留下一份没有元数据引用的 blob | `capture_material()` 先 put_blob 再校验 topic | 确定性校验在落盘前；提交失败孤儿有安全 GC/恢复账本 |

PM-A09、PM-A11 使用事件同步固定竞争窗口，不靠偶然 sleep 来碰运气。它们说明特定交错确实失败，不代表每次普通操作必然发生。

### 4.2 浏览器复现（PM-W）

坐标主要在 [main.tsx](../web/src/main.tsx) 的 `BlogEditor`、`MaterialModal`、`App.newBlog` 和来源路由，以及 [blog_body()](../src/panming/content.py)。这些用例本轮通过实际浏览器执行并留证，还没有变成 CI 浏览器测试。

| ID / 优先级 | 复现步骤 | 实际结果 / 根因 | 验收 |
| --- | --- | --- | --- |
| PM-W01 / P1 | A/B 打开同一博客 v1；A 保存 v2；B 写自己的正文并冲突；A 确认成 v3；B 刷新 | **B 未保存正文消失**。所有窗口共享 `panming.draft.<blog_id>`；A 的 dirty=false effect 删除 B 的草稿 | 草稿有 editor/session 标识、base revision、所有权与内容 hash；一窗口不能删除另一窗口草稿；刷新恢复全部分支 |
| PM-W02 / P1 | A 保存 v2；B 以 v1 保存返回 409；按提示刷新再保存 | 仍然 409。localStorage 中 baseRevision 一直为 1，没有比较、合并、另存、放弃入口 | 保留本机内容，展示 base/local/server 三方差异；用户明确处理后以最新 revision 保存；禁止自动强制覆盖 |
| PM-W03 / P1 | 从素材 v1 创建博客并入馆；素材改成 v2；点 Entry 正文的“查看原始素材” | 打开 v2；旁边“原始证据”仍正确打开 v1。正文 hash 链接只有 ID，没有 revision | 正文、证据抽屉、Markdown 导出使用统一 SourceRef；都绑定相同 revision/hash/anchor |
| PM-W04 / P1 | 在旧 Entry 的证据抽屉看到素材 v1，点击“整理成博客” | 新博客实际使用 v2，未说明来源切换。只有 Report 页面传 report_revision；其他入口只传 material ID | 请求包含明确 SourceRef 列表；要切换最新版必须提示；旧证据写作引用不漂移 |
| PM-W05 / P3 | 在素材列表点“导入文件” | 默认打开“文字/笔记”表单，需要再选文件。CaptureModal mode 总是 note | 导入入口默认文件模式；全局收集默认笔记；键盘/关闭状态正确 |

浏览器关键证据（运行态，gitignored，仅本机可见）：

- `data/audit-2026-10-07/historical-report.jpg`：页面 v1；`downloaded-report.md` 实际版本 2。
- `draft-conflict.jpg`：刷新后仍提示“内容版本已变化”。
- `draft-lost.jpg`：B 刷新后正文变成 A 内容，B 草稿不再出现。
- `inline-source-drift.jpg`、`source-write-drift.jpg`：旧证据入口打开/写作使用 v2。
- `mobile.jpg`：390px 素材列表验证。

## 5. 规模与依赖检查

[test_scale.py](../tests/test_scale.py) 使用 250 份合成素材，每份 2088 字符，再生成一份 Report。一次本机探针：采集+Report 900.7ms；bootstrap 26.2ms；响应 1,771,390 字节（约 1.69MiB）。这使用进程内 TestClient 和同一测试事务，**不是 Web 页面首屏耗时、生产 P95、网络带宽或并发吞吐**。

结果说明小数据量暂未出现接口超时，但 bootstrap 已重复携带原文和 Report 快照；`Store.list()` 全量读取，capture 去重扫描全部素材。需要分页、摘要/详情分离和数据库 fingerprint 索引。后续单独测 1k/10k 素材、不同日期报告和长文档，不能由 250 份推断线性扩展。

依赖检查日期为本审计日：

- `uvx pip-audit --path .venv/lib/python3.12/site-packages --format json`：第三方包未报告已知漏洞；本地 panming 非 PyPI 包被跳过，由本轮代码审计覆盖。
- 默认 npm 镜像审计接口返回 404，不能算成功。改用单次 `--registry=https://registry.npmjs.org` 重试后，npm audit 返回 0 个已知漏洞；未改变全局 registry、未升级依赖。
- Starlette TestClient/httpx 有弃用警告；不阻塞当前测试，但要纳入依赖兼容性维护。

## 6. 风险和功能缺口：不能混成“已复现漏洞”

以下来自代码检查或已明确的未实现边界，本轮未完成故障/生产验证：

1. **备份与恢复**：没有可验证的 workspace 导出/恢复；逐篇 Markdown 导出不包含完整关联/修订。正式存知识前需补最小备份闭环。
2. **访问边界**：无账号/token/RBAC；loopback 只是本机原型范围，不能据此把 bind 改成 0.0.0.0 或直接走公网代理。
3. **任务可靠性**：请求内同步归纳，无 durable queue/租约/outbox；未调用 LLM，因此也未验证费用/取消/外发策略执行。
4. **草稿存储异常**：localStorage.setItem/removeItem 没有异常处理；禁用存储/配额满可能破坏编辑体验，尚未实际注入配额故障。
5. **服务启动竞争**：run.sh 在 uvicorn 成功绑定前写 server.pid；二次启动失败可能覆盖有效 PID。未在正式服务上复现，避免干扰现有运行。
6. **上传资源上限**：业务 8MiB 检查在 multipart 解析后；仍需请求体、并发、临时 spool 总量与限时防护，未做恶意大请求压力测试。
7. **补录提示**：Web lateCount 只比较 selectedDate 当日素材，前日素材新正文可能没有“未纳入”提示；API 跨日补录通过。需 UI 统一后端覆盖账本。
8. **内容质量**：只有三个静态主题、固定追问、三个开头摘录；没有事实/推断/个人观点区分、来源冲突检测和跨日语义新意；可把未补完的框架人工确认入馆。
9. **知识维护**：图书馆目前复制文章，不支持条目修订、章节重排、合并提案、来源变更影响通知、完整回收站与遗忘。

## 7. 复跑与门槛

```bash
cd /Users/lism/xwork/xlab/panming
./scripts/check.sh
# 显式看见已知缺陷，不把 xfailed 当作验收通过：
.venv/bin/python -m pytest -q -rx
# 修复验收模式；当前版本预期非零退出、12 failed：
.venv/bin/python -m pytest tests/test_audit.py --runxfail -q --tb=short
# 小数据量探针（输出合成数据指标）：
.venv/bin/python -m pytest tests/test_scale.py -q -s
# 浏览器人工复跑；Ctrl+C 清理隔离 schema/原件，不停止正式数据库：
.venv/bin/python scripts/audit_server.py
```

v0.3 退出门槛：全部 P1 关闭；相应 strict xfail 移除并变成通过；输入错误无 500；PM-W01–04 加入持续浏览器回归；完成最小备份恢复演练。迭代选择见 [下一轮产品与技术路线](09-iteration-roadmap.md)。
