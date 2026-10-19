# xlab 核心项目验证矩阵

更新：2026-10-19。源码基线 `af9a828`，另含当前未提交的 P0/P1 修复。
本表分别记录已执行结果与新增 CI 配置；配置完成不代表远端已通过。

## 当前范围与分类

保留按语言分目录，并以研究主题检索。核心验收范围覆盖下列模块；
`实验原型` 表示仓库用途，不承诺生产成熟度。未列入核心范围的项目仍保留，
未通过本轮审计自动升级为“已验证”。

| 模块 | 类型 / 研究主题 | 环境与最小验证命令（从仓库根执行） | 本轮本地结果 | CI 配置 |
| --- | --- | --- | --- | --- |
| 仓库维护 | 维护工具 / 导航、依赖契约 | Python 3.12；`python3 -m unittest discover -s tools -p 'test_*.py'`；`python3 tools/check_dependencies.py`；`bash tools/healthcheck.sh` | 50 项通过；依赖元数据通过；健康检查 0 失败 | repository-checks，Linux/macOS |
| cc/cclab + thread-pool | 实验原型 / C++、并发、数据结构 | CMake ≥3.22、GCC/Clang、固定 GoogleTest；`cmake -S . -B build -DXLAB_FETCH_DEPENDENCIES=ON -DXLAB_SANITIZER=undefined`；`cmake --build build --parallel 4`；`ctest --test-dir build --output-on-failure --no-tests=error` | GCC 14.2 直接编译的 ASAN/UBSAN smoke 通过；CMake/GTest 套件未执行 | native-build Linux/Windows Debug/Release；core-quality ASAN/UBSAN |
| rust/rlab | 实验原型 / 并发、算法、外部排序 | Rust stable；`cargo test --manifest-path rust/rlab/Cargo.toml --workspace --locked --release`；`cargo clippy --manifest-path rust/rlab/Cargo.toml --workspace --all-targets --locked` | 未执行；本地无 Rust 工具链 | native-build，Linux/Windows |
| rust/rdb | 实验原型 / 数据库、列式存储 | Rust stable；`cargo test --manifest-path rust/rdb/Cargo.toml --locked`；`cargo clippy --manifest-path rust/rdb/Cargo.toml --all-targets --locked` | 未执行；本地无 Rust 工具链 | native-build，Linux/Windows |
| go/k8s-lab | 教学原型 / MVCC、控制面、并发 | Go 1.26.2；`cd go/k8s-lab`，`gofmt -l .`、`go vet ./...`、`go test -race -count=1 -coverprofile=coverage.out ./...`、`go run ./cmd/demo` | 未执行；本地 `/usr/bin/go` 并非可用的 Go 语言工具链 | core-quality；race 必跑，上传覆盖率产物 |
| python/ivm | 实验原型 / 增量计算、join | Python 3.12，无第三方依赖；`python3 -m unittest discover -s python/ivm -p 'test_*.py'` | 23 项通过；修复相等语义预期与不稳定计时检查 | core-quality |
| python/llm_benchmark | 实验工具 / LLM 评测 | Python 3.12；`python -m pip install -e 'python/llm_benchmark[dev]'`；`cd python/llm_benchmark`，`python -m pytest tests -q` | 未执行；当前无 pytest，安装受网络权限限制 | core-quality；测试采用 mock API，无真实模型调用 |
| python/projects/py-toydb | 实验原型 / 文档数据库 | Python 3.12；`python -m pip install -e python/projects/py-toydb pytest`；`cd python/projects/py-toydb`，`python -m pytest tests -q` | 未执行；当前无 pytest | native-build Windows；core-quality Linux |
| python/pylab smoke | 学习实验 / DuckDB Python API | Python 3.12；`python -m pip install pytest duckdb==1.1.3`；`cd python/pylab`，`python -m pytest test/test_duckdb.py -q` | 未执行；当前无 DuckDB/pytest；已加入结果断言 | core-quality；只覆盖该 smoke，不代表整个 pylab |

每次运行 CI 或手工验收后，记录对应提交、系统、工具版本和结果。
Rust Clippy 当前会报告已有警告；编译/Clippy 错误会失败，尚未施加全仓
`-D warnings` 或全仓重新格式化，以免把历史风格债务混入本轮修复。

## 实际执行记录

本轮本地：Linux，Python 3.12.14，工作树基于 `af9a828`。

- IVM：23 项通过，无模型/API/数据库外部服务调用。
- 维护测试：50 项通过；依赖元数据校验通过；健康检查 0 失败、2 警告（未初始化 gitlink、遗留构建需单独验证）。
- C++：GCC 14.2.0，线程池两种调度模式的结果、停止及拒绝提交行为，以及一致性哈希查找，通过独立 ASAN/UBSAN smoke。
- Shell：`bash -n cc/cclab/build.sh shell/docker/build_folly.sh tools/healthcheck.sh`。
- CI：新增工作流尚未推送和执行，不宣称远端全绿。
- 联网安装验证工具未成功，未通过关闭 TLS、代理绕行或更改系统配置补齐工具。

## 无 CMake 时复现 C++ smoke

`tools/cpp_smoke.cc` 同时是根 CTest 的 `xlab_core_smoke`。本地可直接使用 GCC：

```bash
g++ -std=c++20 -g -O1 -pthread -fno-omit-frame-pointer -fno-sanitize-recover=all \
  -fsanitize=undefined -Icc/projects/thread-pool/include -Icc/cclab/src \
  tools/cpp_smoke.cc cc/projects/thread-pool/src/thread_pool.cc \
  cc/projects/thread-pool/src/ws_deque.cc \
  cc/cclab/src/common/consistent_hash/consistent_hash.cc -o /tmp/xlab-smoke
/tmp/xlab-smoke
```

ASAN 使用同样命令，将 `undefined` 替换为 `address`。本环境受 ptrace 限制，
LeakSanitizer 无法运行，实际 ASAN 验收使用
`ASAN_OPTIONS=detect_leaks=0:halt_on_error=1`；只对本地 smoke 禁用泄漏检测。
CI 仍开启 `detect_leaks=1`。该 smoke 不替代完整 CMake/GTest 套件。

## 尚未纳入自动验收的范围

mini-seastar、web-server、io-uring、完整 legacy cclab、其他 Python 应用、JVM、
Haskell 和 GPU 实验仍按各自说明维护。它们有平台/服务/硬件或独立工具链要求，
不能从上述结果推导其可运行性。全仓不存在一条保证所有实验都通过的构建命令。

依赖安装契约见 [当前依赖](dependencies-current.md)，原始消费证据见
[历史审计](dependency-declarations.md)。目录索引见 [PROJECTS](../../PROJECTS.md)，
后续运行验收见 [TASKS](../../TASKS.md)。
