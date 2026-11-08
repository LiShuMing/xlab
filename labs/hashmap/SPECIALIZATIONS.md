# 面向 Hash Aggregate / Hash Join 的专用结构

参考 StarRocks 本地 checkout 的机制，独立编写教学实现。实验不包含 StarRocks 源码，
不链接其依赖，也不构建或运行 StarRocks；成绩不能归为 StarRocks 算子性能。
参考文件与本地 revision、文件摘要见 [source-reference.json](source-reference.json)。

## 源码观察与实验映射

| StarRocks 入口 | 源码中的机制 | 实验实现 |
| --- | --- | --- |
| `be/src/exec/aggregate/agg_hash_map.h:61` | Int8/Int16 使用 `SmallFixedSizeHashMap`，其它数字键等使用 flat hash map | `direct` 对照 `flat-u64`、`std` |
| `be/src/base/container/fixed_hash_map.h:34` | 用整数的无符号表示作为直接数组索引，聚合状态指针为空表示未出现 | 实验用运行期范围减最小值寻址；COUNT/SUM 状态内联，count==0 表示未出现 |
| `be/src/exec/aggregate/agg_hash_map.h:82` | 4/8/16 字节定长复合键；另外有压缩序列化分支 | 2×32 位字段打包到 uint64，对照等价的 8 字节二进制键 |
| `be/src/exec/aggregate/agg_hash_map.h:243` | 可空单键的 NULL 状态单独存储 | 聚合 NULL 为一个单独分组；普通键 0 保持独立 |
| `be/src/exec/join/join_hash_map_method.h:71` | distinct key 线性探测，相同键的构建行通过 next 链组织；有指纹过滤 | `chain` / `chain-fp`，8 位指纹 + 24 位行号；指纹相等后仍检查完整键 |
| `be/src/exec/join/join_hash_table.cpp:264` | 根据整数范围、内存/缓存预算、Join 语义选择 range direct / dense mapping | `direct` 行号链：展示有限值域的收益及浪费，没有复制 StarRocks 的启发式阈值 |
| `be/src/exec/join/join_hash_map_method.h:318` | 没有额外谓词的 Semi/Anti 只需位图表示存在性 | `bitmap` 对照 std set；仅测试普通等值 Semi 的存在性 |

StarRocks 还包含 two-level 表、批量预计算哈希与预取、压缩复合键、ASOF Join 的专门结构。
这些方向暂未实现。实验中的标量 8 位指纹也不是完整的 phmap/Swiss SIMD 分组实现。

## 运行与负载

```sh
CXX=clang++ python3 tools/run.py --suite operators --build-dir .local/operators-build
```

特殊工具链依然用 `--compiler`、`--cxx-flags`、`--linker-flags` 显式传入。
所有 case 只需要编译器、CMake 和 Python 标准库；不需要 perfect_hash 或 StarRocks checkout。
`source-reference.json` 是静态调查记录，不是构建依赖。

- **聚合**：65536 输入行，有限 256/65536 值域、稀疏 64 位键、2×32 位复合键；
  COUNT/SUM 状态使用无符号 64 位整数。0%/10% NULL 覆盖不同场景。
- **重复键 Join**：8192 构建行，distinct key 分别为 512/4096 的候选池，以及 64 键的热点倾斜；
  16384 探测行，目标命中比例 0%/50%/100%。重复匹配全部保留，通过匹配计数与构建行号求和核对。
- **Semi Join**：相同构建/探测输入，只需一个存在性结果；NULL 不匹配 NULL，不测试 NOT IN。
- **非定常聚合输入**：`phases` 先窄键域、再扩大键域引入新分组，然后热点从前 8 键迁到末 8 键。
  这是输入内容与分布的阶段变化；没有键删除、长期收缩、分组状态淘汰或多线程。
- **未命中**：有限域场景混合域内空洞和域外键，避免仅比较越界快速拒绝；实际命中率包含 NULL 影响。

键编码在计时前完成：整数键与二进制键对照测键表示及哈希路径，不包括原始列序列化成本。
`flat-fp` 和 `flat-bytes` 都有指纹过滤，便于比较两种表示；`flat-u64` 对照 `flat-fp` 则固定键表示。
前者键/hash 路径不同，后者是指纹开关的控制变量比较，不能混为一个原因。

## 计时与正确性边界

聚合计时包含建表、分组查找/插入、COUNT/SUM 更新、扩容和销毁；每轮重新处理完整输入流。
Join build 包含构建和销毁，并用一条 probe 消费结果；Join probe 单独测预热后的完整行链遍历，
没有物化输出行；Semi probe 只测存在性。各阶段单位为 ns/输入行，不能跨阶段直接排名。

每项测量前逐项比较所有聚合状态，或每个 probe 的匹配行数与行号和。计时循环还检查流式校验和。
NULL 在聚合中形成一个分组，在普通等值 Join 中不产生匹配。位图只适合存在性语义，不能替代重复行 Join。
构建行输入由外部持有，行号链没有逐行堆节点；聚合状态采用内联 COUNT/SUM，并未模拟 StarRocks 的状态池。

报告同时展示墙钟与进程 CPU 耗时、内存请求字节、非空实际分组数、NULL 行数、实际命中率。
容量与实际占用率是各结构的布局信息，不保证相同内存预算。重复率、链长对 Join 另有影响。
Join 的访问步数和键比较在计时外诊断；访问步数包含索引槽和构建行链节点。
`phases` 的性能是整条流的均摊结果，目前没有逐阶段时延图或操作 P99。

直寻址先要求明确且有界的值域，默认拒绝超过 1M 个域值；稀疏 64 位与复合键不会自动套用。
运行时新键只要在值域内即可加入，因此与编译期固定实际键集合的 perfect hash 有不同适用范围。

## 后续实验

1. 已新增 [大状态分离存储与 lazy-emplace 实验](STATE_LAYOUTS.md)：对照 COUNT/SUM 与大状态，包含逐阶段计时。
2. two-level 分区表、实际跨缓存规模、哈希预计算与软件预取；预取距离为控制变量。
3. 稠密映射压缩、多个可空字段的位打包与序列化成本；覆盖边界和范围变化后的回退。
4. SQL 类型语义：有符号整数、浮点 NaN/±0、字符串归一化、null-safe Join。
5. 输出物化、外连接与残余谓词、运行时过滤、溢写、多线程与 NUMA。
