
# 一、先定标准：面试官其实在区分三种人

| 层级 | 特征 | 典型表现 |
|---|---|---|
| L1 用过 | 背得出 API | “用 `@ray.remote` 就能并行” |
| L2 懂机制 | 能解释现象 | “`ray.get` 会阻塞 Driver，也会触发对象拉取” |
| L3 能预测 | 能预判行为 + 给证据 | “0.5 GPU 只是调度时的记账单位，不做显存隔离；我实测第三个 Actor 会排队” |

---

# 二、第一层：为什么需要 Ray（淘汰率最高）

### Q1：已有 `multiprocessing` / Kubernetes，Ray 多解决了什么？

**合格答案骨架**（按问题分解，而不是列举 Ray 的功能）：
1. **调度**：`multiprocessing` 需要你手写进程池和生命周期；`ray.remote` 的对象引用、任务队列由系统管理。
2. **有状态驻留**：模型常驻内存不重复加载，这是 `multiprocessing.Pool` 很难直接处理的问题（池里进程不保证稳定）。对应你的 [07_kmeans.py](file:///home/admin/xwork/ray/raylab/experiments/07_kmeans.py#L22-L46)：向量只在 `__init__` 传入一次，后续每轮只传 256 字节中心。
3. **异构资源**：CPU、GPU、自定义资源统一在一个调度器里，能声明 0.5 张卡（[02_logical_gpu.py](file:///home/admin/xwork/ray/raylab/experiments/02_logical_gpu.py)）。
4. **容错**：任务重试、Actor 重建、血缘重建。

**会被追问**：Kubernetes 也能做 2 和 3，区别在哪？
→ K8s 的调度单位是 Pod（粗粒度、秒级、常驻），Ray 的调度单位是任务（细粒度、毫秒级、动态）；K8s 不负责“进程活着但任务失败”的重试语义。

### Q2：Ray 和 Spark、Dask、Flink 的边界

不要只回答“Ray 更快”。应该按**抽象层次**回答：

- Spark、Flink（Flink 是流处理框架）：**数据并行 + 声明式**，优化器接管执行计划，适合 SQL 和批流。
- Ray：**任务并行 + 命令式**，你自己写控制流，适合“迭代训练、异构流水线、有状态服务”。
- Ray Data：试图在 Ray 之上补一层类 Spark 的批处理，但它不是 Spark 的替代品。

### Q3：什么时候**不该**用 Ray？（加分题，很多人答不出来）

- 单机、任务粒度 < 1ms：调度和序列化开销远超计算本身。
- 只有一个大任务：Ray 不能把一个任务拆开加速。
- 需要强事务、精确一次语义的数据管道：Ray 不保证。
- 团队只需要跑 SQL：引入 Ray 只增加运维成本。

**这一题答得好，等于证明你有判断力，而不只是熟悉框架。**

---

# 三、第二层：编程模型（必须零失误）

### Q4：Task 和 Actor 的本质区别

一句话：**Task 是无状态函数调用，Actor 是有身份、有生命周期的进程**。

要点：
- Task 的 `ObjectRef` 是**值**（数据），Actor 的 handle 是**引用**（进程）。
- Actor 的调用是**串行默认**的（`max_concurrency=1`），这既是保护也是瓶颈。
- Actor 一旦被杀死后重建，**内存状态全部丢失**，这是 [05_recovery.py](file:///home/admin/xwork/ray/raylab/experiments/05_recovery.py) 验证的点：持久化的值恢复，未持久化的值丢失。

### Q5：`ObjectRef` 是什么？`ray.get` 为什么是性能杀手？

- `ObjectRef` 是分布式对象存储里的**不可变对象的句柄**，把 task 的输入输出解耦成“数据流”，而非“调用返回值”。
- 把 `ObjectRef` 直接作为参数传给下游 task，**数据留在对象存储，不经过 Driver**，这叫 **zero-copy 传递**（同节点可共享内存）。
- 一旦 `ray.get()`，数据就被**拉回 Driver 并物化到本地内存**，并行度会坍缩，Driver 也会成为瓶颈。

**你 07 的代码正好用上了这个反面例子**：`ray.get([a.partial.remote(...)])` 把 3 个 Actor 的结果全拉回 Driver 再合并。面试时可以主动说明“这是为了教学验收，生产上应该再用一个 reduce Actor 或 `ray.get` 之外的方式合并”，**主动指出自己代码的局限，是最强的可信度信号**。

### Q6：Actor 的构造参数为什么能直接传 `ObjectRef`？

07 第 90 行 `VectorShard.remote(ref, i)`，`ref` 是 `ObjectRef`。Ray 会在 `__init__` 执行前自动解析，因此 Actor 内部拿到的是真正的 `np.ndarray`。这个细节能答出来，说明你真的读过文档，而不只是抄过示例。

### Q7：一个 Actor 串行处理，会不会成为吞吐瓶颈？怎么办？

- 计算密集：加 Actor 数量（`ActorPoolStrategy`）。
- IO 密集：`max_concurrency > 1` + `async def`，让单 Actor 内部并发。
- 07 里就是典型的**同步迭代（BSP）**：最慢的分片决定本轮何时结束，这叫 straggler。这是 KMeans 固有成本，而不是 Ray 的问题；分布式训练里对应的是 AllReduce 的同步开销。

---

# 四、第三层：调度与资源（区分“跑通”和“跑得省”）

### Q8：`num_gpus=0.5` 到底意味着什么？

**标准答案分三层**：
1. Ray 只做**逻辑记账**：`num_gpus=0.5` = 从该节点的资源池里扣 0.5。
2. Ray **不做物理隔离**：不会切分显存，也不会做 MIG、MPS，两个 Actor 会看到同一张完整卡。
3. 真隔离必须由外部负责：MIG、MPS、CUDA_VISIBLE_DEVICES、或一个进程一张卡。

**你的限制**：这台机器没有可见 NVIDIA GPU，02 只验证了记账和排队。**面试时必须这样说**：“我在无 GPU 环境验证的是调度记账语义，物理隔离我没测。”——这句话本身就是加分项。

### Q9：调度器怎么把任务分配到节点上？

对应 [06_autoscaler.py](file:///home/admin/xwork/ray/raylab/experiments/06_autoscaler.py)，源码入口 `python/ray/autoscaler/v2/scheduler.py`（需求装箱）和 `instance_manager/common.py`（合法状态转移）。

要点：**节点规格会直接影响利用率**。例如 3 个各需 0.5 GPU 的 Actor，在 1 GPU 节点上第三个必然排队；这是装箱问题，与代码无关。面试官常问“为什么我的利用率只有 50%”—— 答案往往就是**资源不可分割 + 任务尺寸不匹配**。

### Q10：Placement Group 解决什么问题？

两个标准用例：**故障域捆绑**（把 driver、worker 放在同一机架）和**防死锁**（多个 Actor 互相等资源时，默认调度会死锁，PACK、STRICT_PACK 可以保证全有或全无）。

---

# 五、第四层：Ray Data（最容易只剩背诵答案的地方）

### Q11：Dataset 的执行模型是什么？

关键词：**lazy、block、streaming executor、算子图从后往前拉取（pull-based）**。

`ds.map_batches(...)` 只建图不执行；`materialize()`、`take()`、`iter_batches()` 才触发执行。执行时从输出算子向输入反向请求，天然形成流水线。

### Q12：为什么推荐 `map_batches` 而不是 `map`？

**逐行调用的 Python 开销 >> 向量化计算**。你对 [03_data_pipeline.py](file:///home/admin/xwork/ray/raylab/experiments/03_data_pipeline.py) 改 `batch_size` 8/16/64 做一次实测，比背一百句“减少 Python 开销”都有用。这题能说出“我实测 batch size 从 8 调到 64 后，每行均摊的调度时间下降了 X”，面试官会立刻改变对你的评估。

### Q13：反压是谁给谁的？

这是**最容易被问倒、而你的 04 正好验证过**的题：

- 反压方向：**下游算子的处理能力 → 上游算子**。
- 触发点：对象存储预算（`resource_limits.object_store_memory`）+ 下游队列容量。
- 指标名：`task_submission_backpressure_time`、`task_output_backpressure_time`。
- **反压本身不能证明内存稳定**：04 的 note 里你写了“预算不是内存硬隔离”。这句话要说出来，因为面试官常拿“设了预算为什么还 OOM”来问。

---

# 六、第五层：容错（“Ray 会自动恢复”是错误答案）

### Q14：Ray 的容错有哪几种，边界在哪？

| 机制 | 恢复什么 | 不恢复什么 |
|---|---|---|
| Task retry | 失败的 task 重跑 | 外部副作用（已写入的数据、已发的请求） |
| Actor restart | 进程重建 | **内存状态**（需要自己持久化或 checkpoint） |
| Lineage reconstruction | 丢失的对象重建 | 非确定性函数会得到不同结果 |

对应 05：你先删掉持久化，看到值丢失，再恢复持久化，这种**先制造失败再修复**的过程要讲给面试官听。

### Q15：07 里 Actor 挂了会怎样？

**诚实的答案**：分片数据在 Actor 内存里，Actor 一挂，这部分数据就**丢了**；而要重建它，需要原始数据的 lineage 或 checkpoint，07 没做这个（`result.json` 的 note 里已经写明了）。生产实现要么分片来自可重放的存储，要么把分片持久化到对象存储。

**面试官问这题，考的就是你会不会夸大 Ray 的能力。老实说“这里不保证”，比编造一个“Ray 会自动恢复”要安全得多。**

---

# 七、第六层：可观测与排查（资深岗必问）

### Q16：作业变慢，你怎么定位？

按**从外到内**的顺序回答，不要只说“看 Dashboard”：

1. 是**等资源**还是**在计算**？看 task state（PENDING 就是调度排队）。
2. 如果是在计算，哪个算子慢？看 `stats()` 和算子指标（04 的 `collect_metrics` 就是一层层 `parents` 递归）。
3. 是**反压**还是**倾斜**？如果某几个 task 特别慢，说明数据倾斜。
4. 是**对象存储**问题吗？看 spill（对象存储满了会刷到磁盘，`/dev/shm` 只有 64 MiB 时尤其明显——你的 README 里记录了这点，这是很真实的生产经验）。
5. 是**启动开销**还是**稳定阶段**？你 README 里写的“比较性能时分开记录启动开销和稳定执行阶段”，这句话本身就是很成熟的工程判断。

### Q17：小对象太多怎么办？

对象存储有开销和元数据成本，应做**批量聚合**（batch、block 合并），而不是一味并行。07 的 `partials_to_driver_numeric_bytes` 就是让你直接看到“我传了多少字节”。

---

# 八、第七层：源码（你的优势，但要控制追问范围）

**只准备 3 条链路，不要试图通读整个 Ray。**

1. `ray.get()` 到拿回对象的路径：`ObjectRef` → core worker → 本地对象存储 / owner 拉取。
2. `@ray.remote` 到 Worker 执行的路径：函数序列化 → 提交到 GCS/raylet → 调度 → Worker 反序列化并执行。
3. **GCS（Global Control Store）**：集群元数据（Actor 表、节点表、资源表）的唯一来源，通常用 Redis 或内置 KV 存储。你之前的 GCS 分析记忆可以直接复用。

**追问陷阱**：面试官可能问“Raylet 和 GCS 谁负责调度”。正确回答是：**Raylet 执行任务级调度，GCS 负责元数据和 Actor 生命周期**，不要把两者混在一起。

---

# 九、把 raylab 变成“可引用的证据”（这是你的核心优势）

| 面试问题 | 你能给出的证据 | 引用文件 |
|---|---|---|
| 有状态计算为什么用 Actor | 跨轮 PID/instance 不变，每轮仅传 1656 B | [07_kmeans.py](file:///home/admin/xwork/ray/raylab/experiments/07_kmeans.py) |
| 0.5 GPU 的语义 | 前两个共享设备 ID，第三个排队 | [02_logical_gpu.py](file:///home/admin/xwork/ray/raylab/experiments/02_logical_gpu.py) |
| 反压是否真实 | `pressure_s > 0` 才算通过 | [04_backpressure.py](file:///home/admin/xwork/ray/raylab/experiments/04_backpressure.py#L56-L60) |
| Actor 重建丢什么 | 持久化恢复、非持久化丢失 | [05_recovery.py](file:///home/admin/xwork/ray/raylab/experiments/05_recovery.py) |
| 装箱与利用率 | 节点规格改变 → 新增节点数改变 | [06_autoscaler.py](file:///home/admin/xwork/ray/raylab/experiments/06_autoscaler.py) |
| 幂等写入与故障重放 | 逐 token 验证无重复无遗漏 | [08_llm_preprocess.py](file:///home/admin/xwork/ray/raylab/experiments/08_llm_preprocess.py) |

**表达模板**（面试时照着说）：

> “我在单机 4 CPU、256 MiB 对象存储的环境跑过一个固定分片 KMeans。结论是：Actor 状态跨轮复用让每轮通信只剩 1.6 KB。但我要说明，这个数字是 NumPy 数值载荷，不含序列化，也不含协议，单机还可能走共享内存，所以它不是网络流量的测量值。”

这段话的价值不在技术，而在**你知道自己测的是什么的边界**。面试官对“假精确”极度敏感，对“知道自己不知道”极度加分。

---

# 十、学习节奏（四周，每周围绕 4–5 个问题）

| 周 | 主题 | 自测标准 |
|---|---|---|
| 1 | 编程模型 + 调度 | 不看文档画出 Task/Actor/ObjectRef 的生命周期图，并回答 Q1–Q10 |
| 2 | Ray Data + 反压 + 恢复 | 改 04 的消费者延迟，预测反压计时变化，再验证 |
| 3 | 源码 3 条链路 + GCS | 能讲清 ray.get 的完整路径，能说出 Raylet 与 GCS 的分工 |
| 4 | 边界与实战 | 能回答 Q3（不该用的场景）+ Q16（排查）+ 设计题 |

**每天的自测方法**：挑一道上面的 Q，用“如果面试官反驳我，我拿什么证据”来检验。答不上来的就是第二天的实验任务。

---

# 十一、反向提问：问面试官比答对更能加分

面试结束前一定要问，这两题信息量最大：

1. “你们现在用的是 Ray Core 还是 Ray Data/Train/Serve？线上遇到的最大痛点是在调度、内存还是容错？”
2. “如果我要上手，你觉得最该先读哪一块源码？”

这两题逼面试官暴露真实的技术栈和真实痛点，能帮你判断岗位含金量，也能让面试官觉得你是“能用这个框架解决问题的人”，而不只是“会调 API 的人”。

---

# 十二、减分回答清单（自查用）

1. “Ray 是更快的 multiprocessing”：把调度器说成加速器，方向就错了。
2. “ObjectRef 就是变量”：混淆了值语义和引用语义。
3. “Actor 挂了 Ray 会自己恢复”：漏了“状态不恢复”这个关键限定。
4. “`num_gpus=0.5` 会切一半显存”：很容易被识破。
5. “Ray Data 比 Spark 快”：没有明确场景的对比等于没有信息。
6. **用单机环境的数字去推断生产网络的性能**：这是你要重点避免的。你的 README 已经写明“磁盘上的对象存储不能用于推导生产环境的内存传输性能”，面试时要主动复述这个限定。

---

**一句话总结**：你的 `raylab` 已经解决了“没有证据”的问题，接下来要做的是**给它配一套问题清单**——每个问题都要能说清“答案、反面情况、我的证据、证据的适用边界”。

需要我把上面 18 道题整理成一份可直接对照自测的 `raylab/INTERVIEW.md`，或者继续把某一道题（比如 Q13 反压、Q16 排查）拆成配合实验的可验证练习吗？
