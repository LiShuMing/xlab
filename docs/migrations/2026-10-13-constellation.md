# Constellation 拆分迁移记录（2026-10-13）

## 结论与状态

**独立代码候选已完成本地构建、测试与专项审查；迁移尚未整体验收，原项目全部保留。**
Vela 已核验私有远程提交、文件树，以及实现提交和最终文档提交各自的七项 CI。
联合发布验收、生产部署和真实数据迁移均未宣称完成。Lyra、Carina 代码发布待完成；
两者远程目前仅有引导内容，不能视为代码已经上传。
任何本地提交号都不能代替远程提交验证。本文仅为文档变更，不删除源码。

源仓库：<https://github.com/LiShuMing/xlab>。
共同提取基线：`fd15e65059ff7d0d01ed48b6347cd75881fb4b36`。
协调任务在 2026-10-13 15:28 UTC 和 15:51 UTC fetch 后确认该提交仍为 `origin/main`，
后一次检查源 checkout 也保持干净；
发布和清理前必须重新检查，不能把这次观察当成持续有效的保证。

## 源码映射与保留边界

以下数量是首次提取的已跟踪文件数，不是修改后文件总数。各目标仓库使用全新
Git 历史，提取清单记录原始路径、目标路径和源字节 SHA-256；后续修复由新提交记录。
文档整理时独立复核全部 **546** 项源哈希，均与固定基线一致。

| 源路径（xlab 根目录相对路径） | 私有目标仓库与目录 | 提取数量 | 状态与精确清单 |
| --- | --- | ---: | --- |
| `liminalis/` | [Lyra](https://github.com/LiShuMing/lyra) 根目录 | 365 | `EXTRACTION.json`；四项排除，不代表整个目录可删除 |
| `panming/` | [Carina](https://github.com/LiShuMing/carina) 根目录 | 56 | `docs/source-manifest.json` |
| `python/projects/tech-radar/` | Carina `modules/tech-radar/` | 48 | 同上；采集器和核心业务仍有独立数据边界 |
| `optimizer-learning/` | [Vela](https://github.com/LiShuMing/vela) `optimizer/` | 19 | `docs/source-manifest.json` |
| `cc/projects/query-engine/` | Vela `execution/` | 33 | 同上 |
| `cc/projects/kv-store/` | Vela `storage/` | 25 | 同上 |

明确未迁移或仍保留：

- Lyra 排除两份已跟踪会话日志、个人图片和生成的 Radar 快照；仅新增空的启动快照。
  不复制排除项的内容。精确排除路径保存在目标提取清单中。
- xlab 根 `docs/` 知识库保留。Lyra `docs/content-migration.json` 清点 380 份引用文件，
  没有将它们打包搬走；默认只有新建欢迎页。可选 `LYRA_CONTENT_ROOT` 会把所选内容
  编入前端资源，接入前必须逐项审查，不能指向未经筛选的私人资料。
- `rust/projects/fragment-tutor/` 保留在 xlab。Carina 没有交付该桌面应用、数据库或
  无损 SRS 适配器；核心 3/7/30 天分级不等价于原 interval/ease/streak/history。
- Collector 的 signals 可做离线传输，但文章/发布历史和二进制资产尚未完整转换；
  不能将 signals 适配器的测试通过描述成整个工作流的数据迁移完成。
- 本次范围以表中六个源路径及逐文件清单为准。其他实验项目、第三方子模块、
  根知识库、运行目录、配置密钥、真实数据库、资产和本地未跟踪文件均不属删除范围。
- 未授予新许可证。Vela 已去除没有依据的 TinyKV MIT 声明；公开再分发前仍需
  所有者解决许可来源问题。目标仓库目前按私有仓库处理。

## 本地候选快照与证据

本文汇总各候选 `docs/migration.md` 中的执行记录；本次文档工作复核清单和文档，
未把整套应用测试重新执行一遍。下表为文档整理时读取的本地 HEAD，**不是远程 SHA**。

| 仓库 | 本地 HEAD | 首次提取提交 | 验证定位 |
| --- | --- | --- | --- |
| Lyra | `1fea7259d9465b44ce73c72bb8ffc1408db58463` | `1921459` | 候选 `docs/migration.md` 最终附录 |
| Carina | `d0393d021cb97a6f29a75b6490351330667dc9e0` | `728d74b` | 候选 `docs/migration.md` 验证账本 |
| Vela | `410aaa9bf23aa3fb591696b4754adc93f67ee521` | `9671913` | 候选 `docs/migration.md` 验证与独立审查 |

每个目标均有自己的 README、AGENTS.md、构建/依赖清单、格式化配置、测试和迁移记录。
它们不依赖旁边存在 xlab checkout；新环境仍需按各 README 安装工具和锁定依赖。
远程核验记录（协调任务提供）：

- Vela 实现快照：`5ed9fc68d6e1ca1580d051397ce41d611f12a18b`。
  文件树 `8165e0eb516632bf681458cb3c8e46b359590255` 与本地最终候选完全一致；
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
- Lyra、Carina：代码发布待完成，远程目前仅有引导内容；
  最终代码远程 SHA、文件树和 CI 均未核验。

完成联合远程验收还需补充 Lyra、Carina 的远程提交、完整文件树与 CI。

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

已执行：247 个 Python 测试（包含临时 PostgreSQL 用例）、3 个前端测试、生产构建、
Go 全包 uncached race（包含 PostgreSQL）与 vet、Alembic 临时数据库升/降/再升级、
Ruff/Prettier/Go 格式和 shell/空白检查。独立 clone 无数据库运行明确为 246 通过、
1 项 PostgreSQL 跳过；不将跳过算成通过。另验证任意目录名内容根和小型 golden fixtures。
Python 3.12 为实际验证版本；已有弃用和 Browserslist 数据陈旧警告未被掩盖。

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
这不是远程 CI 或其他 sanitizer 检查的阻塞；源码清理前仍需明确这一项验证范围。
Debug benchmark smoke 不构成性能比较或吞吐量结论。

## 删除源代码前的联合验收门槛

删除门槛针对全部候选，不因某一个仓库的本地测试通过而提前放行。

1. 重新 fetch/核对 xlab `origin/main`；如基线后有变化，先分类并迁移相关 delta，
   对更新后的候选重新审查和测试。
2. 验证三个私有远程各自最终提交、完整文件树和清单；
   核验对应提交的必需 CI。没有 CI 运行或状态未知不能标记通过。
3. 从已核验远程的新 clone 安装锁定依赖，构建、执行完整质量命令并验证无 xlab
   旁路依赖；必要数据库必须为明确指定的临时数据库，跳过项须单列。
4. 完成独立审查，记录修复与测试对应关系；明确 Vela 独立泄漏检查的证据范围，
   不把远程默认 ASan/UBSan 通过改写成另外执行过的独立 LeakSanitizer 自检。
5. 明确完成范围内的功能/数据等价验收：尤其是 Carina 外部 FragmentTutor 与
   采集器历史/资产边界、Lyra 内容库边界。未实现的等价迁移继续保留原项目，
   或由所有者明确调整范围；不能自行把“拆出代码”解释为“全部替代”。
6. 形成逐文件删除白名单与保留清单，确认不会删除排除内容、运行数据或知识库，
   验证备份/恢复和新入口可用，再提交独立、可审查、可回退的源码清理变更。
   审查根构建脚本、CI、文档和 PROJECTS.md 引用，避免清理后留下失效路径。

**当前决定：六个映射源路径和 FragmentTutor 均保留；没有任何源删除操作获本记录放行。**

## 回滚方案

- 尚未清理源码：继续使用固定基线或现有源工作流，无需恢复数据，因为本次没有操作
  真实业务数据。目标代码使用普通 revert 或本地提取提交回退，不重写远程历史。
- 将来单独批准源码清理后：优先 revert 清理提交；也可从固定基线恢复白名单路径，
  但必须先检查后续有效修改，避免覆盖。排除数据和运行目录不由代码回滚处理。
- 真实数据接入前：另行审查备份、校验和、schema/version、完整关系和未知字段、
  时间/null 语义及幂等导入方案；恢复须指向明确批准的干净目标。
- Lyra 临时库的 Alembic downgrade 测试不是生产回滚操作手册。
  Carina v4 数据库不能未经兼容评估直接交给旧软件；事务失败后残留的未引用
  内容寻址 blob 可供重试复用，不能未经审查自动删除。

## 文档导航维护

[PROJECTS.md](../../PROJECTS.md) 增加独立候选导航，原目录路由仍保留。
目标项目运行方式以各自 README/AGENTS.md 为准，完整历史执行账本以目标
`docs/migration.md` 为准。发布最终验收记录时需补入远程 SHA/CI 证据和未决项结论；
本记录不包含凭据、个人资料、原始运行日志或生产数据库内容。
