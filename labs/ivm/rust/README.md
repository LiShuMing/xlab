# Rust ZSet 与时间序列 radix tree 实验

前置条件：Rust/Cargo（清单声明最低 1.75），标准库，无第三方 crate、数据库或网络服务。
独立 Cargo workspace，不需要构建仓库里的其他 Rust 项目。当前验证环境见文末。

这是对照 Feldera 开源源码独立编写的教学实现，不是 Feldera 的移植或完整 DBSP 引擎。
保留同主题 Python 原型，不修改它们的行为。

## 运行

在本目录执行：

```sh
cargo test --offline --locked
cargo test --offline --locked --release
cargo run --offline --locked --example time_series
cargo fmt -- --check
cargo clippy --offline --locked --all-targets -- -D warnings
```

也可从仓库根目录传入 `--manifest-path labs/ivm/rust/Cargo.toml`。
编译结果进入已忽略的 `target/`，不提交二进制或运行缓存。

## 学习顺序

1. [TUTORIAL.md](TUTORIAL.md)：完整设计、源码对应和逐步实验。
2. [zset.rs](src/zset.rs)：记录到整数权重的映射、加法、投影、连接。
3. [batch.rs](src/batch.rs)、[indexed_batch.rs](src/indexed_batch.rs)：排序归并与分组游标。
4. [radix_tree.rs](src/radix_tree.rs)：前缀、压缩路径、子树缓存、原子节点更新。
5. [time_series.rs](src/time_series.rs)：累计事件状态、受影响时间点重算、SUM/COUNT 与 MIN。
6. [time_series 示例](examples/time_series.rs) 和 [测试](tests/)：插入、撤回、迟到修正和全量对照。

## 数据流与约定

```text
事件差分 ((timestamp, value), weight)
    → Batch 排序、合并重复项、去零
    → 累计 ZSet（时间序列拒绝负重数）
    → 从更新后的累计状态重算受影响 timestamp 的聚合
    → 原子更新压缩 radix tree
    → 节点差分 ((prefix, node), ±1) + 闭区间聚合查询
```

- 基础 ZSet 允许负权重，规范化后没有零权重项；不是 Redis Sorted Set。
- IndexedBatch 中 `(K,V)` 唯一，同一个 K 可以对应多个 V；cursor 只前进，回查要 `rewind`。
- 时间戳是 `u64`，查询为 `[from, to]`；支持 `0`、`u64::MAX`，反向区间返回错误。
- `/0` 前缀覆盖全域，`/64` 表示单个时间点。树为二叉，不是字符串 trie。
- 空聚合用 `None`；`Some(SumCount { sum: 0, count: 2 })` 仍然有数据。
- 节点差分是结构替换，不是对 SUM/MIN 做 ±1；重放后每个存活前缀恰好一个节点、权重 1。
- `Result::Err` 不改变可变集合状态；不承诺内存耗尽或用户实现 panic 的事务恢复。

## 验证范围与边界

测试包含：规范化与有界群律、连接权重相乘、投影抵消、游标边界、前缀边界、
删除后压缩、节点差分重放、180 轮小域树更新后的全部闭区间对照、120 轮全宽时间戳
更新与删除，以及 240 轮时间序列更新后 SUM/COUNT 和 MIN 的全量重算对照。
另验证非交换聚合的时间顺序、非法撤回及权重/聚合溢出的原子性。
这些是本地正确性实验，不是性能收益或生产兼容性证明。

刻意未实现：完整 Trace（追加批次与后台归并）、逻辑时间、并行调度、持久化、
watermark（判断旧事件何时不再到来的进度标记）、过期回收、SQL NULL/类型语义。

- `TimeSeries` 每批克隆累计输入，成本 O(N)；树使用临时覆盖表，只修改受影响路径。
- 一条树路径最多检查 64 个时间戳位，但节点放在 BTreeMap 中，不能据此宣称总更新 O(64)。
  连续区间可复用完整子树；返回大量叶子的接口未提供。
- 时间点桶内重算与桶中不同 value 的数量相关。MIN 删除不能简单把 delta 的最小值加回去。
- 教学 join 为嵌套循环，成本 O(|L|×|R|)，不是生产索引 join。
- 权重 `i64`，重复项求和和 SUM/COUNT 使用 `i128`，检查中间运算溢出；
  这是有界机器算术，不是任意精度整数群。结果可表示也不保证每种中间归并顺序都可表示。
- `QueryStats` 统计读取节点数与复用缓存子树数，不是耗时、缓存命中率或性能 benchmark。

## 本轮验证记录

2026-11-08，Linux，rustc/cargo 1.94.0，实际执行结果：

| 检查 | 结果 |
| --- | --- |
| `cargo check --offline --locked` | 通过 |
| debug / release `cargo test --offline --locked` | 各 19 个集成测试 + 1 个文档示例通过 |
| debug / release `cargo run --offline --locked --example time_series` | 断言通过；最终 [10,20] 的 sum=16、count=2、min=7 |
| `cargo fmt -- --check` | 通过 |
| `cargo clippy --offline --locked --all-targets -- -D warnings` | 通过 |
| 仓库 `tools.test_navigation` + `tools.test_entrypoints` | 8 项通过（含本实验文档链接） |
| 原有 Python IVM `unittest` | 23 项通过；未修改 Python 原型 |
| 原有 `dbsp/` pytest 用例 | 未运行，当前 Python 环境没有 pytest |

最低 1.75 工具链未在当前机器执行；CI 配置另安排兼容性检查，远端结果须单独查看。

示例中三轮全域 sum/count 分别为 `16/5 → 10/3 → 21/3`，树均有 3 个内部节点，
节点差分记录数分别为 `3 → 4 → 6`；全域查询均读取 1 个节点、复用 1 份 child 缓存。
最后 [10,20] 查询排除 t=30，所以 sum 为 16 而不是全域的 21。
记录数是结构差分中规范化 `(prefix,node)` 项的数量，不是“改变了几个前缀”。

源码引用固定于公开 Feldera 提交
[`d1dfb6447a30f194c2b59d3c66c3708dda6e5699`](https://github.com/feldera/feldera/tree/d1dfb6447a30f194c2b59d3c66c3708dda6e5699)。
公开版许可及本实验差异见 [教程](TUTORIAL.md#源码对应与差异)。
