# LLM Runtime Agent Guide

遵守根 AGENTS.md。修改前阅读 README.md、ARCHITECTURE.md、TASKS.md；模型相关修改读取 Python 项目的 docs/artifact-contract.md。

- 当前只有文档，无 Cargo.toml 或已验证命令。
- 实现阶段使用 Rust 2021；执行 cargo check、相关测试、cargo fmt 和 cargo clippy。
- 优先 MockBackend 和同步 Engine，再引入真实张量计算与网络入口。
- 错误使用 Result，不以 panic 处理非法模型、容量不足或用户取消。
- 状态与缓存集中管理；测试终态清理、请求隔离、句柄复用和失败路径。
- CPU 参考正确后验证 Metal；数值容差必须显式且有依据。
- Candle 不通过 Python 运行时调用；不为了两个项目互通提前增加 FFI。
- 不提交权重、运行输出、凭据或 target 目录；测试用小型合成样本例外。
- 性能结论须注明设备、后端、工作负载和同步方式。
- 上游代码复用保留来源、commit 和许可证。
