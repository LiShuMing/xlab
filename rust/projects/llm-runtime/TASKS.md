# LLM Runtime Tasks

## 已完成

- [x] 建立目录与设计文档。
- [x] 明确与 Python 的独立运行边界、共享契约位置。

## P0：独立模拟运行时

- [ ] 验证 Rust 工具链，创建独立 Cargo crate，使用 Rust 2021。
- [ ] 实现 Request、Engine、FIFO Scheduler、MockBackend。
- [ ] 增加等待队列与活跃请求上限、确定性工作负载。
- [ ] 验收：状态转换、EOS、长度上限、取消、错误和缓存释放测试。

## P1：真实单请求推理

- [ ] 固定 Candle 版本，首先验证 CPU 构建与小张量计算。
- [ ] 实现共享契约的校验与模型加载。
- [ ] 实现无缓存 forward、prefill/decode、连续 KV Cache。
- [ ] 与 Python FP32 CPU 参考逐步对齐，验证容量与错误路径。
- [ ] 可选验证 Metal，记录算子限制、精度和设备。

## P2：批处理

- [ ] 实现变长输入的静态 batch，而非循环调用单请求冒充 batch。
- [ ] 加入连续 batching、prefill/decode 预算与调度事件记录。
- [ ] 验收：批量与单请求数值一致，取消和 EOS 不破坏其他请求。
- [ ] 固定长短请求混合负载，比较 FIFO 基线与新策略。

## P3：缓存管理实验

- [ ] 实现逻辑块表、引用计数、释放和容量限制。
- [ ] 增加前缀复用与 copy-on-write 测试。
- [ ] 区分 gather 功能原型与真实分页 attention 内核。
- [ ] 报告缓存碎片、命中率与吞吐，不把模拟结果当实机性能。

## 后续再评估

- [ ] 是否增加 HTTP 流式服务和 Tokio 命令入口。
- [ ] 是否支持额外开源模型及对应 tokenizer。
- [ ] 是否需要远端 NVIDIA 环境研究 CUDA 或多 GPU。

有对应运行记录和通过的验收才勾选任务；骨架创建不等于实现完成。
