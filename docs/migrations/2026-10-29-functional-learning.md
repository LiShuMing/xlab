# Haskell 退役与 OCaml / Lean 4 学习项目

## 授权与范围

2026-10-29，所有者要求删除 Haskell，新增 OCaml、Lean 4 学习项目、教程，
并在本机安装和实际构建学习环境。
本次起点为 xlab `240840a549bc8eed52151165ff103cc2a1ccade6`，
实际工作树为 `/home/admin/xwork/xlab`。

移除 `haskell/SKILL.md` 和四个项目下共 27 个已跟踪文件：
`haskell/hslab`、`haskell/projects/dsl-transform`、
`haskell/projects/sql-parser`、`haskell/projects/stm-engine`。
检查时这些路径没有额外的未跟踪或被忽略文件。
既有 C++ singleton 文件和清单中的 118 条计数修改属于用户原有工作，保持不变。

这是所有者决定的源码退役，不是 Haskell 工具链卸载，
也不声称新项目覆盖旧 SQL parser、Monad Transformers 或 STM 的全部功能。
历史任务文档继续保留当时记录；根忽略规则继续保护旧路径生成物。

## 恢复

需要时先确认不会覆盖新的本地工作，再从起点恢复：

```bash
git restore --source=240840a549bc8eed52151165ff103cc2a1ccade6 -- haskell
```

本次不会执行该恢复命令，也不改写 Git 历史。

## 新项目

- [OCaml](../../ocaml/README.md)：标准库基础、带错误的表达式解释器、常量折叠；
  [中文教程](../../ocaml/TUTORIAL.md)；Dune 构建和语义对照测试。
- [Lean 4](../../lean4/README.md)：自然数表达式、列表归纳、常量折叠保持求值的证明；
  [中文教程](../../lean4/TUTORIAL.md)；Lake 构建、编译期和运行期检查。

两个项目各自描述自己的语义。Lean 的定理不自动认证 OCaml 程序。

## 本机环境

使用 [安装脚本](../../tools/setup-learning.sh) 和
[激活脚本](../../tools/learning-env.sh)。默认目录为
`~/.local/share/xlab-learning`，可用 `XLAB_LEARNING_HOME` 覆盖。
脚本不安装系统包，不修改 shell 启动文件，也不替换系统 glibc 或 GCC。
下载保留 TLS 校验并检查固定 SHA-256；源码固定到官方发布提交。

本机为 Linux / x86_64、glibc 2.17。
OCaml 5.5.2 与 Dune 3.24.2 由源码构建。
Lean 4.35.0 使用源码自举，通过 elan 4.2.4 注册为本机工具链；
项目的 `lean-toolchain` 仍固定官方版本，目录级 override 只保存在隔离 ELAN_HOME。
源码构建需要 CMake ≥3.21、C++20 编译器、OpenSSL ≥3 和 pkg-config。
脚本在本机使用已有的 Clang/libc++ 20 与 Miniconda OpenSSL 3.3.1；
其他机器可以通过 `CC`、`CXX`、`OPENSSL_ROOT_DIR` 选择工具链；
旧 GCC 环境也可显式设置 `XLAB_CLANG_ROOT` 指向已有 Clang/libc++ 安装目录。
libuv 1.51.0、CaDiCaL 2.1.2、leantar 0.1.20 安装在同一用户目录。
Lean 使用内置大整数（`USE_GMP=OFF`）和系统 allocator（`USE_MIMALLOC=OFF`）。
构建明确使用 PATH 中的 Make 4.4.1，避开系统 Make 3.82 的并行任务管道问题。
glibc 2.17 缺少 `sys/random.h`；安装脚本应用可审阅的
[兼容补丁](../../tools/lean-glibc217.patch)，仅移除两个未使用的头文件引用。
Lean 原有 `/dev/urandom` 随机数读取和证明内核实现保持不变。

默认构建并行度为 4，可设置 `XLAB_LEARNING_JOBS`。
本次最终工具链构建使用 32 个并行任务（本机 96 个处理器、内存充足）。
新终端需要重新 source 激活脚本；原来的 opam 配置不会被改动。
源码安装时，激活脚本从该工具链的 CMake 配置读取 `LEAN_CC`，
让 Lake 使用相同编译器；已有显式 `LEAN_CC` 以及全局 `CC`、`CXX` 保持不变。
安装脚本适用 Linux x86_64，Windows/macOS 应使用各语言官方安装器，尚未在本轮验收。

## 验证记录

实际构建与验收完成于 2026-10-30 UTC；退役和新增工作始于 2026-10-29。

- OCaml：5.5.2 编译器安装成功；Dune 3.24.2 构建成功。
- `dune build`、`dune runtest`、`dune exec ocaml-lab` 实际通过：116 项检查，演示结果 45。
- Lean：4.35.0 Release 源码自举完成，Lake 报告 `5.0.0-src (Lean version 4.35.0)`。
- `lake build xlab-lean xlab-tests`、两个 `lake exe`、
  `lake env lean Xlab/Proofs.lean` 实际通过；64 项运行期检查、6 项编译期检查，演示结果 45。
- `sum_append` 和 `foldConstants_correct` 的公理依赖检查均为 `[propext]`，
  即 Lean 标准的命题外延性；没有 `sorryAx`、`sorry`、`admit` 或自定义公理。
  这些证明只覆盖本 Lean 项目的语义，不认证 OCaml 实现。
- `bash tools/setup-learning.sh all` 重复执行通过，不重编译已完成的工具链，
  不覆盖指向其他位置的既有自定义工具链。
- 仓库离线维护测试（不含依赖 Git 暂存区的项目计数检查）：52 项实际执行，47 项通过，5 项失败。
  失败来自既有退役目录仍存在：books/email/learning、`liminalis`、
  `rust/projects/fragment-tutor`、`python/projects/py-cli`、`docs/books`。
  本次未改动这些目录或放宽测试断言。
- 导航链接 2 项、环境脚本边界 3 项、脚本语法与依赖声明元数据检查通过。
- 项目计数使用单独临时 `GIT_INDEX_FILE` 验证通过：OCaml 14、Lean 11 个源码/清单文件。
  为匹配用户原有 `cc/cclab=118` 修改，临时索引纳入两个原有 singleton 文件；
  随后从临时索引移除它们，仅对本次变更执行格式检查，通过。
  以实际索引文件的 SHA-256 确认真实暂存区没有改变。
- `git diff --check` 通过；`ocaml/_build/`、`lean4/.lake/` 生成物被忽略，
  `lean4/lake-manifest.json` 作为无外部依赖的锁定清单保留。
- 上述环境验收阶段没有执行 git commit、push、远端 CI 或其他语言项目的构建。

## 后续提交范围（2026-10-30）

按所有者后续要求，将本次 Haskell 退役、OCaml / Lean 4 项目、中文教程、
环境脚本和导航更新单独作本地提交，不执行 push。
既有两个 C++ singleton 文件及清单中 `cc/cclab` 从 116 到 118 的修改不纳入提交；
提交版本仍记录 116，本地工作树继续保留用户的 118。
