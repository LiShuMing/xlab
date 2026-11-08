# LLM Lab Agent Guide

遵守仓库根 AGENTS.md。修改前阅读 README.md、ARCHITECTURE.md 和本文件的阶段进度；跨语言 修改还需阅读 docs/artifact-contract.md。

- 本地环境入口 scripts/setup.sh；检查命令 .venv/bin/pytest -q 与 .venv/bin/ruff check src tests。依赖由 uv.lock 固定。
- Python 使用独立虚拟环境、类型标注与 pathlib；依赖在实现时验证后固定。
- 模型代码应能直接对应计算公式，不提前增加插件系统和抽象工厂。
- CPU FP32 作为正确性基线；缓存和加速实现必须与参考 logits 对照。
- 性能记录必须标明设备、同步方式、数据和版本；不将 MPS 结果描述为 CUDA 性能。
- 不提交数据集、模型权重、运行产物、凭据或虚拟环境；小型合成 fixtures 可跟踪。
- README 只写已实现入口；设计与待办分别维护在 ARCHITECTURE.md 和本文件的“阶段进度”一节。
- 引用上游代码保留许可证和来源 commit。

## 阶段进度

已完成：目录与文档骨架、Python/Rust 边界与产物契约草案；P0 环境与最小训练链路
（pyproject + 独立虚拟环境 + 固定依赖、CPU/MPS 可用性记录、byte tokenizer 与合成数据集、
bigram 训练/验证/保存/重载/生成，验收四项均通过）；P1 Tiny Transformer（契约模型与训练恢复、
因果遮罩/shape/极小数据过拟合测试、固定验证集与 bigram 对照）。

P2 缓存与跨语言验证（未开始）：

- [ ] 实现 prefill/decode 与连续 KV Cache。
- [ ] 缓存与无缓存逐步 logits 对照、上下文边界测试。
- [ ] 实现 bundle 导出器、参考数据和契约校验。
- [ ] 与 Rust CPU 后端完成一致性验证。

P3 本机性能实验（未开始）：

- [ ] CPU/MPS 分别记录预热、同步计时、内存及重复测量。
- [ ] 对比不同上下文长度的有/无缓存推理。
- [ ] 完成可复现实验报告，再决定 BPE 或更大模型扩展。

文档完成不代表代码、测试或后端已经可用。暂不启动完整预训练、后训练或服务平台建设。
v0.1 本机验收（CPU 与 MPS 训练、检查点重载、生成通过，9 项 CPU 测试通过）见
`experiments/2026-09-19-local-acceptance.md`；单次训练耗时不作为性能基准结论。
