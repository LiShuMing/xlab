# 聚合状态：内联、分离存储与延迟初始化

这是 [算子特化实验](SPECIALIZATIONS.md) 的下一步，聚焦 Hash Aggregate 的状态布局。
独立实现，不链接 StarRocks，也不将结果归为 StarRocks 性能。

## 源码依据与比较方式

参考本地 StarRocks revision `f977b53c13eab90425f552675f3b3463ada8b2fc`：

- `be/src/exec/aggregate/agg_hash_map.h:43,65`：表的 mapped value 是 `AggDataPtr`，即状态地址。
- 同文件 `:1060–1078`：`lazy_emplace` 回调内才调用 `allocate_func(key)`，命中已有分组时复用状态。
- 文件摘要与本地源码证据边界沿用 [source-reference.json](source-reference.json)。

本实验用 4 种实现拆开比较：

| 实现 | 哈希槽 / 节点 | 状态构造 | 扩容时状态 |
| --- | --- | --- | --- |
| `std` | 标准库 unordered_map 节点 | `try_emplace`，新分组才构造 | 节点状态保留 |
| `std-eager` | 同一个标准库容器 | 先构造状态参数再 `emplace` | 新插入时复制候选状态；rehash 保留节点 |
| `inline` | 键与完整状态内联的线性探测表 | 包括空槽在内的状态清零 | 搬迁已有分组状态 |
| `arena-lazy` | 键与 32 位状态索引的线性探测表 | 新分组才在 deque 构造状态 | 只搬迁键与索引，状态地址稳定 |

`std` 与 `std-eager` 是初始化 API 的对照；`inline` 与 `arena-lazy` 是布局的对照。
后者同时改变空槽初始化、状态搬迁和一次间接访问，不能将总体收益全归给其中一个原因。
所有方法使用相同整数混合哈希和 0.75 扩容阈值。deque 是标准库提供的分段存储，
不是 StarRocks 的内存池；对照结果还受标准库具体实现影响。

## 状态与输入

- **16 B**：COUNT、SUM 两个无符号 64 位数。
- **256 / 4096 B**：前 16 B 仍是 COUNT/SUM；其余分别为 30 / 510 个分桶 SUM。
  每个输入值映射到一个桶并更新，不是填充空白扩大结构体。加法按无符号 64 位回绕。
- **few-groups / many-groups**：65536 行，候选键池为 64 / 16384 个键，10% NULL。
  键池大小不等于最终实际分组数；实际数逐样本记录，NULL 形成一个独立分组。
- **unique**：16384 行全部不同、无 NULL，观察几乎没有状态复用的情形。
- **uniform / phases**：phases 四段等长：先使用 1/8 键域，再扩展到完整候选域，
  再偏向前 8 个键，最后迁移到末 8 个键。后期仍可能首次出现此前未抽中的键。

同一场景、种子的键、值和 NULL 轨迹不随方法或状态大小变化。比较不同状态大小时，
更新桶的数量、取模和访存方式也不同，因此不是只改变状态字节数的纯缓存实验。
本轮没有删除、状态淘汰、并行聚合或溢写。

## 运行与观测

```sh
CXX=clang++ python3 tools/run.py --suite states --build-dir .local/states-build
```

本机的非默认编译器复现命令：

```sh
python3 tools/run.py --suite states --build-dir .local/states-build \
  --compiler /opt/alibaba-cloud-compiler/bin/clang++ \
  '--cxx-flags=--gcc-toolchain=/apsara/alicpp/built/gcc-9.2.1-cxx98abi/gcc-9.2.1 -stdlib=libc++' \
  '--linker-flags=-L/opt/alibaba-cloud-compiler/lib64 -Wl,-rpath,/opt/alibaba-cloud-compiler/lib64' \
  --clean-build
```

矩阵为 180 个任务，每任务 5 次至少 20ms 的批量测量，3 个种子，共 900 样本、60 组汇总。
结果写入 `.local/results/<timestamp>/report.html`，同时保存 CSV、运行清单、日志和源码/二进制摘要。
不依赖 perfect_hash、StarRocks、网络、特权计数器或第三方 Python 包。
报告沿用本实验内的离线样式和筛选脚本；运行时不依赖技能目录。

整流墙钟与进程 CPU 耗时包含建表、更新、扩容、销毁。每轮从空表开始，输入生成和键编码在计时外。
四个阶段各记录墙钟/CPU 的 ns/输入行，以及计时外诊断的新分组数、扩容次数。
阶段计时包含当段插入和扩容，不包含初始表创建、最终销毁及部分计时开销，不能直接相加还原整流时间。
分段计时需要读取时钟，整流数字包含这些开销；数据是批量均值，不是单操作 P99。

内存诊断：

- 存活/峰值是对象大小与分配器请求字节；峰值捕获扩容时旧、新数组共存。
- 累计申请字节包含已释放请求；不代表峰值。分配器元数据、输入和校验参考状态不计入。
- 逻辑初始化字节按源码状态清零需求计数，不代表硬件实际写流量，编译器可能消除或合并写入。
- 搬迁字节只统计完整状态；不含键与索引。`std-eager` 的新候选复制也计入。
- 诊断采用编译期启用计数的单独实例；计时实例关闭这些计数。两者做相同的结构操作。

每个任务计时前检查所有分组的每个桶，计时中再次检查流式校验和；
测试额外覆盖全 NULL、普通键 0/最大整数、冲突回绕、扩容状态完整性及分离状态地址稳定性。
共享主机的波动在报告中展示，不据此推断缓存失效或 CPU 调度根因。

下一轮可在已观测的布局差异上增加批量哈希与预取距离实验，并单独控制工作集规模。
