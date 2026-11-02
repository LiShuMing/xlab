# 项目状态与交付清单（2026-10-31）

这是公开源码交付前的状态快照，检查完成时间为 2026-10-31 12:23 UTC 之后。
只记录可公开的源码、工具版本、验证结果和后续任务，不复制私有环境或运行数据。
当前任务要求将现有源码改动全部记录、使用 Gmail 身份提交，并普通推送至 `origin/main`。

## 源码与交付范围

核验时远端主干为 `240840a`，本地分支为 `chore/rlab-cargo-cleanup-20261024`，
已有一个尚未发布的学习项目提交 `cdd1e1c`，在主干上无分叉。
该学习提交包含 69 个文件的变更：删除 27 个 Haskell 跟踪文件，新增 OCaml 14 个、
Lean 4 11 个源码/配置/教程文件，补充隔离安装、激活和兼容补丁，并同步导航及清单。
完整范围可用 `git show --stat cdd1e1c` 查看；恢复旧源码的边界见
[学习项目迁移记录](../migrations/2026-10-29-functional-learning.md)。

本次将此前所有工作区源码改动一并纳入，不再排除原有 C++ 工作：

| 路径 | 本次交付内容 |
| --- | --- |
| `.gitignore` | 忽略 Daft 私有 `.local/`，精确保留必需的 `uv.lock` |
| `PROJECTS.md` | Daft 项目导航 |
| `cc/cclab/src/common/singleton.h` | 三种单例实现与内存序说明 |
| `cc/cclab/test/interview/singleton_test.cc` | 并发初始化、同一实例、异常后重试测试 |
| `docs/meta/retained-projects.json`、`retained-projects.md` | C++ 跟踪数 118；新增 Daft 11 文件清单；两份数据同步 |
| `python/projects/daft-lab/README.md` | 环境、学习顺序、证据解释和未覆盖边界 |
| `python/projects/daft-lab/bootstrap.py`、`env.sh` | 固定镜像下载、受限解包、本地命名空间运行和环境身份校验 |
| `python/projects/daft-lab/lab.py`、`experiments.py` | 确定性输入、12 变体、完整输出断言、计划/事件/内存记录 |
| `python/projects/daft-lab/image.lock.json`、`source-reference.json` | 镜像与阅读参考版本，明确参考源码不是运行产物 |
| `python/projects/daft-lab/pyproject.toml`、`uv.lock` | 固定最小依赖及哈希，使用公开 HTTPS 镜像 |
| `python/projects/daft-lab/test_bootstrap.py`、`test_lab.py` | 解包、镜像身份、未登记分片和悬空链接保护回归 |
| `TASKS.md`、`docs/meta/validation-matrix.md`、本文件 | 当前状态、历史结果区分及未完成事项 |

交付检查修复了三处新项目缺口：遗漏依赖锁、生成器覆盖未登记分片、镜像锁与旧 rootfs
身份不一致。未登记分片与悬空链接的回归测试在旧代码失败、修复后通过；生成器在
修改过的自有文件、未登记文件或链接冲突时保留现场并拒绝继续。

## 当前运行与验证

- 学习工具安装在用户级隔离目录；每个新终端执行 `source tools/learning-env.sh`。
  本轮实际重跑：OCaml 5.5.2、Dune 3.24.2 的 build/runtest/demo；116 项检查、结果 45。
  Lean 4.35.0 的 Lake build、测试、demo 与证明文件编译；64 项运行检查、6 项编译期
  检查通过，演示结果 45。环境激活不修改用户原有 opam 或全局 CC/CXX。
- Daft 是私有 rootfs 中的 0.7.26 发行 wheel；Python 3.11.18、PyArrow 20.0.0、
  NumPy 2.2.6、psutil 7.0.0，容器内 glibc 2.36。CPU affinity 为 4 核，未设置内存
  cgroup 限额。镜像 digest 与安装标记实际匹配。本轮 9 项回归和 12 个真实实验变体
  通过；临时目录中真实 Arrow 生成、再生成、空输入、热点输入通过。
  输入使用已有数据，没有重写主实验输入。
- Daft 本次证据位于项目 `.local/runs/20261031T122001Z-4f551b3b/`，保留在本机、
  不纳入 Git。结果只说明该输入下的输出/机制检查，不是分布式或公平性能排名。
- C++ singleton 从独立源码快照编译，使用现有 GoogleTest 与 UBSAN，6 项通过。
  根 CMake 配置成功，但 GCC 9.2.1 编译已有 `enum_test.cc` 时不支持相应 C++20
  语法而失败，完整 CTest 未执行；没有把定向成功扩称全量成功。
- 主工作区维护测试在可用 locale 下为 53 项中的 48 项通过，5 项因旧退役目录残留
  失败。只含待交付源码的独立快照 53/53 通过。依赖清单、暂存格式与 Bash 语法通过。
  临时快照及构建日志保留在 `/tmp/xlab-publication-20261031-XVqq8Q/`，不是主工作区。
- Daft 和学习项目入口均为前台短任务，不部署常驻服务或开放端口。本轮拥有的验证
  任务结束后会回收进程；不触碰其他会话、编辑器或用户服务。

## 未完成事项

1. 主工作区退役目录残留：books/email/learning 对应旧根、`liminalis`、
   `rust/projects/fragment-tutor`、`python/projects/py-cli`、`docs/books`。
   先核验归属、引用、活动运行及恢复需要，再由维护者选择处置；本次不清理。
2. 根 CMake 使用受支持的现代 C++ 工具链重跑；将 singleton 定向测试接入默认构建
   需要独立变更。完整 legacy cclab 仍需专门依赖环境。
3. OCaml、Lean、Daft 专用 CI 和跨平台验收尚缺；本轮没有重跑 Rust、Go、JVM、
   其他 Python 或 GPU 模块全套。现有其他任务仍见 [TASKS](../../../TASKS.md)。
4. Daft generate/run 共享数据目录，必须串行；不承诺并发隔离、中断自动恢复或内存
   限额。Ray、Spark、跨节点成本尚未验收，参考 Daft checkout 未编译。
5. 新的远端提交 SHA 与 CI 结果必须推送后读取；本快照不预先宣称发布成功或 CI 全绿。
   已迁出的应用继续在目标仓库维护，不在 xlab 恢复旧源码。

## 忽略文件与公开检查边界

保留但不提交：Daft `.local/`（rootfs、环境、缓存、输入、日志、证据）、编辑器 swap、
`__pycache__/`、OCaml `_build/`、Lean `.lake/`，以及其他既有忽略目录。
没有为满足“所有改动”而强制添加私有数据、凭证或编译产物，没有删除这些文件。

发布检查覆盖主干之后每个待推送提交及完整暂存内容，而不只是最终 diff。
原未发布学习提交的宿主专用标识已中性化并重写，避免仅在后续提交删除而仍泄露历史。
对凭证格式、私钥、带凭证 URL、企业账号及非公开环境引用进行静态扫描与人工复核，
未发现需阻止发布的内容；公开包镜像引用予以保留。此结论不声称全仓历史从未含敏感信息，
也不将规则扫描等同于形式化安全保证。私有忽略目录不作为发布扫描输入。

作者与提交者均使用 `shuming.li <ming.moriarty@gmail.com>`；
GitHub SSH 身份已核验为个人账号 `LiShuMing`。提交设置 `AI_COMMIT=1` 与
`AI_MODIFY_AGENT=codex`。普通快进推送目标为 `origin HEAD:main`，不用 force；
不切换当前分支、不改写远端已发布历史、不创建版本发布。
