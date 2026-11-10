# KMeans 与预训练数据准备：从运行结果理解执行过程

在 `labs/raylab` 运行。两个实验都使用真实 CPU 多进程 Ray，
不需要额外安装依赖、下载模型或预先执行 `ray start`。
每个实验结束都会关闭自己的本地集群，并在 `cleanup.json` 检查存活进程。

```bash
./run.sh run 07
./run.sh run 08
```

启动器会输出本次 `results/<UTC时间>/` 路径。先读 `result.json`，再看下面列出的明细。
UTC 目录时间换算到北京时间需要加 8 小时。

## 07：固定分片的 Actor KMeans

入口：`experiments/07_kmeans.py`。默认生成 12000 个 8 维 float64 向量，K=4，分成 3 片。
Driver 是提交任务的主 Python 进程，Actor 是保留实例和状态的 Worker。

```text
初始化一次：Driver → ray.put(分片) → Actor A/B/C

每一轮：Driver 发布中心
          ↓
        各 Actor：本地找最近中心，累计每类 sum/count 和 SSE
          ↓
        Driver：合并 sum/count，更新中心
          ↓
        中心移动足够小则结束，否则下一轮
```

1. 先看 `VectorShard.__init__`：向量只在构造时传入，保存在 `self.values`。
2. 再看 `partial`：输出的是每类的向量和、样本数、距离平方和，没有返回全部原始向量。
3. 最后看 `experiment` 的循环：Driver 发布新中心，等待所有分片，然后做一次全局更新。
   这是同步迭代；最慢的分片决定本轮何时结束。

SSE 是每个点到所属中心的距离平方和，越小表示对当前数据的拟合越紧。
日志中的 SSE 在**本轮更新中心之前**计算；下一轮通常不大于上一轮。
空簇保持原中心，中心移动不超过 `1e-8` 时结束，最多 30 轮。

### 如何读证据

- `iterations.json`：每轮类别计数、SSE、中心移动、Actor PID、数值载荷。
- `centers.npz`：初始中心、分布式最终中心、串行参考中心。
- `result.json`：所有 Actor 的固定实例 ID、输入大小、串行标签和中心对照结果。

默认原始向量大小为 `12000 × 8 × 8 = 768000` 字节。
每轮每个 Actor 接收 `4 × 8 × 8 = 256` 字节的中心，返回：

```text
sum：4 × 8 × 8 = 256 字节
count：4 × 8 = 32 字节
SSE：8 字节
合计：296 字节
```

3 个 Actor 的每轮逻辑数值载荷是 `3 × (256 + 296) = 1656` 字节。
这不包括序列化、协议、返回字典及元数据；单机可能共享内存，因此不是网络流量测量。
最终额外取回全部标签做正确性检查，也不属于上述迭代载荷。
Driver 为串行验收保留了这份小数据；生产实现不应因此推断全部数据必须留在 Driver。

串行参考使用相同初始中心、独立的距离计算及求均值路径。
逐元素检查中心、逐个检查标签，同时检查每轮样本计数和 Actor 身份。
KMeans 可能收敛到局部最优；与串行结果一致不代表得到了全局最优。

### 修改一个变量再观察

```bash
RAYLAB_KMEANS_SHARDS=1 ./run.sh run 07
RAYLAB_KMEANS_SHARDS=4 ./run.sh run 07
RAYLAB_KMEANS_ROWS=24000 ./run.sh run 07
```

先预测：增加行数会增大一次性输入和计算量，但 K、维数、Actor 数不变时，每轮数值载荷不变。
增加 Actor 数则会增大中心分发和统计量返回的总载荷，不保证这个小实验更快。
本实验不演示 Actor 丢失后的分片恢复；真正容错需要可重新读取的分片及迭代检查点。

## 08：预训练数据准备与失败重放

入口：`experiments/08_llm_preprocess.py`。
生成 64 篇本地 JSONL 文档，分布在 8 个输入文件中，其中 6 篇清洗后为空，保留 58 篇。

```text
读取 JSONL → 无状态清洗过滤 → 两个 Tokenizer Actor 分批编码
                                      ↓
                            materialize 缓存小规模分词结果
                                      ↓
                      groupby(shard_id)，发生数据交换
                                      ↓
                     每组按文档 ID 排序，拼接并补 PAD
                                      ↓
                      固定文件名写入 → 汇总 manifest
```

### 模型常驻和并发

先看 `ByteTokenizer.__init__` 和 `__call__`。
每个 Actor 初始化一次 256 项字节词表，之后跨批次复用。
ActorPool 大小为 2，每 Actor 最多 1 个在途任务、1 个并发调用。
输出记录词表实例 UUID、PID 和批次调用序号，验收要求至少一个实例处理过多个批次。
不要求两个 Actor 都分到同样多的数据，Ray 调度不保证平均分配。

上述是逻辑步骤，不是一条转换必定对应一个独立进程。
当前实际执行计划把清洗和分词合并成了同一个 Actor 算子：
`MapBatches(clean_batch)->MapBatches(ByteTokenizer)`。
可以对照 `console.log` 的 Execution plan 和 `tokenize_stats.txt` 理解算子融合。

编码规则是 `0=PAD`、`1=EOS`、UTF-8 字节加 2。每篇文档尾部加 EOS。
中文字符可能占多个字节，因此这里的 token 数不能当作真实模型的 BPE token 数。
HTML 清洗是教学正则，不是完整的 HTML 解析和网页正文提取。

### 为什么拼接必须确定

每篇文档用 `id % 4` 选择分片，在分片内部按文档 ID 排序。
默认每个样本 64 token，不足一段时补 PAD，并记录 `valid_length`。
训练时可以由这个长度构造 attention/loss mask；本实验不运行训练。

每个 token 还保存 `[文档ID, 文档内token位置]`，包括 EOS、不包括 PAD。
这是额外的教学审计字段，便于检查跨文档拼接边界和遗漏，生产中不必逐 token 保存。
不会把剩余 token 隐藏在 Actor 内存中，因此任务重放无需恢复一个隐式拼接缓冲区。
分组内排序使输出不依赖上游批次的完成顺序。

### 故障发生在哪一步

读 `pack_and_write_group`，观察以下顺序：

1. 构造确定内容，写入 PID 专属临时文件。
2. 通过本机文件系统的 `replace` 发布为固定分片文件。
3. 分片 1 首次执行时记录故障标记，然后 `os._exit(23)`。
4. Worker 在返回成功之前退出，Ray Data 按 `max_retries=2` 重新执行任务。
5. 重试发现文件已存在，检查字节完全相同后复用；如果内容不同就报错。
6. Driver 收齐所有成功回执、核验文件后才发布 `manifest.json`。

Ray 只负责重新执行。固定分片身份、确定内容和幂等写入由本实验实现。
一个底层任务可能处理多个组，失败后还可能重做同任务里的其他组；这些组也必须能重复执行。

### 如何证明没有重复或遗漏

- `shards/shard-*.jsonl`：实际训练样本，包含 token、长度和来源位置。
- `shards/manifest.json`：4 个分片的文件名、SHA256、样本数、有效 token 数。
- `shards/failure_after_commit.json`：第一次失败的 PID 和已写内容的校验值。
- `writer_receipts.json`：第一次执行和再次重放的 PID、文件复用状态、校验值。
- `tokenize_stats.txt`、`packing_stats.txt`：Ray Data 的执行统计。

验收不只比较样本数：

1. 与已知清洗文本构造的串行参考逐个样本比较，包含全部 token 和来源位置。
2. 要求所有来源位置唯一，与参考位置多重集合完全相同。
3. 要求故障前后 Worker PID 不同，重试复用的内容与故障标记中的 SHA256 一致。
4. 再执行一次下游，要求所有分片被复用，输出和 manifest 内容保持一致。

预期会出现 Worker 异常退出日志，最终以断言和 `result.json` 判断成功。
如果去掉文件存在检查改成追加，重试会制造重复数据；如果改动排序规则，参考比较会失败。

```bash
RAYLAB_LLM_SEQUENCE_LENGTH=128 ./run.sh run 08
RAYLAB_LLM_SEQUENCE_LENGTH=2048 ./run.sh run 08
```

先预测：改变样本长度不改变有效 token 总数，但会改变样本数、尾部 PAD 和文件校验值。

### 实验边界

这是小规模、单机本地文件实验。`materialize` 是显式物化边界，
`groupby` 需要数据交换且每个组必须能放入内存；不能把整个语料都当成一个组。
Driver 的 `take_all` 仅用于小数据验收。生产中应限制分片大小，用分布式校验和汇总结果。
没有实现全局去重、近似去重、真实 BPE、训练 rank 分配或训练断点恢复。

本机 `replace` 不等于对象存储上的原子重命名，也没有做 fsync 来验证断电持久性。
如果跨机器运行，需要所有 Worker 都能访问的持久存储。
对象存储通常应写不可变 attempt 文件，再通过受控清单提交决定可见版本。
本实验不证明并发 Driver、整机故障或跨节点情况下的 exactly-once 保证。

## 与 Spark 对照时，比较什么

| 问题 | 本实验的 Ray 组织 | Spark 中对应思路 |
| --- | --- | --- |
| KMeans 数据跨轮保留 | Actor 字段保存向量分片 | 缓存向量分区，迭代分发中心、局部聚合 |
| 模型跨批次复用 | Actor 显式拥有词表和调用状态 | 分区函数、Python Worker 缓存或推理 UDF |
| 拼接前汇聚数据 | `groupby` 后组内排序 | 按 key Shuffle，分区内按确定规则排序处理 |
| 处理进程失败 | Ray 重试 Task，输出逻辑必须可重放 | Spark 重试 Task，同样需要正确的输出提交机制 |

这里只实现 Ray 和串行参考，没有运行 Spark，不能据此得出速度或成本对比。
