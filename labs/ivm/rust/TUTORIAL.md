# 从 ZSet 到增量时间区间聚合

## 目标与分层设计

要解决的问题：持续接收带事件时间的插入和撤回，在任意闭区间查询 SUM/COUNT 或 MIN，
不在每次查询时扫描所有事件。同时让树本身也能表示成可重放的差分集合。

本实验从下往上分为四层：

| 层 | 状态或接口 | 负责什么 |
| --- | --- | --- |
| 关系代数 | `ZSet<T>` | 记录 → 整数权重；作为语义清晰的参考容器 |
| 批存储 | `Batch<T>`、`IndexedBatch<K,V>` | 规范化、线性归并、键值分组、只前进游标 |
| 区间索引 | `RadixTree<A>` | 时间戳前缀寻址、压缩路径、缓存子树聚合 |
| 增量应用 | `TimeSeries<G>` | 累计输入、受影响时间点重算、原子更新与结构差分 |

实现只用 Rust 标准库，类型定义和错误见 [lib.rs](src/lib.rs)。
`Aggregate` 有 SUM/COUNT 与 MIN 两个实际实现，不为未实现的运行时引入框架。

## 1. ZSet：带符号的重数，不是按分数排序

数学上，一个有限 ZSet 是函数 `record → integer`，未出现的记录权重为 0。
权重表示重数（multiplicity）：`+2` 是两份，`-1` 是撤回一份。负权重在基础代数层合法。

```text
输入：("a", +2), ("b", +1), ("a", -1), ("b", -1)
规范化：("a", +1)
```

规范化做三件事：同记录归并、权重相加、删除零权重项。这里用 `BTreeMap` 保存当前状态，
有序 `Vec` 保存不可变批次；它们是两种独立的归并实现，测试互相对照。
`from_updates` 先以 `i128` 汇总再转换为 `i64`，避免 `MAX + 1 - 1` 因逐项窄化错误失败。

加法逐记录相加；取逆把所有权重变号；投影可能把不同记录映射到同一个输出，必须再次归并。
连接的每一对匹配记录生成 `left_weight × right_weight`，投影后的碰撞也必须合并。

在本目录创建 Rust 用例时，可直接用以下接口（已有对应自动测试）：

```rust
use ivm_radix_lab::ZSet;

let a = ZSet::from_updates([(1, 3), (2, -3)]).unwrap();
let b = ZSet::from_updates([(7, 2)]).unwrap();
let joined = a.join(&b, |left, right| Some(left + right)).unwrap();
assert_eq!(joined.weight(&8), 6);
assert_eq!(joined.weight(&9), -6);
assert!(joined.map(|_| 0).unwrap().is_empty());
```

执行 `cargo test --offline --test collections`。关注 [collections.rs](tests/collections.rs)
中的群律、溢出和抵消测试。有界整数上的群律只在涉及的运算都可表示时成立。

## 2. Batch、IndexedBatch 与 cursor

`Batch<T>` 是按 T 排序、T 唯一且没有零权重的 `(T,i64)` 数组。
两份已排序批次可以用双指针线性归并；普通 ZSet 与 Batch 不代表追加历史的 Trace。

`IndexedBatch<K,V>` 把规范化 `(K,V)` 对分成四个数组：

```text
记录：((1,2),-1), ((1,4),+1), ((3,7),+1)
keys    = [1, 3]
offsets = [0, 2, 3]
values  = [2, 4, 7]
weights = [-1, 1, 1]
```

第 i 个键的值位于 `offsets[i]..offsets[i+1]`。同一个键能有多个不同值；
对 `(prefix,node)` 来说，结构差分可能同时包含一个旧 node 的 -1 和一个新 node 的 +1。

cursor 使用 `key/value/weight` 读取当前位置，`step_value` 遍历组内值，`step_key`
进入下一组。`seek_key/seek_value` 只在当前位置以后的有序区间做 lower bound，
不会倒退，也不会把当前键已经耗尽的值重新展开。要回查旧键，先 `rewind()`。
空批次、组尾、全局耗尽都返回 `None`；测试验证耗尽后继续 seek/step 不越界。

## 3. 二进制前缀与压缩 radix tree

时间戳按高位到低位划分。`Prefix { key, len }` 中 key 的后缀必须归零：
`/0` 覆盖整个 `u64` 域，`/64` 是单点，普通前缀代表连续时间区间。
构造函数自动归零后缀，拒绝长度超过 64，并单独处理 0/64，避免移位 64 位。

分叉位置由 `(old_key ^ new_key).leading_zeros()` 找到最长公共高位前缀。
每个内部节点只有两个 child slot；child 包含子树前缀和缓存聚合。
叶子（某 timestamp 的聚合）直接嵌入父节点的 child，不单独放入节点表。

以只看最后三位的 0、1、2 为例（共同的前 61 个零位被压缩）：

```text
root /0
  └─ prefix 0 /62：覆盖 [0,3]
       ├─ prefix 0 /63：覆盖 [0,1]
       │    ├─ leaf 0 /64
       │    └─ leaf 1 /64
       └─ leaf 2 /64
```

节点记录在 `BTreeMap<Prefix,TreeNode<A>>` 中。根节点覆盖全域；非根内部节点
恰好两个孩子，遇到只有一个孩子时向上压缩。整棵树为空时不保留根节点。

例如删除时间点 1，`0/63` 只剩 leaf 0，便删除该中间节点，让 `0/62` 直接指向 leaf 0。
删除所有时间点后节点表也为空。`validate()` 递归检查可达性、前缀严格增长、
分叉槽位、非根双孩子以及缓存聚合值；它是昂贵的诊断接口，不在正常更新中自动执行。

## 4. 区间查询为什么能跳过整段数据

对每个 child 的前缀区间：不相交就跳过；完全被查询区间包含就直接取缓存；
部分相交才向下查。`Aggregate::combine` 按左子树、右子树顺序合并，要求结合律，
不强制交换律，也不要求“空值”的数值单位元。

`None` 是没有数据，不是聚合结果为 0。`Some(SumCount {sum:0,count:2})` 表示
两份值恰好抵消，不能删除该叶子。MIN 为 0 也不能当空节点。

`query_with_stats` 返回 `node_visits`（查阅的内部节点数）与 `cached_subtrees`
（直接消费的 child 缓存数）。全域查询只读取根节点，复用其非空孩子的缓存；
这说明计算路径，不证明墙钟时间更快。BTreeMap 查找、聚合对象克隆等仍有成本。

## 5. 从事件撤回到树节点差分

累计输入是 `ZSet<(u64,i64)>`，权重是每个 `(timestamp,value)` 的份数。
基础 ZSet 允许负权重，但这里代表实际事件袋，提交后的每个重数必须为正。
同批插入与撤回先抵消，再检查最终状态；不存在的事件不能被额外撤回。

一次批更新的事务顺序：

1. 克隆累计输入，在副本上应用整个规范化批次，预检查权重溢出。
2. 收集有变化的 timestamp，从**更新后的累计状态**读取该时间点全部 value/weight。
3. 校验最终重数，重算每个时间点的 `Option<Acc>`。没有值就删除该时间点。
4. 树在临时覆盖表中更新受影响路径，检查聚合溢出并生成完整结构差分。
5. 全部成功后应用树覆盖表，再替换累计输入；提交阶段没有可返回的算术错误。

输入副本让错误原子性容易理解，但每批有 O(N) 克隆开销。这一版不是生产增量存储性能模型。
树的覆盖表避免每批重建整树；单次逻辑路径深度最多 64 位，节点表查找仍有额外成本。

### 为什么 MIN 不能直接对差分取最小值

原状态：同一时间点 `{3×2, 7×1}`，MIN=3。撤回 `3×2` 后，剩余 MIN 应为 7。
如果只看差分 `{3×-2}`，无法得到 7。因此从累计状态重算受影响时间点，
再向树传 `Some(MinValue(7))`，而不是把 MIN 当作可减的 SUM。

### 节点差分的 ±1 是什么

假设某前缀的缓存由 sum=6 变成 sum=9，输出的是：

```text
((prefix, old_entire_node), -1)
((prefix, new_entire_node), +1)
```

这是删除旧结构、加入新结构，不是对聚合数值加减 1。
把每轮差分应用到单独 ZSet 后，必须与 `tree.snapshot()` 一致；
每个存活前缀恰有一个 node，权重 1。相同节点不重复输出，临时变化最后抵消也不输出。

## 6. 运行完整实验

```sh
cargo run --offline --locked --example time_series
cargo test --offline --locked --test radix
cargo test --offline --locked --test time_series
```

示例依次插入 `t=10:{3×2,7×1}, t=20:{-2×1}, t=30:{5×1}`，
撤回 `t=10` 的两份 3，再迟到修正 `t=20` 的 -2 为 9。
每轮打印全域 sum/count、min、节点数、结构差分记录数、child 缓存和查询计数。
差分按 `(prefix,node)` 排序，不保证输出中 -1 先于 +1；同批应用后才是新状态。
示例末尾断言：

```text
[10,20]: sum=16, count=2, min=7
[21,29]: empty
```

自动对照不依赖相同树算法：测试维护独立 BTreeMap，直接扫描区间得到期望值。
树测试在 180 轮确定性更新后穷举小域全部闭区间，另做 120 轮全宽时间戳更新/删除；
时间序列在 240 轮更新后
分别比较 SUM/COUNT、MIN、累计输入和重放后的节点结构。另有 `0/MAX`、空状态、
重复 timestamp、替换、删除、非法撤回、`i64` 权重与 `i128` 聚合溢出的测试。

这些是本地教学正确性证据，不是 Feldera 集成测试、完整形式化证明或性能 benchmark。
当前环境与实际执行状态记录在 [README](README.md#本轮验证记录)。

## 源码对应与差异

参考的是本机开源 checkout 的固定提交
`d1dfb6447a30f194c2b59d3c66c3708dda6e5699`，不是会漂移的 `main`：

| 公开 Feldera 源码 | 对照点 | 本实验 |
| --- | --- | --- |
| [algebra/zset.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/algebra/zset.rs) | ZWeight=i64、普通和 indexed ZSet 别名 | `ZSet<T>`、`IndexedBatch<K,V>`；不是生产 OrdZSet 存储的复刻 |
| [utils/consolidation.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/utils/consolidation.rs) | 排序、同项合并、去零 | `Batch::from_updates`，中间汇总显式检查溢出 |
| [indexed_wset_batch.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/trace/ord/vec/indexed_wset_batch.rs) | 两层有序存储 | 四数组分组批次；没有文件层与动态类型工厂 |
| [trace/cursor.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/trace/cursor.rs) | seek 只前进 | `Cursor` 显式 rewind，没有时间维游标 |
| [radix_tree.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/operator/dynamic/time_series/radix_tree.rs) | `RADIX=2`；完整子树直接取聚合 | 固定 u64 二叉树；不是插图暗示的四叉实现 |
| [prefix.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/operator/dynamic/time_series/radix_tree/prefix.rs) | 规范化高位前缀、最长公共前缀 | 安全处理 /0 和 /64 |
| [treenode.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/operator/dynamic/time_series/radix_tree/treenode.rs) | ChildPtr、二分支、old/new 节点更新 | 叶子嵌入 child、BTreeMap 前缀寻址 |
| [updater.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/operator/dynamic/time_series/radix_tree/updater.rs) | 删除压缩；从更新后累计输入读取受影响时间点 | 递归路径更新与临时覆盖表，不复刻 DBSP 批游标栈 |
| [tree_aggregate.rs](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/crates/dbsp/src/operator/dynamic/time_series/radix_tree/tree_aggregate.rs) | 旧节点 -1、新节点 +1 | `NodeDelta<A>` 可重放为 canonical ZSet |

Feldera 的 OrdZSet 不是简单 BTreeMap：它有内存/文件批次、Trace 和后台归并；
通用 trace cursor 也不等于“每次读取都没有零累计权重”。这里规范化、去零是本实验
**已物化容器**的约定，不把这个保证外推到其所有运行时游标。

本实验独立实现上述公开算法与数据模型，没有复制企业功能代码或引入 Feldera 依赖。
Feldera [根 LICENSE](https://github.com/feldera/feldera/blob/d1dfb6447a30f194c2b59d3c66c3708dda6e5699/LICENSE)
说明公开版 MIT、企业功能另有许可；引用不意味着所有子目录都同一许可。
本实验的代码许可声明见 [Cargo.toml](Cargo.toml)，不代表重新许可上游代码。

## 后续实验方向（未实现）

可在保持全量对照的前提下增加多批 Trace 与分层归并、按分区维护独立树、
window/watermark 淘汰及相同输入上的扫描/树查询 benchmark。先分开测量输入克隆、
桶内重算、树维护和查询，不能把教学容器的开销误当成 radix tree 算法本身的开销。
