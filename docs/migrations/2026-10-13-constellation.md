# Constellation 拆分迁移记录（2026-10-13）

Snapshot note: the five-project owner decision on 2026-10-15 supersedes earlier
retention statements for FragmentTutor, Umbra, subway-game, llm-runtime and
py-academic. Historical evidence below remains tied to its stated commit; see
[the retirement record](2026-10-15-five-project-retirement.md).

## 结论与状态

**三个独立项目已发布到各自 main；xlab 源码清理 PR #21 已于 2026-10-13 17:29:46 UTC 合并。**
合并提交为 [`25d8a76`](https://github.com/LiShuMing/xlab/commit/25d8a76fbcc083c869b0af0538e409fcfc791749)，
见 [PR #21](https://github.com/LiShuMing/xlab/pull/21)。以下候选、提案及当时状态记录保留为历史证据，不能解读为当前尚未合并。
原始工作 checkout 保持只读，清理在新建隔离 checkout 中按精确文件白名单执行。
生产部署、真实数据迁移、付费/线上集成未执行，也不是本次代码提取的验收门槛。
三个目标继续保持私有，根知识库、FragmentTutor 和私人/运行数据保留。

源仓库：<https://github.com/LiShuMing/xlab>。
提取与清理基线：`fd15e65059ff7d0d01ed48b6347cd75881fb4b36`。
2026-10-13 17:08 UTC 再次回读 GitHub `main` 与
[`backup/pre-constellation-cleanup-2026-10-14`](https://github.com/LiShuMing/xlab/tree/backup/pre-constellation-cleanup-2026-10-14)，
二者均为上述完整 SHA。分支名按用户指定保留，实际核验日期为 10 月 13 日 UTC。
这份远程备份是在任何源码清理之前创建并验证的；后续若 main 前进，须重新分类 delta，不能覆盖新修改。

### 已合并目标与发布后 CI

| 目标 | 已验证 main SHA | 发布后 CI |
| --- | --- | --- |
| Lyra（PR #1 已合并） | `6a16ad95014e0dd362586f1345f884e041a06284` | [三项通过](https://github.com/LiShuMing/lyra/actions/runs/38435521042) |
| Carina（脱敏 PR #2 已合并） | `9660052d544306ab53a0921376e2b4d9b0cbe20a` | [通过](https://github.com/LiShuMing/carina/actions/runs/38435575616) |
| Vela | `4d2d65c05a309b7f49e500d7b25206a34ae73853` | [七项通过](https://github.com/LiShuMing/vela/actions/runs/38425931473) |

三个 main 在本次清理开始时重新回读一致；合并树与独立审查、测试的脱敏候选完全相同。
以下候选历史记录保留作为过程证据，不代表当前未合并状态。

## 源码映射与保留边界

以下数量是当前脱敏提取清单中的已跟踪源文件数，不是修改后文件总数。各目标仓库使用全新
Git 历史，提取清单记录原始路径、目标路径和源字节 SHA-256；后续修复由新提交记录。
最初 546 项清单已经源哈希复核；脱敏后 Lyra 增加三项排除，最终清单现为 **543** 项。
重新复核全部 543 项源哈希与固定基线一致、源路径唯一、对应目标文件全部存在。
逐文件新清单是源码清理白名单的上限，旧的 546 项清单不再适用。

| 源路径（xlab 根目录相对路径） | 私有目标仓库与目录 | 提取数量 | 状态与精确清单 |
| --- | --- | ---: | --- |
| `liminalis/` | [Lyra](https://github.com/LiShuMing/lyra) 根目录 | 362 | `EXTRACTION.json`；七项排除，不代表整个目录可删除 |
| `panming/` | [Carina](https://github.com/LiShuMing/carina) 根目录 | 56 | `docs/source-manifest.json` |
| `python/projects/tech-radar/` | Carina `modules/tech-radar/` | 48 | 同上；采集器和核心业务仍有独立数据边界 |
| `optimizer-learning/` | [Vela](https://github.com/LiShuMing/vela) `optimizer/` | 19 | `docs/source-manifest.json` |
| `cc/projects/query-engine/` | Vela `execution/` | 33 | 同上 |
| `cc/projects/kv-store/` | Vela `storage/` | 25 | 同上 |

明确未迁移或仍保留：

- Lyra 共七项源文件排除，不复制它们的内容；源端继续保留。发布历史各阶段采用
  通用配置模板和脱敏文档；`EXTRACTION.json`、`SANITIZATION.json` 记录来源与变换前后
  校验和。新建空的启动快照不代表原始内容迁移。
- xlab 根 `docs/` 知识库保留。Lyra `docs/content-migration.json` 清点 380 份引用文件，
  没有将它们打包搬走；默认只有新建欢迎页。可选 `LYRA_CONTENT_ROOT` 会把所选内容
  编入前端资源，接入前必须逐项审查，不能指向未经筛选的私人资料。
- `rust/projects/fragment-tutor/` 保留在 xlab。Carina 没有交付该桌面应用、数据库或
  无损 SRS 适配器；核心 3/7/30 天分级不等价于原 interval/ease/streak/history。
- Collector 的 signals 可做离线传输，但文章/发布历史和二进制资产尚未完整转换；
  不能将 signals 适配器的测试通过描述成整个工作流的数据迁移完成。
  本次仅迁移已提交代码，不以真实历史/资产迁移或 FragmentTutor 完整合并为前提。
- 本次范围以表中六个源路径及逐文件清单为准。其他实验项目、第三方子模块、
  根知识库、运行目录、配置密钥、真实数据库、资产和本地未跟踪文件均不属删除范围。
- 未授予新许可证。Vela 已去除没有依据的 TinyKV MIT 声明；公开再分发前仍需
  所有者解决许可来源问题。目标仓库目前按私有仓库处理。

## 本地候选快照与证据

本文汇总各候选 `docs/migration.md` 中的执行记录；本次文档工作复核清单和文档，
未把整套应用测试重新执行一遍。下表为文档整理时读取的本地 HEAD，**不是远程 SHA**。

| 仓库 | 本地 HEAD | 首次提取提交 | 验证定位 |
| --- | --- | --- | --- |
| Lyra | `438d756bd23341b9e6a4ba8e7ede4df725dbed87` | 脱敏历史，以新清单为准 | 候选 `docs/migration.md` 最终附录 |
| Carina | `43158f0fc6103f5d9bc41a3fac6a02428541ccb5` | 脱敏历史，以新清单为准 | 候选 `docs/migration.md` 验证账本 |
| Vela | `0a8cb9dc3b55dbea9fb0124ddb1c14dd8d73163e` | `9671913` | 候选 `docs/migration.md` 验证与独立审查 |

脱敏历史审查：Lyra 六个提交、474 个唯一 blob，362 项源条目和七项排除；
Carina 代码历史 tip `c9369417bbd108bcb88045592c80142a241ff4a9` 的十一个提交、
192 个唯一 blob，104 项原始源哈希及七项脱敏提取哈希；之后增加一项仅文档提交。
配置模板和文档的变换前后校验和用于区分原始来源与可发布字节；完整历史逐阶段复核，
不能只检查最终 HEAD。Lyra、Carina 新远程文件树与对应精确 HEAD 的 CI 均已核验通过。

每个目标均有自己的 README、AGENTS.md、构建/依赖清单、格式化配置、测试和迁移记录。
它们不依赖旁边存在 xlab checkout；新环境仍需按各 README 安装工具和锁定依赖。
历史候选发布核验记录（协调任务提供；当前 main/合并状态见上表）：

- Vela 实现快照：`5ed9fc68d6e1ca1580d051397ce41d611f12a18b`。
  文件树 `8165e0eb516632bf681458cb3c8e46b359590255` 与本地实现快照 `410aaa9` 完全一致；
  远程 AGENTS.md、迁移文档和 CI 配置已回读。
  [实现提交 CI](https://github.com/LiShuMing/vela/actions/runs/38425584645) 七项 job 全部成功：
  Python 17、根 CTest 18、独立 execution 17、storage 22 用例、公共头文件 22、
  TSan 18、ASan/UBSan 18 及格式检查（用例数不等于 job 数）。
- 后续仅文档更新的 Vela `main`：`4d2d65c05a309b7f49e500d7b25206a34ae73853`，
  文件树 `f32bbb5e2a83a69e58cb1e84c7301faa79408496`；新增 `docs/publication-map.json`
  并记录实现提交 CI。[最终文档提交 CI](https://github.com/LiShuMing/vela/actions/runs/38425931473)
  七项 job 也全部成功，独立于先前实现提交的检查结果。
- Vela 分阶段上传保留了五个快照，但提交元数据使远程 SHA 与本地 SHA 不同。
  本地/远程映射：`9671913` → `52f32f8`（提取），`3e48ddf` → `d059c15`，
  `6d60d9b` → `6fe9109`，`9d5cdab` → `944d76b`，`410aaa9` → `5ed9fc6`（最终）。
  比较文件树而不是假定 SHA 相同；远程回退应使用对应远程提交。
- Lyra 私有仓库 [draft PR #1](https://github.com/LiShuMing/lyra/pull/1)：
  脱敏候选远程 HEAD `c68508384b725ae50e209fbfa665893540442344`，
  文件树 `fe3ac88602b8d7e5f2fc3a3d3abea52aad084b13` 与审查后的本地最终候选完全一致。
  共 386 个文件、六个分阶段提交；尚未合并，`main` 保留引导内容。
  [PR CI](https://github.com/LiShuMing/lyra/actions/runs/38434080145) 的 app、context、postgres
  三项 job 对上述精确 HEAD 全部通过。
- Carina 私有仓库 [draft PR #2](https://github.com/LiShuMing/carina/pull/2)：
  分支 `migration/sanitized-import`，远程 HEAD `f647ea97802ad4845bbc23d336140c922863b8d1`，
  文件树 `31f83ff28e6e62ab4b070ed11d81a22ede7a2bfd` 与本地最终候选完全一致，
  共十二个分阶段提交。[新 HEAD CI](https://github.com/LiShuMing/carina/actions/runs/38434263019)
  已成功，对应上述精确 HEAD。
  `main` 仍保留引导内容；原 PR #1 已被替代、未合并，不纳入本次候选验收。

以上为合并前的候选证据。当前三个 main 已验收，源码清理提案的验证记录见下文。

### Lyra：应用边界与可靠性修复

- 前端支持任意命名的外部内容根；后端快照定位基于项目根。保留兼容配置，
  Go module/import 同步更名，npm 锁文件采用公共源且保留原版本与完整性值。
- 删除任意四位 PIN 登录；凭据只接受 POST body。浏览器身份由服务端独立 HMAC 密钥
  签名，拒绝无签名或篡改值；仍是可信单所有者访问，不是多租户隔离认证。
- Radar 取消任务后保持锁所有权直到工作线程结束；公共刷新入口统一使用 POSIX flock，
  修复取消/重入竞争、跨次运行元数据污染和过远未来日期绕过缓存问题。
- PostgreSQL upsert 保留来源并集；Go 的可选外键空字符串改为 NULL，测试数据独立化。
  部署/健康检查失败正确返回非零，Compose 数据库/缓存端口绑定 loopback。
- 保留共享 business_uow、架构守卫、代理重定向、多 Cookie、Unix socket 等既有行为。

原候选已执行：247 个 Python 测试（包含临时 PostgreSQL 用例）、3 个前端测试、生产构建、
Go 全包 uncached race（包含 PostgreSQL）与 vet、Alembic 临时数据库升/降/再升级、
Ruff/Prettier/Go 格式和 shell/空白检查。独立 clone 无数据库运行明确为 246 通过、
1 项 PostgreSQL 跳过；不将跳过算成通过。另验证任意目录名内容根和小型 golden fixtures。
Python 3.12 为实际验证版本；已有弃用和 Browserslist 数据陈旧警告未被掩盖。
脱敏新候选另已通过 248 个 Python 测试（临时 PostgreSQL）、Go race/vet、
三个前端测试、生产构建与格式检查；上述新远程三项 CI 已通过。

未执行：真实 OAuth、模型计费请求、邮件/交易、生产部署、真实用户数据库/资产迁移、
认证后的生产浏览器流程。POSIX 锁并不提供 Windows 等价实现。

### Carina：证据不可变与离线适配

- 独立 Python/uv 工作区和两个前端；保留 `panming` 导入/CLI 与 `PANMING_*` 兼容，
  增加 `CARINA_*` 配置别名。Origin 检查按真实 scheme/host/port 和明确开发端口匹配。
- 仅元数据修订保留原证据引用；原始内容改变不继承旧证据。Collector schema v4 保存
  完整文章快照/校验和；历史缺快照记录明确为 `legacy_unverified`，不伪造历史证据。
- signals SQLite 只读导出、事务性核心导入已经可执行，保留原 JSON、关联、修订和回执。
  覆盖重放、并发、预验证、去重、失败回滚/重试与备份恢复的合成测试。
- 离线 fixture 采集无需发现真实 OpenCLI；依赖与格式化工具锁定，不启用外部发布。

已执行：独立 clone 锁定依赖安装、`scripts/check.sh`、真实临时 PostgreSQL 上
199 个核心 Python 测试、17 个采集器测试、5 个前端测试、两个 TypeScript 检查/生产构建、
53 文件 Ruff 与两个前端的 Prettier。独立审查覆盖适配器、可靠性、备份和源清单。
完整验证基于 `29dce12`；后续迁移账本/链接变更为文档。已有 deprecation 和损坏 ZIP
测试警告不影响结果。早期安装/环境/数据库进程失败经过修复后重跑，不能抹去失败记录。
脱敏新候选的锁定依赖安装及上述测试、lint/format、两个前端类型检查和构建组件均通过；
最后的采集器构建单独重跑成功，不将分段完成描述成一次不中断的 aggregate 运行。
另通过 demo TOML 解析、仓库相对输出路径及应用代码未变化的比较检查。

未执行：真实 LLM、线上采集/发布、Tauri 桌面、私人数据导入/恢复、部署和浏览器交互 QA。
FragmentTutor 的 SRS/history 原子性和凭据 fallback 是外部审查发现，不是本仓库已修复项。

### Vela：教学型优化器、执行与存储

- 执行模块修复跨批聚合计数、TopN 键/值错配、join 游标与重复行乘积、递归 Prepare、
  重复执行状态、输入形状、null/selection 缓冲增长、哈希容量与独立头文件包含。
- 存储修复空/反向迭代、零字节操作、placement-new 生命周期、分配对齐/溢出和内存指标
  同步。迭代要求外部同步；不声称 lock-free、快照、持久化或完整数据库语义。
- 优化器修复 memo 结构身份、谓词/限定列下推、成本、DP 子集枚举、pruning、别名与
  物理表身份；非法/不支持 SQL 显式拒绝。审查进一步修复复用 null 位、SUM/COUNT 溢出
  和浮点 signed-zero 哈希一致性。Join 随机差分 120 轮覆盖重复/负键和大结果集。

已执行：根 Debug CTest 18/18（17 个 execution 条目及含 22 用例的 storage 条目），
独立 execution 17/17、storage 22 用例、Python 17/17（安装 SQLGlot 后无跳过）、
22 个独立公共头文件及组合头文件编译、ASan/UBSan 18/18（关闭 leak detection）、
独立 storage TSan 22 用例、格式/lint、可选 benchmark 构建与 SeqPut smoke。
独立 clone `9d5cdab7aed0d0e7d5a7547cc2295085d94e7e89` 验证安装、构建、测试及 checkout 外 CLI；
后续证据提交不改变代码。stdlib-only 优化器运行有两项明确 parser 跳过。

泄漏检查证据需区分环境：本地独立 LeakSanitizer 检查受 ptrace 沙箱限制，未完成。
最终远程 ASan/UBSan 套件 18/18 在默认运行时设置下通过；检查 workflow、日志和 CMake
未发现 `ASAN_OPTIONS`、`LSAN_OPTIONS`、`detect_leaks` 覆盖或禁用配置。
没有额外的 LeakSanitizer 显式启用/自检证据，因此不单独断言独立泄漏检查通过。
这属于验证范围披露，不是远程 CI、其他 sanitizer 检查或本次已提交代码清理的额外门槛。
Debug benchmark smoke 不构成性能比较或吞吐量结论。

## 删除源代码前的联合验收门槛

验收范围是已提交代码的云端独立项目迁移。三个候选共同验收后才执行白名单清理；
生产部署、付费/真实外部集成、真实数据库或资产传输、完整 FragmentTutor 合并、
知识库复制均不属于本次必需验收项。这些边界保留，不用未执行的生产操作阻塞代码验收。

1. 重新 fetch/核对 xlab `origin/main`；如基线后有变化，先分类相关 delta，
   必要时同步候选并重新审查、测试，不能漏掉后续有效修改。
2. 完成三个候选所有将发布提交的隐私审查，再验证各私有远程最终提交、完整文件树、
   清单与对应提交 CI。本记录所列最终候选的远程证据已完成；
   旧候选检查不能代替新候选检查，未知状态不能标记通过。
   当前 Carina 脱敏 PR #2 已合并，发布后 main CI 也已通过。
3. 使用已验证的全新隔离本地 checkout 完成锁定依赖安装、构建、完整质量命令和
   无 xlab 旁路依赖检查，再核对其树与远程目标树相同；无需额外要求当前环境
   无法取得的私有远程 clone。数据库测试只使用明确指定的临时数据库，跳过项单列。
4. 完成各目标独立审查并记录修复/测试对应关系。Vela 本地 LSan 限制与远程默认
   ASan/UBSan 通过保持如实披露，不另设未约定的独立 LSan 自检或豁免门槛。
5. 以已核验的 543 项映射为上限：Lyra 362、Panming 56、Collector 48、
   Optimizer 19、Query Engine 33、KV 25。具体清理计划为删除 536 项，保留两份 `.gitignore`，
   将五份已有 README 改为迁移导航，并新增 Liminalis README 导航。
   543 项映射不等于 543 项删除；禁止整目录递归删除代替逐文件计划。
   保留 Lyra 七项排除的已跟踪文件、根 `docs/`、FragmentTutor、全部运行/未跟踪文件，
   并保留相应忽略规则，防止清理后私人或生成内容失去保护。
   两份原 `.gitignore` 位于 `panming/` 与 `python/projects/tech-radar/`，根忽略保护也保留。
6. 在单独、可审查、可回退的源码清理变更中修复仍存的调用方：
   - 根 CMake 移除 KV/Query Engine 开关和对应 `add_subdirectory`。
   - 退役 Liminalis CI；调整原生构建路径过滤器。
   - 更新 Windows dispatcher 与 `WINDOWS.md`。
   - 更新 README、AGENTS、PROJECTS 中的活动路径路由，以及 TASKS、Go SKILL 的活动工作路由。
   - 导航现指向已验收的三个 `main`，不再使用旧候选或引导分支。
   - 检查剩余根 CMake/CTest、Windows CI 与文档导航，验证清理没有破坏剩余项目入口。

**提案阶段历史状态：当时 draft 包含白名单清理，main 尚未修改。当前已合并，见本文顶部；远程备份仍是清理前的固定基线。**
FragmentTutor、知识库、排除项和运行数据在白名单清理后仍保留。

## 清理提案与验证

- 重新验证全部 543 项源 SHA-256 和目标路径：Lyra 362、Carina 104、Vela 77。
- 精确删除 536 个已跟踪源文件；替换五份已有项目 README，新增 `liminalis/README.md`。
- 两份项目 `.gitignore`、根忽略规则和七项 Lyra 排除文件字节保持不变。
- 单独退役 `.github/workflows/liminalis-ci.yml`，因此整个 PR 的删除数为 537；
  其中 536 是源码白名单，1 是明确审查的过期工作流，不扩大源码白名单。
- 支持修改仅涉及根 CMake、原生 CI 路径过滤器、Windows dispatcher/说明、
  README/AGENTS/PROJECTS/TASKS、Go 导航及本报告。cclab、thread-pool、其他项目与子模块不变。
- 本地根 CMake Debug 与 Release 配置/全量构建均通过（包括可选 benchmarks），各 46/46 CTest 通过。
  使用既有固定版本 GoogleTest/Benchmark 源缓存，没有修改依赖或调用线上服务。
- Windows selector 静态检查通过：仅保留 all/cpp/cclab/thread-pool/rlab/rdb/toydb，
  每个路由对应现存构建清单。当前云端无 PowerShell/MSVC，原生执行由远程 Windows CI 核验。
- 96 个迁移目的地文档链接与已验收目标树匹配；git diff --check 通过。
  逐 blob 对比确认除明确列出的源码/导航/构建变更外，原有跟踪内容保持一致。
- 首次远程运行 [38437060710](https://github.com/LiShuMing/xlab/actions/runs/38437060710)
  的 Windows jobs 在 checkout 阶段因既有 Java 尾空格文件名失败，未执行测试；Linux 构建不受影响。
  稀疏 checkout 重试仍在 Git 索引校验阶段失败。最终由 Linux job 从精确 PR checkout
  打包原生 CI 所需源码，Windows jobs 下载同一 run 的短期 artifact 后执行原构建/测试命令。
  不关闭 Git 安全校验，不修改 Java 文件，Linux C++ 仍使用完整 checkout。
- 远程 Windows/Linux CI 按最终 PR HEAD 单独核验；结果记录在 PR 中，不能以本地通过替代。

## 回滚方案

- 本提案使用独立源码移除提交和配套构建/路由/文档提交；如合并后需回滚，应将这组清理提交
  一并 revert（含所有 CI 修复提交，按提交逆序，最后源码提交），恢复入口和实现的一致性，不重写历史。
- 远程备份 `backup/pre-constellation-cleanup-2026-10-14` 固定在
  `fd15e65059ff7d0d01ed48b6347cd75881fb4b36`。恢复指定路径前先审查清理后的有效修改，避免覆盖。
- 本次不操作真实数据；代码回滚不等于数据库/资产回滚。未来数据迁移须另行核验备份、schema、
  关系/未知字段、时间与 null 语义、幂等性和批准的干净目的地。
- Lyra 临时库 Alembic 测试不是生产回滚手册；Carina v4 数据库不得未经兼容评估交给旧软件。

## 文档导航维护

[PROJECTS.md](../../PROJECTS.md) 的活动开发入口已路由到独立仓库 main；旧根目录保留迁移导航。
目标项目运行方式以各自 README/AGENTS.md 为准，完整历史执行账本以目标
`docs/migration.md` 为准。后续候选或源码清理变化须同步更新远程 SHA/CI 证据和验收结论；
本记录不包含凭据、个人资料、原始运行日志或生产数据库内容。
