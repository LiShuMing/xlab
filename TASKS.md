# xlab 当前质量与维护任务

更新：2026-10-19；评审基线：`af9a828`。本轮改动尚未提交，验证结果只代表
当前工作树。当前项目见 [PROJECTS.md](PROJECTS.md)，质量入口与实际执行结果见
[验证矩阵](docs/meta/validation-matrix.md)。

历史的大规模重构模板、旧目录树和已迁出任务移至
[历史规划](docs/meta/tasks-history-2026-10-19.md)，不作为当前缺口清单。
不再要求每个小实验统一创建 AGENTS/RULES/CHANGELOG 或统一达到 80% 覆盖率。

## P0/P1 修复与验收

| 项目 | 已实施的修复 | 验收方式与边界 |
| --- | --- | --- |
| P0：IVM 键语义 | 明确使用 Python 相等/哈希语义，修正 True/1 预期；计时比例改为确定性操作量检查 | `python3 -m unittest discover -s python/ivm`，23 项通过 |
| P0：UBSAN | 修复遗留 CMake 分支；便携构建加入 address/undefined/leak；构建脚本默认便携并执行测试 | Shell 与脚本入口测试通过；直接 GCC ASAN/UBSAN smoke 通过，完整 CMake/GTest 仍待验收 |
| P0：依赖声明 | 仅保留两个固定 gitlink；69 条历史记录完整保留；遗留 CMake 支持包/显式源码；Folly 脚本不再修改 Git 或安装系统包 | 元数据校验通过不代表遗留实验全部可构建，见依赖说明 |
| P1：核心验证矩阵 | 记录范围、环境、命令、执行状态及研究主题 | [矩阵](docs/meta/validation-matrix.md)；未执行项目不能宣称通过 |
| P1：CI | 增加 Go race/vet、IVM、LLM Benchmark、Linux ToyDB、DuckDB smoke、C++ sanitizer；Rust 增加 Linux 与 Clippy | 工作流已配置；本轮 GitHub Actions 尚未运行 |
| P1：测试断言 | DuckDB smoke 比较查询结果 | 已补断言；当前缺少 DuckDB/pytest，尚未执行 |
| P1：任务管理 | 当前修复与历史规划分离，按具体验收记录工作 | 本文件为当前待办唯一入口 |

## 待完成的运行验收

- [ ] 在具备工具链的环境执行验证矩阵全部核心命令，记录实际版本、提交和失败信息；新 CI 必须通过后才标记验证完成。
- [ ] 在配置 fmt/glog/absl 的专用环境验收遗留 cclab；Folly 为显式可选项，不能把便携测试结果外推为全量构建结果。
- [ ] 将未验证项目逐个登记为稳定、活跃或冻结；保留清单不自动代表活跃维护。

这些是尚未获得的运行证据，不因维护测试通过而关闭。

## 后续 P2

- [ ] 核对第三方代码来源与适用许可，再补充仓库许可说明。
- [ ] 为需要比较性能的实验记录硬件、数据规模、正确性对照和可复现命令。
- [ ] 分别核对 py-ego 的监控、对话和小程序职责，提出模块边界调整方案。
- [ ] 按独立改动评估 cc/golab 的路径归类，核对所有引用后再移动。
- [ ] 检查 `cc/srlab/data/v1.jstack` 的保留价值；不能据此删除用户数据。

## 维护边界

已迁出的源码和书稿继续在 Lyra、Carina、Vela、Cygnus 中维护，不在 xlab 重建。
[迁移记录](docs/meta/migration-guide.md)、[保留项目](docs/meta/retained-projects.md)、
[依赖消费历史](docs/meta/dependency-declarations.md)、
[当前依赖契约](docs/meta/dependencies-current.md)提供来源和恢复入口。
