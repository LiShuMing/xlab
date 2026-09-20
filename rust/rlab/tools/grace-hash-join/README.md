# Hybrid Grace Hash Join 学习实验

这是文章《深入 Hash Join：从内存哈希表到分区 Spill》的配套 Rust 小实验。它不是一个生产级执行器，目标是让 Grace/Hybrid Hash Join 的状态转换可以运行、观察和修改。

Spill 的物理 I/O 已抽到 workspace library `lib/spill-io`。本 crate 只负责 Join 的分区状态机和 `RowCodec`；后续 Hash Aggregate 可以复用分区文件，External Sort 可以复用 run 文件。

## 先建立整体模型

普通 Hash Join 假设 Build 侧能够整体放入内存：

```text
build rows -> HashMap<key, Vec<build row>> -> probe rows -> joined rows
```

Grace Hash Join 把一张不可控的大表变成多张有内存上界的小表：

```text
                    same stable hash + same partition bits
build rows -------------------------------------------------- probe rows
    |                                                            |
    +-> bucket 0 (memory if it fits) <---- probe immediately -----+
    +-> bucket 1 build.bin          <---- probe.bin bucket 1 -----+
    +-> bucket N build.bin          <---- probe.bin bucket N -----+
                   |
                   +-> restore one build bucket
                   +-> rebuild a local HashMap
                   +-> read the matching probe bucket
                   +-> join and release local state
```

如果恢复的 Build bucket 仍超预算，就从同一个 64-bit hash 中取后续位，对 Build 和 Probe 两侧同步递归分区。相同 key 在两侧使用完全相同的规则，这是正确性的核心不变量。

Hybrid 的含义是：bucket 0 能装下时保留在内存，Probe 到来后直接匹配；只有其他 bucket 才发生写盘和恢复。

## 运行

在 `rust/rlab` 下执行：

```bash
cargo run -p grace-hash-join
```

默认只有 4 行 Build 内存预算，因此 demo 会进入外存路径并打印状态轨迹。可以对照两个极端：

```bash
# 全内存 Hash Join
cargo run -p grace-hash-join -- --memory-rows 100

# 更频繁地递归分区
cargo run -p grace-hash-join -- --memory-rows 2 --partitions 2 --max-depth 6
```

验证代码：

```bash
cargo test -p grace-hash-join
cargo clippy -p grace-hash-join --all-targets -- -D warnings
```

## 阅读顺序

建议按这个顺序阅读 `src/lib.rs`：

1. `hybrid_grace_hash_join()`：决定全内存还是 external 路径；
2. `partition_initial()`：保留 bucket 0，其他逻辑行写临时文件；
3. `partition_for()`：Build/Probe 共享的分区契约；
4. `process_partition()`：恢复局部 HashMap，或者对两侧递归重分区；
5. `build_hash_table()` / `probe_one()`：被外存层复用的普通 Hash Join 内核；
6. `RowCodec`：定义 Join 逻辑行格式，而不是序列化包含地址的 HashMap；
7. 单元测试：重复 key、NULL、external/内存结果等价，以及热点 key 无法继续拆分。

公共 I/O 层建议按以下顺序阅读：

1. `spill_io::SpillCodec<T>`：算子提供逻辑记录格式；
2. `spill_io::SpillWriter` / `SpillReader`：缓冲顺序 I/O 和记录/字节统计；
3. `spill_io::SpillDirectory`：临时文件所有权与失败/取消后的自动清理。

## 代码与文章概念的对应关系

| 文章中的概念 | 实验中的位置 |
| --- | --- |
| Build/Probe 状态契约 | `stable_hash()` + `partition_for()` |
| 重复 key | `HashMap<u64, Vec<Row>>`，输出笛卡尔乘积 |
| SQL NULL 语义 | Inner Join 跳过 `key == None` 的行 |
| Spill 逻辑数据 | Join 的 `RowCodec` 定义 `[key][payload length][payload]` |
| Spill 物理 I/O | 公共 `spill-io` crate |
| Hybrid 当前分区 | 初始 bucket 0 在预算内就驻留内存 |
| Restore + rebuild | `process_partition()` 中重新构造局部 HashMap |
| Recursive Grace | 超预算时用下一组 hash bits 同步重分区 |
| 数据倾斜边界 | 到达 `max_repartition_depth` 后返回明确错误 |
| 可观测性 | `JoinEvent` 和 `JoinStats` |

## 有意简化的部分

- 只实现 Inner Join；Outer/Semi/Anti 需要额外的逐行匹配状态。
- Key 固定为 nullable `u64`，没有组合键编码和字符串 Arena。
- 内存预算按 Build 行数计算；真实引擎要计算 payload、bucket、装载因子、分配碎片和 Probe buffer 的字节数。
- I/O 是同步逐行流式读取；生产实现通常按 block/chunk 处理，并增加压缩、异步预取和 backpressure。
- 单线程执行，没有 pipeline barrier、并行 build 或输出 continuation。

## 推荐练习

1. 把 `memory_budget_rows` 改为字节预算，并估算 `HashMap` bucket 开销。
2. 增加 Left Outer Join，为每个 Probe 未匹配行补 NULL Build payload。
3. 增加 Full Outer Join，为 Build row 保存 `matched` 标记，并在每轮结束扫描未匹配行。
4. 把逐行 `RowReader` 改为批量 chunk reader，比较 syscall、内存峰值和吞吐变化。
5. 基于已有 spill bytes，继续记录 restore bytes、每层 bucket 分布和最大倾斜比例。
6. 构造 60% 相同热点 key，观察为什么增加 hash bits 仍无法拆开它。
