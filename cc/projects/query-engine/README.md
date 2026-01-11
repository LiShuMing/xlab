0. 第一性原理：这个项目到底在练什么？

你要练的核心不是“写一个能 group by 的程序”，而是：
	1.	列式执行的热路径是什么？
扫描 → 解码 → 过滤 → 计算 key/hash → probe/insert → 聚合 update → 输出。
	2.	Hash Agg 的瓶颈本质是什么？
	•	高基数：hash table probe/insert 成本 + cache miss
	•	低基数：聚合 update 的算术开销、分支、SIMD 机会
	•	关键资源：内存带宽 + cache + 分支预测（CPU 才不是只会算加法）
	3.	系统设计层面：为什么要“可扩展算子框架”？
因为你后续一定会加：Filter / Project / Join / TopN / Exchange（可选）。
如果不先定好接口，你后续每加一个算子都要推倒重来。

⸻

1) 项目总体架构（建议对齐 Velox/DuckDB 的最小集合）

1.1 目录结构（强制输出给 Claude）

vagg/
  CMakeLists.txt
  cmake/
  include/vagg/
    common/status.h
    common/slice.h
    common/likely.h
    exec/operator.h
    exec/pipeline.h
    exec/driver.h
    exec/context.h
    vector/vector.h
    vector/selection.h
    vector/types.h
    io/csv_reader.h
    io/data_source.h
    ht/hash_table.h
    ht/hash.h
    agg/aggregator.h
    agg/aggregate_functions.h
    ops/scan_op.h
    ops/project_op.h
    ops/aggregate_op.h
    ops/sink_op.h
    util/arena.h
    util/timer.h
    util/prefetch.h
  src/...
  tests/...
  bench/...
  tools/
    run_instruments.md
  docs/
    design.md

1.2 关键抽象（最少但能扩展）
	•	Vector（列向量）：Vector<T> + ValidityBitmap + SelectionVector
	•	Batch / Chunk（列批）：一组列向量（RowCount N），典型 N=1024/4096
	•	Operator：Next() 产出 Chunk
	•	Pipeline/Driver：串联算子形成执行链（Morsel/pipeline 可以后续加）

你做的是“单机最小可用框架”，不要上来就搞复杂调度。

⸻

2) 数据模型与列式布局（Columnar Layout）

2.1 支持类型（先做极简）
	•	k: int32 或 int64
	•	v: int64（sum 结果避免溢出）
	•	可选：nullable（Phase 2 再加）

2.2 向量表示（Velox/DuckDB 风格）
	•	FlatVector<T>：连续数组 T* data
	•	ValidityBitmap：bitset 标记 null
	•	SelectionVector：支持过滤后“逻辑行号”

2.3 为什么要 selection vector？

因为 Filter/Join 会制造稀疏数据，避免复制。

⸻

3) HashTable 设计：Agg + Join 两用（项目核心）

你要一个可复用的 HashTable，能支持：
	•	Agg：find_or_insert(key) -> entry*
	•	Join：build(key, payload) + probe(key) -> iterator

3.1 第一个版本选型：Robin Hood + open addressing（推荐）

原因：
	•	cache-friendly（连续 probe）
	•	高性能、实现难度适中
	•	适合单 key（int32/int64）场景

结构（建议）：
	•	控制字节（control bytes）+ payload arrays（SoA）
	•	或者 AoS entry（简单但 cache 差一点）

MVP 版本：AoS entry 也可以，但要设计升级路径。

3.2 控制字节（重要：减少分支）

类似 SwissTable 的思路：
	•	每个 slot 有 1 byte tag（hash 高 7bits + occupancy）
	•	probe 时先扫 tag，再比较 key
	•	NEON/AVX 可以一次对 16 bytes 做 compare（Phase 3）

3.3 负载因子与扩容
	•	max_load_factor = 0.7~0.85
	•	扩容必须 rehash
	•	设计 Rehash()，并在 bench 里观察扩容抖动

3.4 Prefetch（非常适合练）
	•	对 key 做 hash 后，计算 slot index
	•	__builtin_prefetch(&ctrl[index])
	•	在 probe loop 中预取下一段 ctrl

你会发现：prefetch 对高基数 group by 非常关键。

⸻

4) Hash Aggregation 算法：从正确到快

4.1 MVP：每行逐个更新（scalar）

流程：
	1.	Scan 读取 chunk（k,v）
	2.	对每行：
	•	h = hash(k)
	•	entry = ht.find_or_insert(k, h)
	•	entry->sum += v

4.2 Phase 2：批量 hash + 批量 probe（减少分支）
	•	先对 chunk 的所有 k 计算 hash 数组 hashes[N]
	•	再 probe/insert
好处：能更好流水线化；prefetch 更容易安排。

4.3 Phase 3：局部聚合（local pre-aggregation）

对高重复 key 的数据非常有效：
	•	用小的 local hash（L1-friendly）先聚合
	•	再 merge 到 global hash

这能练到 ClickHouse/DuckDB 常用套路。

⸻

5) Query Engine 框架（可扩展算子）

5.1 算子接口（极简版）

class Operator {
 public:
  virtual ~Operator() = default;
  virtual Status Prepare(ExecContext*) = 0;
  virtual Status Next(Chunk* out) = 0;   // out empty => end
};

5.2 具体算子
	•	ScanOp：从 CSV 或内存表读取，输出 chunk
	•	ProjectOp：可先不做
	•	HashAggOp：消费 child chunk，内部 build HT，最后输出结果 chunk
	•	SinkOp：收集结果，打印/写出

HashAgg 是 blocking operator：要消费完全部 input 才能 output。

⸻

6) macOS Instruments 验证路径（写进项目）

你要让项目“可验证”，不是“我觉得它很快”。

你需要固定的 bench + 观测点：
	•	Throughput（rows/s）
	•	CPU utilization
	•	cache miss / branch miss（Instruments）
	•	HT probe 次数、miss 次数、平均探测长度

⸻

7) Benchmarks（Google Benchmark）与数据生成器

必须提供数据生成器（否则你测不出东西）：
	•	uniform keys（高基数）
	•	zipf keys（热点）
	•	low cardinality keys（重复高）
	•	sorted keys（对 hash 不友好但对 locality 有影响）

Benchmark 场景：
	1.	BM_Agg_LowCardinality
	2.	BM_Agg_HighCardinality
	3.	BM_Agg_Zipf
	4.	BM_HashTable_InsertOnly
	5.	BM_HashTable_FindOnly

⸻

8) 建议你加的“工程加分项”（对技能提升巨大）

这些不是必须，但非常值：
	1.	Arena allocator：HashTable entry 与 vector buffer 都从 arena 分配
	2.	Result/Status：明确错误路径（OOM、bad input）
	3.	Checksum / Verify 模式：在 debug 构建下对 HT invariants 做强校验
	4.	统计模块：probe length 分布、rehash 次数、load factor