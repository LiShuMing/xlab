# LLM Runtime Architecture

状态：设计草案。所有模块和接口均为计划，尚未实现。

## 执行结构

```text
Requests → Engine → Scheduler → ExecutionPlan
             │                       │
             ├── CacheManager        ▼
             ├── Metrics       ModelBackend
             └── Output         ├── Mock
                                └── Candle CPU / Metal
```

Engine 使用单线程同步循环，集中管理状态。网络层未来可以使用 Tokio 投递命令，但不能让各请求自行修改缓存或并发调用共享后端。暂不增加 Python FFI。

## 模块与数据所有权

| 计划模块 | 职责及所有权 |
| --- | --- |
| `request.rs` | RequestId、输入/输出 token、上限、状态和结束原因 |
| `scheduler.rs` | 选择本轮请求和 token 预算；不操作张量 |
| `engine.rs` | 状态转换、执行顺序、取消处理和终止清理 |
| `backend.rs` | 模型加载、prefill、decode；返回 logits 或明确错误 |
| `backends/mock.rs` | 根据固定输入生成确定性结果，支持注入失败 |
| `backends/candle.rs` | 契约模型的张量计算，先 CPU 后 Metal |
| `kv_cache.rs` | CacheId、容量、长度、租约与释放；禁止裸跨请求索引 |
| `sampling.rs` | greedy 起步；后续增加可复现采样 |
| `artifact.rs` | 产物版本、哈希、配置、权重 shape 校验 |
| `metrics.rs` | 单调时钟记录队列与执行事件，汇总而不改变调度 |

运行时管理逻辑缓存句柄和生命周期；后端缓存容器持有设备张量。Engine 是两者唯一协调入口。句柄应带代际或等效校验，避免释放后复用造成旧请求访问新缓存。

## 请求状态

```text
Waiting → Prefilling → Decoding → Finished
   └──────────┴──────────┴──────→ Cancelled / Failed
```

结束原因区分 EOS、输出长度上限、取消和错误。各终态不可再次调度；所有终态统一释放缓存并产生一次终止事件。取消在 step 边界处理，不承诺中断正在执行的 GPU kernel。

第一版拒绝超过 context capacity 的请求，不隐式截断。`max_new_tokens=0` 立即成功结束，不分配缓存。空 prompt 按契约插入 BOS。特殊 token、padding 与结束处理不可由不同模块各自猜测。

## 后端语义

先定义单请求 prefill/decode 概念接口，再根据真实 batch 实现扩展：

- Prefill 输入 prompt 和新缓存句柄，返回最后位置 logits；缓存有效长度等于 prompt 长度。
- Decode 消费一个新 token，位置由旧缓存长度确定，追加 K/V 后返回下一步 logits。
- 输出 token 是采样结果，只有下次 decode 消费后才写入缓存；达到结束条件时无需再做一步计算。
- Backend 返回错误时不能假定缓存仍可复用；第一版失败即终止相关请求并清理。

数值对齐优先使用固定追加 token，而非自由采样文本。模型细节只以 [共享契约](../../../python/projects/llm-lab/docs/artifact-contract.md) 为准。

## 调度演进

1. Mock + FIFO：有界等待队列、最大活跃请求数、每轮预算；资源不足留在 Waiting，无法满足的请求显式拒绝。
2. 单请求 Candle：确保完整 prefill/decode 和缓存语义正确。
3. 静态 batch：明确 padding mask、各请求位置与有效长度，测试批量和逐条结果一致。
4. 连续 batching：每轮移除完成请求、接纳新请求；分别定义 prefill/decode 预算，测量公平性。

对多个请求逐个调用模型仍然是串行执行，不能称为 GPU batching。第一版 FIFO 不保证复杂负载下最优公平性；后续比较长短请求与饥饿现象。

## 缓存演进

第一版每请求独立连续缓存，记录每层 K/V 的容量和有效长度，测试取消、错误、EOS 后释放。第二版增加逻辑块表和分配器；共享块引用计数，写入共享末块前进行 copy-on-write。

分页管理器与分页 attention kernel 是独立交付。如果仍通过 gather 拼成连续张量计算，只能声明为功能原型，不宣称实现高性能 PagedAttention。前缀缓存键必须包含模型/tokenizer/位置语义和 token 前缀，不能仅按文本键复用。

## 数值与资源验收

- Mock 测试：FIFO 顺序、预算限制、取消、重复取消、后端失败、无双重结束。
- 缓存测试：请求隔离、越界拒绝、容量耗尽、全部结束后使用量归零。
- 模型测试：CPU 与 Python 参考 logits 对齐；缓存/无缓存一致；Metal 单独记录容差。
- Batch 测试：变长输入、不同 EOS 时机、取消一个请求不影响其他请求。
- 性能测试：固定请求轨迹、预热与 GPU 同步，分别报告排队、首 token、decode、吞吐。

模拟时间只能用于调度策略分析，不能作为真实模型吞吐。实际 GPU 计时包含同步语义，后端版本与设备必须记录。
