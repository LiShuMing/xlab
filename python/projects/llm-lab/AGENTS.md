# LLM Lab Agent Guide

遵守仓库根 AGENTS.md。修改前阅读 README.md、ARCHITECTURE.md 和 TASKS.md；跨语言修改还需阅读 docs/artifact-contract.md。

- 本地环境入口 scripts/setup.sh；检查命令 .venv/bin/pytest -q 与 .venv/bin/ruff check src tests。依赖由 uv.lock 固定。
- Python 使用独立虚拟环境、类型标注与 pathlib；依赖在实现时验证后固定。
- 模型代码应能直接对应计算公式，不提前增加插件系统和抽象工厂。
- CPU FP32 作为正确性基线；缓存和加速实现必须与参考 logits 对照。
- 性能记录必须标明设备、同步方式、数据和版本；不将 MPS 结果描述为 CUDA 性能。
- 不提交数据集、模型权重、运行产物、凭据或虚拟环境；小型合成 fixtures 可跟踪。
- README 只写已实现入口；设计与待办分别维护在 ARCHITECTURE.md 和 TASKS.md。
- 引用上游代码保留许可证和来源 commit。
