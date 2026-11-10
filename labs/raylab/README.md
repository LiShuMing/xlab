# 当前机器的 Ray 学习实验室

前置条件：Linux、Python 3.11，以及已安装 Ray 和 NumPy 的 Python 环境。
实验位于本仓库的 `labs/raylab/`；虚拟环境、临时文件和结果保留在该目录的忽略路径中。
设置 `RAYLAB_BASE_PYTHON` 指向已有解释器，再通过独立 `.venv` 补充学习依赖。
不需要重新编译 Ray，不安装到系统 Python，也不修改已有 Conda 包。

## 开始使用

```bash
cd labs/raylab
./run.sh doctor       # 检查解释器、依赖和源码位置
./run.sh list         # 列出实验
./run.sh run 01       # 从 Task / Actor 开始
./run.sh run 02       # 逻辑 GPU 调度
./run.sh run 03       # 批量推理
./run.sh run 04       # 反压
./run.sh run 05       # 故障恢复
./run.sh run 06       # 装箱与实例状态机
./run.sh run 07       # 固定分片 Actor KMeans
./run.sh run 08       # 预训练数据准备、确定性拼接及失败重放
./run.sh run 09       # 执行计划、算子融合与流水线重叠
./run.sh run 10       # shuffle 路径、分区数与倾斜
./run.sh run 11       # 多模态：图像/音频/文本
./run.sh run 13       # 两节点副本生命周期（12 预留给对象 spill 实验）
./run.sh run all      # 顺序运行；失败时停止，先检查该实验
```

每个实验默认 180 秒超时，可以用 `./run.sh run 04 --timeout 240` 调整。
也可以从仓库根目录激活环境后自己写代码：

```bash
source labs/raylab/env.sh
python -c 'import ray; print(ray.__version__, ray.__file__)'
```

必要时使用 `./setup.sh` 补齐依赖。它需要下载依赖，但不会重新安装或编译 Ray。
此环境通过 `--system-site-packages` 复用已有源码安装和基础包；它不是可直接迁往另一台机器的独立发行包。
每次运行会记录源码 HEAD、Ray 导入路径和依赖版本；源码 HEAD 不等于原生二进制的已验证构建提交。

## 实验顺序与观察点

| 实验 | 做什么 | 看什么 | 建议修改 |
| --- | --- | --- | --- |
| 01 `core` | 8 个任务、ObjectRef 依赖、有状态 Actor | Task 在 Worker 进程执行；Actor 的多次调用复用同一进程和状态 | CPU 从 2 改成 1 或 4；改变任务耗时 |
| 02 `logical_gpu` | 声明 1 个逻辑 GPU，启动三个各需 0.5 GPU 的 Actor | 前两个共享设备 ID；第三个等待，释放资源后运行 | 改成 0.25；观察空闲 Actor 是否仍占资源 |
| 03 `data_pipeline` | 两个模型 Actor，用 NumPy 做批量计算并写 Parquet | 模型实例 ID、Actor PID、每实例调用次数、输出正确性 | batch size 8/16/64；Actor 数 1/2/4 |
| 04 `backpressure` | 快生产者产生约 64 MiB 中间数据，慢消费者处理 | `stats.txt` 和实际 task submission/output backpressure 指标 | 消费者延迟、Actor 数、对象存储调度预算 |
| 05 `recovery` | 自己的任务进程故意退出；自己的 Actor 被终止后重建 | 任务 PID 改变；持久化值恢复，未持久化值丢失 | 禁用重试或重启；去掉持久化；观察错误 |
| 06 `autoscaler` | 调用源码装箱算法和合法状态转移表 | 新增节点数、启动中容量、节点上限、单节点 GPU 限制 | 节点规格、需求数量、状态转移 |
| 07 `kmeans` | 3 个 Actor 各持有固定向量分片，多轮合并 sum/count | Actor 跨轮身份、SSE、中心移动、数值载荷大小、串行对照 | `RAYLAB_KMEANS_SHARDS=2`、`RAYLAB_KMEANS_ROWS=16000` |
| 08 `llm_preprocess` | 清洗 JSONL、Actor 分词、按固定分片拼接、幂等写入 | 写完 后退出的 Worker 被重试；逐 token 验证无重复和遗漏 | `RAYLAB_LLM_SEQUENCE_LENGTH=128`；观察 PAD 和分片数 |
| 09 `operators` | 读四段执行计划、看融合、量算子级并行度与算子间时间重叠 | 逻辑 3 个算子被融合成 1 个；重分区后下游 task 数跟分区数走；上游 ActorPool 不断开融合时，两个算子时间区间相交 | 去掉 `repartition` 看融合；把中间算子改成 ActorPool 看融合断点；调 `override_num_blocks` |
| 10 `shuffle` | 五条 shuffle 路径的物理算子名、分区数、task 粒度、热 key 倾斜 | 按 key 走 `HashShuffleOperator`，无 key/sort/随机走 `AllToAllOperator`；上游 8/16 个 task 都只出 3 个分区；热 key 在 4 和 8 分区下最大分区占比都是 0.957 | 把 `group` 改成 `doc_id` 看倾斜消失；把 `repartition` 换成 `sort` 看耗时变化 |
| 11 `multimodal` | 现场生成真 PNG/WAV，与文本混存，再看列裁剪与按模态解码 | 只选 `text` 列时块字节降到 1/96；图像/音频/文本三个解码算子资源请求不同；把 bytes 列带进 shuffle 与先窄化再 shuffle 的体积差 110 倍 | 改 `IMAGE_SIDE` 看字节占比；把 `num_cpus` 改成 2 看调度；对未窄化的数据做 `groupby` 看搬运量 |
| 13 `object_lifecycle` | 用 loopback 起两个真实节点，观察对象副本如何产生与消失 | 产生后只有生产者一份；同节点 3 个 task 共用同一份；driver 跨节点 `get` 后 `node_ids` 从 1 变 2、head 的 Plasma 多 8 MiB；删除引用后回落到 0 | 把 `ray.wait` 的 `fetch_local` 改成默认值，看第 1 阶段就出现两份；把 `PAYLOAD_BYTES` 调大看拉取耗时 |

03 的“模型”是常驻的 NumPy 参数，不依赖 PyTorch、模型下载或真实 GPU。
04 要求实际观测到反压计时大于零才算通过；仅仅设置慢消费者不算反压证据。
05 会出现预期的 Worker 异常退出日志，这是故障注入的一部分。以 `result.json` 的断言结果判断。
06 运行真实算法，但只在内存中模拟节点状态，不申请云主机或 Kubernetes Pod。
07 的通信记录是 NumPy 数值载荷大小，不是实际网络流量；串行 NumPy 对照不等于 Spark 对照。
08 使用可逆的 UTF-8 字节分词器，无需下载模型，不是 BPE。只验证单机文件提交与 Worker 故障，不验证跨节点恢复。
09 的并行度结论只对 `repartition` 之后的算子成立；流水线重叠只证明单机两个算子可同时在跑，不等于跨节点线性加速。
10 的耗时不能当吞吐指标：64 行数据下 hash shuffle 的秒数主要是聚合器 Actor 启动开销。倾斜结论依赖“分组键本身就是热维度”这个前提。
11 的 PNG/WAV 是标准库现场生成的真实编码，解码也用标准库完成；没有 PIL、torch 或 GPU，所以不是多模态模型推理基准。
13 的两个节点是同一台机器上的两个 Ray 进程（head 与本机 loopback 地址），走完整网络栈但不出物理网卡，因此只证明位置语义，不做带宽或延迟测量。
13 的“释放”以 Plasma 用量变化作为观测量，因为对象一旦删除就没有 ObjectRef 可用来查询位置。
13 需要独占 GCS（Global Control Store）端口 6379，启动前会检测占用并直接失败，不会去杀别人的集群。

### 与 MPP SQL 执行机制对位

09 和 10 是照着“拿 Ray Data 去对位 MPP（Massively Parallel Processing）SQL 引擎”这个目标设计的，对位关系如下：

| 阶段 | MPP SQL 引擎中的常见机制 | Ray Data（09/10 里可观测的入口） |
| --- | --- | --- |
| 逻辑计划 | SQL AST → 逻辑算子 | Python API 链，`explain_plan` 第一段 |
| 规则优化 | 谓词/列裁剪下推、常量折叠等 | 6 条规则：`LimitPushdownRule`、`ProjectionPushdown`、`PredicatePushdown`、`CombineShuffles`、`CombineDownloads`、`PushdownCountFiles` |
| 物理计划 | 按代价选 join 顺序、选算子实现 | `planner.py` 用类型路由表翻译，不做代价搜索 |
| 物理优化 | 将相邻算子融合到同一个执行任务 | 4 条规则，其中 `FuseOperators` 把连续 map 合并成一个 task 函数 |
| 并行度 | 由分区数（shuffle 决定）决定整个 stage | **算子级**：每个算子按自己的 block 数并行（10 的 `partition_arity`） |
| stage 边界 | shuffle 是硬屏障，上下游不重叠 | shuffle 仍是边界，但非 shuffle 段上下游可流水（09 的 `pipeline_overlap`） |
| shuffle 实现 | 排序/SortMerge，或 hash 分区 + 多路归并 | 默认 `HASH_SHUFFLE`：hash 分区 + 长驻聚合器 Actor；`sort`/`random_shuffle`/无 key 重分区才走基于排序的 exchange |
| 倾斜 | 靠统计信息与运行时动态调整 | 只做固定 `partition_id % num_aggregators` 映射，不自动打散热 key |

此表用于理解机制，不代表特定数据库产品的实现或性能。规则数量和局部实现只能说明
本文所读 Ray 版本的路径，不能单独推导整个系统的优化能力或性能收益。

07、08 的执行流程、结果解读和修改练习见 [进阶实验说明](TUTORIAL.md)。

## 结果与日志

每次运行生成独立目录：

```text
results/<UTC时间>/
  environment.json             Python / Ray / 依赖 / 源码版本
  summary.json                 每个已运行实验的结果、退出码和耗时
  01_core/                     其他实验同理
    console.log                完整终端输出
    result.json                断言结果和观测值
    runner.json                进程退出码、超时等
    process.json               本次实验进程 PID 和启动时间
    ray_session.json           本次 Ray 会话地址与日志目录
    cleanup.json               本实验子进程身份与退出后的存活检查
```

Ray 内部日志在 `tmp/session_*/logs/`。当前 `/tmp` 剩余空间少，实验会将临时文件放到此实验目录所在磁盘。
真实服务执行时发现 `/dev/shm` 约 64 MiB，256 MiB 对象存储因此退回实验磁盘。
这是功能学习环境；磁盘上的对象存储不能用于推导生产环境的内存传输性能。
日期目录使用 UTC；机器内部 Ray 日志可能使用另一时区，比较时注意转换。

## 运行范围

- 每个运行时实验创建自己的本地集群，默认 4 CPU、256 MiB 对象存储；01 使用 2 CPU。
- 禁用 Dashboard 和使用统计，不连接已有集群。实验结束调用自己的 `ray.shutdown()`。
- 启动器超时会先向本次创建的进程组发送 SIGTERM，给清理留出时间；不使用全机 `ray stop --force`。
- Ray 需要监听本机端口。如果在限制 socket 的沙箱内执行，GCS 可能启动失败；在有本机监听权限的服务器终端运行。
- 不使用 `local_mode=True`，任务和 Actor 在真实 Worker 进程中运行。
- 当前机器没有可见 NVIDIA GPU：02 只验证逻辑资源记账和队列，不验证 CUDA、MIG/MPS、显存争用或 GPU 性能。
- 单机文件恢复不等于跨机器高可用；真实抢占恢复需要共享持久存储。

## 源码阅读入口

可选源码阅读使用独立的 [Ray 公开源码仓库](https://github.com/ray-project/ray)，
以其检出目录为 `$RAY_SOURCE_ROOT`；运行实验只使用已安装的 Ray，不导入源码 checkout。
以下路径相对于该源码仓库：

- `python/ray/data/dataset.py`：`map_batches`、批次格式和资源声明。
- `python/ray/data/_internal/util.py`：`explain_plan`，一次打印四段执行计划（09 的入口）。
- `python/ray/data/_internal/logical/optimizers.py`：逻辑与物理两套规则集。
- `python/ray/data/_internal/logical/rules/operator_fusion.py`：`FuseOperators`，融合的充分条件。
- `python/ray/data/_internal/execution/operators/hash_shuffle.py`：`HashShufflingOperatorBase` 与聚合器 Actor。
- `python/ray/data/_internal/compute.py`：TaskPoolStrategy / ActorPoolStrategy。
- `python/ray/data/_internal/execution/backpressure_policy/`：资源预算和下游容量反压。
- `python/ray/autoscaler/v2/scheduler.py`：需求装箱。
- `python/ray/autoscaler/v2/instance_manager/common.py`：合法实例状态转移。
- `python/ray/autoscaler/v2/instance_manager/reconciler.py`：外部状态同步、超时和启动限流。

每次只改一个变量，先预测结果，再看实际观测。比较性能时分开记录启动开销和稳定执行阶段。
