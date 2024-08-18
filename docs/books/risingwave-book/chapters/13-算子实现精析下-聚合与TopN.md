# 第 13 章 · 算子实现精析（下）——聚合与 TopN

> **核心源码**：
> - `src/stream/src/executor/aggregate/hash_agg.rs` — `HashAggExecutor`、`AggGroupCache`（710 行）
> - `src/stream/src/executor/aggregate/simple_agg.rs` — `SimpleAggExecutor`（589 行）
> - `src/stream/src/executor/aggregate/agg_group.rs` — `AggGroup`、`Strategy`、`GroupKey`（626 行）
> - `src/stream/src/executor/aggregate/agg_state.rs` — `AggState`、`AggStateStorage`（157 行）
> - `src/stream/src/executor/mview/materialize.rs` — `MaterializeExecutor`、冲突检测（2521 行）
> - `src/stream/src/executor/top_n/top_n_plain.rs` — `TopNExecutor`（1215 行）
> - `src/stream/src/executor/top_n/group_top_n.rs` — `GroupTopNExecutor`（723 行）
> - `src/stream/src/executor/top_n/top_n_appendonly.rs` — `AppendOnlyTopNExecutor`（388 行）
> - `src/stream/src/executor/top_n/top_n_cache.rs` — `TopNCache`（low/middle/high 三段缓存）
> - `src/stream/src/executor/top_n/top_n_state.rs` — `ManagedTopNState`
> - `src/stream/src/executor/over_window/general.rs` — `OverWindowExecutor`（724 行）
> - `src/stream/src/executor/over_window/eowc.rs` — `EowcOverWindowExecutor`（624 行）
> - `src/stream/src/executor/over_window/over_partition.rs` — `OverPartition`、`PartitionDelta`
> - `src/stream/src/executor/over_window/frame_finder.rs` — 窗口帧范围计算（1583 行）
> - `src/stream/src/executor/gap_fill.rs` — `GapFillExecutor`（1855 行）
> - `src/stream/src/executor/approx_percentile/` — 两阶段近似百分位计算
> **关键特征**：这些算子都需要维护跨 Barrier 持久化的状态表，且状态的结构和更新逻辑比连接算子更加多样

---

## 13.1 聚合算子的两极：SimpleAgg 与 HashAgg

流式聚合是 RisingWave 中最核心的有状态算子之一。它有两种形态：

- **SimpleAggExecutor**：无 GROUP BY 的全局聚合（如 `SELECT count(*), sum(amount) FROM orders`）
- **HashAggExecutor**：带 GROUP BY 的分组聚合（如 `SELECT region, count(*) FROM orders GROUP BY region`）

两者共享相同的 `AggGroup` 抽象（聚合状态管理），但在状态缓存、分组管理和输出策略上有显著差异。

> **第一性原理思考**：批处理聚合是一个"全量输入 → 单次输出"的过程。流式聚合则是一个"增量输入 → 增量输出"的过程。每次新数据到达时，聚合状态需要**更新**而非**重算**，且需要输出**变化量**（changelog）而非**最终结果**。这意味着流式聚合必须：① 维护可增量更新的状态；② 追踪"旧值 → 新值"的变化以输出正确的 Insert/Delete/Update。

---

## 13.2 AggState——单个聚合调用的状态

`AggState`（`agg_state.rs:49-56`）是聚合状态的最小单元：

```rust
pub enum AggState {
    /// 单标量值状态，如 count、sum、append-only 的 min/max
    Value(AggregateState),
    /// 物化输入行状态，如非 append-only 的 min/max、string_agg
    MaterializedInput(Box<MaterializedInputState>),
}
```

两种存储模式对应 `AggStateStorage`（`agg_state.rs:33-45`）：

```rust
pub enum AggStateStorage<S: StateStore> {
    /// 状态作为值存储在中间状态表中
    Value,
    /// 状态作为输入行的物化存储，在独立的状态表中
    MaterializedInput {
        table: StateTable<S>,
        mapping: StateTableColumnMapping,
        order_columns: Vec<ColumnOrder>,
    },
}
```

**为什么需要两种存储？**

- `Value` 模式：count/sum 等聚合可以仅用一个标量值表示（如 count=42, sum=1000），更新操作是 O(1) 的
- `MaterializedInput` 模式：min/max 在非 append-only 流中，删除操作可能导致最小值/最大值变化，必须保留所有输入行才能在删除时找到新的极值。类似地，`string_agg` 需要保留所有参与聚合的行

`apply_chunk` 方法（`agg_state.rs:105-124`）展示了两种模式的更新逻辑：

```
Value 模式:   对 chunk 投影后调用 func.update(state, &chunk)
Minput 模式:  将 chunk（带 visibility）直接写入 MaterializedInput 状态
```

---

## 13.3 AggGroup——一组聚合调用的状态管理

`AggGroup<S, Strtg>`（`agg_group.rs:209-230`）管理一个分组键下的所有聚合调用状态：

```rust
pub struct AggGroup<S: StateStore, Strtg: Strategy> {
    ctx: Context,                         // 包含 group_key
    states: Vec<AggState>,                // 每个聚合调用对应一个 AggState
    prev_inter_states: Option<OwnedRow>,  // 上一轮中间状态
    prev_outputs: Option<OwnedRow>,       // 上一轮输出结果
    row_count_index: usize,               // count(*) 的索引位置
    emit_on_window_close: bool,           // 是否 EOWC 模式
}
```

### 13.3.1 Strategy——输出策略

`AggGroup` 的泛型参数 `Strtg: Strategy` 决定了何时输出聚合结果：

```rust
pub trait Strategy {
    fn infer_change_type(
        ctx: &Context,
        prev_row: Option<&OwnedRow>,
        curr_row: &OwnedRow,
        row_count_col: usize,
    ) -> Option<RecordType>;
}
```

两种策略：

| 策略 | 使用场景 | 行为 |
|------|---------|------|
| `AlwaysOutput` | SimpleAgg | 无论 row_count 是否为 0，始终输出（即使结果是 0/NULL） |
| `OnlyOutputIfHasInput` | HashAgg | 仅在有输入行时输出；row_count 降到 0 时输出 Delete |

`OnlyOutputIfHasInput` 的四状态决策（`agg_group.rs:131-165`）：

```
(prev_row_count, curr_row_count) → 输出
(0, 0) → None（无输出）
(0, _) → Insert（新分组出现）
(_, 0) → Delete（分组消失）
(_, _) → Update（如果新旧值不同）
```

这个设计确保了 HashAgg 不会在没有任何输入行时输出空聚合结果——这在流式系统中很重要，因为空结果行不应该被物化。

### 13.3.2 build_states_change 与 build_outputs_change

`AggGroup` 的核心输出逻辑分为两层：

1. **`build_states_change`**（`agg_group.rs:473-536`）：生成中间状态的变更（写入 `intermediate_state_table`），用于持久化
2. **`build_outputs_change`**（`agg_group.rs:545-610`）：生成最终输出的变更（yield 给下游），需要从 `MaterializedInput` 状态中计算实际输出

两层分离的原因：中间状态是编码后的标量值（紧凑），最终输出是解码后的用户可见值（可能需要重新计算 min/max）。

---

## 13.4 SimpleAggExecutor——全局聚合

`SimpleAggExecutor`（`simple_agg.rs:42-45`）维护**单个** `AggGroup`（无 group key）：

```rust
pub struct SimpleAggExecutor<S: StateStore> {
    input: Executor,
    inner: ExecutorInner<S>,
}
```

执行流程：

```
① 收到 Chunk → apply_chunk:
   - 计算 agg_call_filter_res（过滤条件）
   - Distinct 去重
   - 写入 MaterializedInput 状态表
   - 更新 AggGroup 的所有 AggState

② 收到 Barrier → flush_data:
   - flush distinct 去重状态
   - build_states_change → 写入 intermediate_state_table
   - build_outputs_change → 生成输出 StreamChunk
   - commit 所有状态表
```

SimpleAgg 的一个重要特性是 `must_output_per_barrier`——每个 Barrier 都必须输出结果，即使值没有变化。这个特性是为 `approx_percentile` 的两阶段聚合设计的：Local 阶段输出桶计数，Global 阶段需要 Local 在每个 epoch 都输出，否则 `RowMergeExecutor` 无法组合完整的行。

### 13.4.1 Noop Update 优化

对于非 `must_output_per_barrier` 的场景，SimpleAgg 做了一个优化（`simple_agg.rs:216-223`）：

```rust
if !this.must_output_per_barrier
    && let Record::Update { old_row, new_row } = &change
    && old_row == new_row
{
    None  // 旧值等于新值 → 不输出
}
```

避免输出无意义的 `UpdateDelete + UpdateInsert`。

---

## 13.5 HashAggExecutor——分组聚合

`HashAggExecutor`（`hash_agg.rs:64-67`）是 SimpleAgg 的分组版本，复杂度大幅增加：

```rust
pub struct HashAggExecutor<K: HashKey, S: StateStore> {
    input: Executor,
    inner: ExecutorInner<K, S>,
}
```

### 13.5.1 分组状态缓存

HashAgg 最核心的设计是 `AggGroupCache`——一个 LRU 缓存（`hash_agg.rs:52`）：

```rust
type AggGroupCache<K, S> = ManagedLruCache<K, Option<BoxedAggGroup<S>>, PrecomputedBuildHasher>;
```

为什么需要 LRU 缓存？因为分组数可能远大于内存容量。如果一个查询有 100 万个分组，不可能把所有 `AggGroup` 都放在内存里。LRU 缓存只保留最近活跃的分组，不活跃的分组状态保存在 `intermediate_state_table` 中。

### 13.5.2 Dirty Groups 机制

HashAgg 引入了 `dirty_groups`（`hash_agg.rs:148`）——当前 epoch 中被修改的分组：

```rust
dirty_groups: EstimatedHashMap<K, BoxedAggGroup<S>>,
```

当新 Chunk 到达时（`apply_chunk`，`hash_agg.rs:332-409`）：

```
① 从 Chunk 中提取 group key → 计算每个 group 的 visibility bitmap
② touch_agg_groups: 将涉及的 AggGroup 移入 dirty_groups
   - 如果在 LRU 缓存中 → 移出缓存，放入 dirty_groups
   - 如果不在缓存中 → 从 intermediate_state_table 恢复
③ 对每个 group:
   - 计算 agg_call 过滤 visibility
   - Distinct 去重
   - 写入 MaterializedInput 状态表
   - apply_chunk 到 AggGroup
④ 检查 dirty_groups 堆大小，超过阈值则提前 flush（防 OOM）
```

`touch_agg_groups` 的设计（`hash_agg.rs:260-330`）尤其精妙：

```
if dirty_groups.contains_key(key) → 已经在 dirty 中，跳过
if agg_group_cache.get_mut(key) → 从缓存移入 dirty
else → cache miss → 异步从状态表恢复（最多 10 个并发）
```

### 13.5.3 flush_data——Barrier 时的双重刷新

`flush_data`（`hash_agg.rs:411-514`）做两件事：

```
① 写入中间状态变更到 intermediate_state_table
   - 对每个 dirty group 调用 build_states_change
   - EOWC 模式 → 写入 SortBuffer
   - 非 EOWC 模式 → 直接写入状态表

② 生成输出
   - EOWC 模式 → 从 SortBuffer 中消费 watermark 以下的分组，逐个输出 Insert
   - 非 EOWC 模式 → 对每个 dirty group 调用 build_outputs_change

③ 将 dirty groups 移回 LRU 缓存
```

### 13.5.4 Emit On Window Close (EOWC)

HashAgg 支持一种特殊的输出模式：**只在窗口关闭时输出**。当 `emit_on_window_close = true` 时，聚合结果不会在每次数据到达时立即输出，而是等到 Watermark 推进到窗口结束时间后才输出。

这需要 `SortBuffer`（`eowc/sort_buffer.rs`）——一个按窗口列排序的缓冲区，存储每个分组的中间状态。当 Watermark 推进时，SortBuffer 中所有窗口结束时间早于 Watermark 的分组被取出并输出。

EOWC 的语义保证：**在窗口关闭前，不输出任何部分聚合结果**。这对某些业务场景（如"每小时的总交易额"）很重要——你不想看到窗口还在收集数据时就输出了一个不完整的数字。

---

## 13.6 ApproxPercentile——两阶段近似百分位

`approx_percentile` 的实现采用了一个独特的两阶段架构：

### 13.6.1 LocalApproxPercentileExecutor

Local 阶段（`approx_percentile/local.rs:23-29`）是一个**无状态**算子，在每个并行度上独立运行：

```rust
pub struct LocalApproxPercentileExecutor {
    input: Executor,
    base: f64,              // 对数桶的底数
    percentile_index: usize, // 百分位列的索引
    chunk_size: usize,
}
```

它的逻辑是将每个输入值映射到对数桶中：

```
输入值 value → bucket = log_base(value).ceil()

输出格式: (sign, bucket, count)
  sign = -1 (负数) / 0 (零) / 1 (正数)
  bucket = 桶编号
  count = 该桶中的行数变化
```

所有输出都是 `Insert` op，不管输入是 Insert 还是 Delete——因为 Local 只统计桶的计数变化。

### 13.6.2 GlobalApproxPercentileExecutor

Global 阶段（`approx_percentile/global.rs:18-26`）是有状态的，维护两个状态表：

- `bucket_state_table`：桶计数
- `count_state_table`：总行数

执行逻辑：

```
① 收到 Chunk → 更新桶计数和总行数
② 收到 Barrier → 计算近似百分位值 → 输出结果
```

Local + Global 的组合实现了 `approx_percentile` 的分布式计算：每个 Local 实例独立计算本地桶计数，Global 实例汇总所有桶计数后计算百分位。

---

## 13.7 MaterializeExecutor——物化视图的边界

`MaterializeExecutor`（`mview/materialize.rs:70-119`）是流计算图中最特殊的算子——它是**流和表的边界**，将上游的 changelog 物化为 Hummock 中的持久化表。

### 13.7.1 冲突检测

MaterializeExecutor 的核心复杂度在于**冲突检测**。当两行数据具有相同的 Primary Key 但不同的值时，需要决定如何处理。

`ConflictBehavior` 定义了三种策略：

| 策略 | 语义 | 实现 |
|------|------|------|
| `NoCheck` | 不检测冲突，直接写入 | 适用于 append-only 表 |
| `Overwrite` | 新值覆盖旧值 | 将 Update 改写为 Delete + Insert |
| `IgnoreConflict` | 忽略冲突，保留旧值 | 新行被丢弃 |

冲突检测通过 `MaterializeCache`（`mview/cache.rs`）实现——一个基于 LRU 的内存缓存，记录每个 PK 对应的当前行。当新行到达时：

```
① 查缓存获取该 PK 的旧行
② 比较旧行和新行
③ 根据冲突策略生成正确的输出
   - Overwrite: 输出 U-(old) + U+(new) 或 D(old) + I(new)
   - IgnoreConflict: 不输出
```

### 13.7.2 一致性级别

`get_op_consistency_level`（`materialize.rs:190-210`）根据场景选择操作一致性级别：

```rust
if cleaned_by_ttl_watermark {
    Inconsistent        // TTL 表：异步清理导致不确定 key 是否已过期
} else if !subscriber_ids.is_empty() {
    LogStoreEnabled     // 有下游订阅：需要记录完整 changelog
} else if !may_have_downstream && Overwrite {
    Inconsistent        // 无下游且 Overwrite：直接覆盖即可
} else {
    ConsistentOldValue  // 默认：需要校验旧值一致性
}
```

### 13.7.3 状态机——刷新物化视图

`MaterializeStreamState`（`materialize.rs:56-67`）定义了物化视图刷新的状态机：

```rust
pub enum MaterializeStreamState<M> {
    NormalIngestion,                              // 正常摄入
    MergingData,                                  // 合并新旧数据
    CleanUp,                                      // 清理旧数据
    CommitAndYieldBarrier { barrier, expect_next_state },  // 提交并 yield Barrier
    RefreshEnd { on_complete_epoch },              // 刷新完成
}
```

刷新物化视图（`REFRESH MATERIALIZED VIEW`）的流程：

```
NormalIngestion → 收到 RefreshStart Mutation →
  新数据同时写入主表和 staging 表（staging 表只存 PK）
  → 收到 LoadFinish Mutation →
MergingData →
  合并排序主表和 staging 表
  删除主表中 PK 不在 staging 表中的行
  → 完成 →
CleanUp → CommitAndYieldBarrier → NormalIngestion
```

`RefreshProgressTable`（`mview/refresh_progress_table.rs`）跟踪每个 VNode 的刷新进度，支持故障恢复。

### 13.7.4 Dummy Table 优化

对于 Iceberg engine 的 append-only 表，`is_dummy_table = true`（`materialize.rs:111-112`）——数据直接写入 Iceberg，Materialize 只做透传，不写入 Hummock 状态表。

---

## 13.8 TopN 算子族——流式排名

TopN 在流式系统中的挑战在于：**排名是全局性的**——插入一行可能改变所有行的排名。批处理中只需排序取前 N，流式处理中需要持续维护排名状态。

### 13.8.1 TopNCache——三段缓存

`TopNCache`（`top_n_cache.rs:51-91`）是 TopN 算子的核心数据结构，将所有行分为三段：

```
        offset              limit
├──────────────┤├────────────────────┤├──────────────────────
     low              middle                  high
  [0, offset)    [offset, offset+limit)    [offset+limit, ...)
```

```rust
pub struct TopNCache<const WITH_TIES: bool> {
    pub low: Option<Cache>,     // [0, offset)，始终与状态表同步
    pub middle: Cache,          // [offset, offset+limit)，始终与状态表同步
    pub high: Cache,            // [offset+limit, ...) 的开头部分，LRU 缓存
    pub offset: usize,
    pub limit: usize,
    pub high_cache_capacity: usize,
}
```

- **low**：排名在 offset 之前的行。只在 `offset > 0` 时存在
- **middle**：排名在 `[offset, offset+limit)` 之间的行。这是**输出窗口**
- **high**：排名在 `offset+limit` 之后的行的缓存。只需要缓存开头部分即可

**插入一行时的逻辑**：

```
新行排名 < offset → 插入 low，如果 low 溢出则 low 的最后一行进入 middle
新行排名在 [offset, offset+limit) → 插入 middle，middle 最后一行进入 high
新行排名 >= offset+limit → 插入 high（如果缓存有空间）
```

**删除一行时的逻辑**：

```
删除行在 low → 从 low 删除，如果 middle 不空则 middle 第一行补充到 low
删除行在 middle → 从 middle 删除，如果 high 不空则 high 第一行补充到 middle
删除行在 high → 从 high 删除（如果缓存中有）
```

只有 middle 的变化才会产生下游输出。

### 13.8.2 WITH_TIES 语义

`TopNCache<const WITH_TIES: bool>` 的 const generic 参数控制是否支持 `FETCH FIRST n ROWS WITH TIES` 语义。当 `WITH_TIES = true` 时，middle 缓存可能超过 limit——因为所有与第 N 名并列的行都必须包含在结果中。

### 13.8.3 ManagedTopNState——持久化状态

`ManagedTopNState`（`top_n_state.rs:35-41`）封装了 Hummock State Table，提供 insert/delete/scan 操作：

```rust
pub struct ManagedTopNState<S: StateStore> {
    state_table: StateTable<S>,
    cache_key_serde: CacheKeySerde,
}
```

存储键格式：`[order_by 列 + PK 剩余列]`。对于 Group TopN，前面还有 group key。

### 13.8.4 TopNExecutor——通用版本

`TopNExecutor<S, const WITH_TIES: bool>`（`top_n_plain.rs:28-29`）处理 retractable 流（有 Insert/Delete/Update）：

```rust
pub type TopNExecutor<S, const WITH_TIES: bool> =
    TopNExecutorWrapper<InnerTopNExecutor<S, WITH_TIES>>;
```

执行逻辑（`top_n_plain.rs:133-177`）：

```
① apply_chunk: 逐行处理
   Insert → 写入状态表 + 插入 TopNCache
   Delete → 从状态表删除 + 从 TopNCache 删除（可能需要从状态表补充 high 缓存）

② flush_data: 提交状态表

③ init: 初始化 epoch + 从状态表恢复 TopNCache
```

### 13.8.5 GroupTopNExecutor——分组 TopN

`GroupTopNExecutor`（`top_n/group_top_n.rs`）在 TopN 基础上增加分组维度，每个分组独立维护一个 `TopNCache`：

```
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC) AS rn
  FROM orders
) WHERE rn <= 10
```

分组 TopN 的状态表键为 `[group_key | order_by | remaining_pk]`，每个 group key 有独立的 TopNCache 实例。这些缓存通过 `ManagedLruCache` 管理，避免分组数过多时 OOM。

### 13.8.6 AppendOnlyTopNExecutor——追加优化

`AppendOnlyTopNExecutor`（`top_n/top_n_appendonly.rs`）专门针对 append-only 流优化。因为流只包含 Insert 操作，可以省略很多逻辑：

- 不需要维护 low 缓存（offset 之前的行永远不会被删除）
- 删除操作不需要从状态表补充缓存
- 状态更简单，性能更高

### 13.8.7 GroupTopNAppendOnlyExecutor

`GroupTopNAppendOnlyExecutor`（`top_n/group_top_n_appendonly.rs`）是 Group TopN 的 append-only 优化版本。

---

## 13.9 OverWindowExecutor——窗口函数

`OverWindowExecutor`（`over_window/general.rs:46-49`）实现流式窗口函数（`OVER (PARTITION BY ... ORDER BY ...)`），如 `ROW_NUMBER`、`RANK`、`DENSE_RANK`、`LEAD`、`LAG`、聚合窗口函数等。

```rust
pub struct OverWindowExecutor<S: StateStore> {
    input: Executor,
    inner: ExecutorInner<S>,
}
```

### 13.9.1 状态表设计

OverWindow 的状态表 schema = 输出 schema，状态表 PK = `partition_key | order_key | input_pk`。这意味着状态表中存储了每个分区内所有行的完整数据及其窗口函数结果。

### 13.9.2 PartitionCache 与 DeltaBTreeMap

`OverWindowExecutor` 使用 `PartitionCache`（`over_window/range_cache.rs`）缓存每个分区的数据，内部使用 `DeltaBTreeMap`——一个支持增量的 BTreeMap。

当新 Chunk 到达时（`apply_chunk`，`general.rs:284-`）：

```
① merge_changes_in_chunk: 合并同一 PK 的多次变更
② 按 partition key 分组
③ 对每个分区:
   - 构建分区 delta（PartitionDelta = BTreeMap<CacheKey, Change<OwnedRow>>）
   - 检测 order key 变化的行（需要先删后插）
④ 写入状态表
⑤ 计算受影响的范围（AffectedRange）
⑥ 重新计算窗口函数状态
⑦ 生成输出
```

### 13.9.3 Frame 计算

`frame_finder.rs`（1583 行）是窗口帧范围计算的核心，支持三种帧类型：

- **ROWS 帧**：基于行数的物理偏移（`ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING`）
- **RANGE 帧**：基于排序键值的逻辑偏移（`RANGE BETWEEN INTERVAL '1' HOUR PRECEDING AND CURRENT ROW`）
- **GROUPS 帧**：基于分组逻辑的偏移

`merge_rows_frames` 函数合并多个窗口函数调用的 ROWS 帧范围，取并集——确保一次扫描就能满足所有窗口函数的计算需求。

### 13.9.4 缓存策略

`CachePolicy`（`general.rs:218-224`）决定了分区缓存的行为：

```
有界帧 → 使用配置的缓存策略（Recent / Full / Auto）
无界帧 → 强制 Full 策略（因为最终需要分区内的所有行）
```

- **Full**：缓存分区内所有数据
- **Recent**：只缓存最近访问的范围
- **Auto**：根据数据特征自动选择

### 13.9.5 编号函数优化

`Calls` 结构体（`general.rs:142-158`）维护了窗口函数调用的元信息，其中有两个优化标志：

```rust
numbering_only: bool,   // 所有调用都是 row_number/rank/dense_rank
has_rank: bool,         // 包含 rank 或 dense_rank
```

当 `numbering_only = true` 时，窗口函数的计算不需要访问帧内数据——只需要知道行号和排名，计算量大大减少。

---

## 13.10 EowcOverWindowExecutor——窗口关闭时输出

`EowcOverWindowExecutor`（`over_window/eowc.rs`）是 OverWindow 的 EOWC 变体，类似于 HashAgg 的 EOWC 模式：只在 Watermark 推进过排序键时才输出窗口函数结果。

它使用 `SortBuffer` 缓冲排序键对应的行，当 Watermark 到达时，排序键小于 Watermark 的所有行被取出并计算窗口函数。

EOWC OverWindow 的语义保证：**只在排序键之前的数据完整时才输出窗口函数结果**。这对于基于时间排序的窗口函数至关重要——你不想在窗口还在收集数据时就输出不完整的 `ROW_NUMBER` 或 `RANK`。

---

## 13.11 GapFillExecutor——时间序列空洞补齐

`GapFillExecutor`（`gap_fill.rs`）解决时间序列数据中的"空洞"问题：当数据在某个时间点缺失时，自动插入填充行。

### 13.11.1 填充策略

`FillStrategy` 定义了每列的填充方式：

| 策略 | 行为 |
|------|------|
| `Null` | 填充 NULL |
| `Prev` | 使用前一个非 NULL 值（LOCF） |
| `Next` | 使用后一个非 NULL 值 |
| `Linear` | 线性插值 |
| `Value` | 使用固定值 |

### 13.11.2 执行逻辑

```
① 收到 Chunk 中的新行 (time=T1, value=V1)
② 检查前一行的时间 T0
③ 如果 T1 - T0 > gap_interval:
   - 在 T0 和 T1 之间按 gap_interval 生成填充时间点
   - 对每个填充点，根据 FillStrategy 计算填充值
   - 输出填充行（标记为 Filled）
④ 输出原始行（标记为 Original）
```

### 13.11.3 状态管理

`ManagedGapFillState`（`gap_fill.rs:63-68`）管理持久化状态：

```rust
pub struct ManagedGapFillState<S: StateStore> {
    state_table: StateTable<S>,
    time_key_serde: OrderedRowSerde,
    time_column_index: usize,
    filled_column_index: usize,
}
```

状态表中每行额外存储 `is_filled` 标志（`RowType::Original` vs `RowType::Filled`）。当原始数据到达导致填充行需要被替换时，GapFillExecutor 通过 `scan_filled_rows_between` 找出需要删除的填充行。

---

## 13.12 有状态算子的共同模式

回顾 HashAgg、TopN、OverWindow、GapFill 这些有状态算子，它们共享一个核心模式：

### 13.12.1 Cache + StateTable 双层架构

```
              ┌─────────────────────────────────┐
              │       In-Memory Cache            │
              │  (LRU / BTreeMap / TopNCache)    │
              │  - 近期热数据                     │
              │  - dirty 标识                     │
              └────────────┬────────────────────┘
                           │ Barrier 时 flush
              ┌────────────▼────────────────────┐
              │     Hummock State Table          │
              │  - 持久化全量状态                 │
              │  - 支持 epoch 读取               │
              │  - 故障恢复的数据源               │
              └─────────────────────────────────┘
```

这个双层架构在所有有状态算子中反复出现：
- HashAgg: `AggGroupCache` + `intermediate_state_table`
- TopN: `TopNCache` (low/middle/high) + `ManagedTopNState`
- OverWindow: `PartitionCache` + `state_table`
- GapFill: `GapFillCache` + `ManagedGapFillState`
- Materialize: `MaterializeCache` + `state_table`

### 13.12.2 Barrier 驱动的生命周期

```
① init: 从 StateTable 恢复缓存
② apply_chunk: 更新缓存 + 写入 StateTable
③ flush_data: 计算变更 + 输出 StreamChunk
④ commit: 提交 StateTable 到 Hummock
⑤ yield Barrier
```

### 13.12.3 变更追踪

有状态算子都需要追踪"从上一个 Barrier 以来的变化"，但方式各异：
- HashAgg: `dirty_groups` map
- TopN: `TopNStaging`（middle 区域的变更记录）
- OverWindow: `PartitionDelta`（BTreeMap<CacheKey, Change>）
- Materialize: `ChangeBuffer`（基于 PK 的变更合并）

---

## 13.13 小结

本章深入了 RisingWave 中聚合、TopN、窗口函数和填充算子的实现原理：

- **SimpleAggExecutor / HashAggExecutor**：两种聚合模式共享 `AggGroup` 抽象，通过 `Strategy` trait 区分输出策略，HashAgg 的 LRU 缓存 + dirty groups 机制支持大规模分组
- **ApproxPercentile**：两阶段架构（Local 桶计数 + Global 汇总计算），用 `must_output_per_barrier` 保证 RowMerge 的正确性
- **MaterializeExecutor**：流与表的边界，冲突检测、一致性级别选择、刷新状态机、Dummy Table 优化
- **TopNExecutor 族**：三段缓存（low/middle/high）、WITH_TIES 语义、Group TopN 的 LRU 缓存、AppendOnly 优化
- **OverWindowExecutor / EowcOverWindowExecutor**：PartitionCache + DeltaBTreeMap、Frame 计算、编号函数优化、EOWC 的 SortBuffer
- **GapFillExecutor**：时间序列填充、五种填充策略、Filled 行的状态管理

有状态算子的核心复杂度来自 **Cache + StateTable 双层架构** + **Barrier 驱动的增量变更追踪** + **分组/排名/窗口等语义的正确性保证**。理解这个模式，就掌握了流计算引擎中所有有状态算子的设计范式。

下一章将进入 Backfill 机制——看 RisingWave 如何在创建物化视图时高效地将历史数据与增量流合流。

---

*本章完成。下一章：[第 14 章 · Backfill——历史数据与增量流的合流](../chapters/14-Backfill-历史数据与增量流的合流.md)*