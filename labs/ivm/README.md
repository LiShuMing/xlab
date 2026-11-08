# ivm —— 增量视图维护与 DBSP 原型

用集合运算手工推导增量视图维护（Incremental View Maintenance，IVM）的更新公式，
再用 DBSP（Database Stream Processing，数据库流处理）的代数结构把同一套公式形式化。
Python 与 Rust 实验均只使用标准库，不依赖数据库，方便逐行对照公式与代码。
Rust 版本进一步实现有序批次、压缩 radix tree 与可撤回时间区间聚合。

## 前置条件

- Python 3.11+，只用标准库与 `unittest`
- `dbsp/` 下的用例是 pytest 风格，需要先装 `pytest`；`ivm.py` 的用例不需要
- Rust 实验独立构建，Cargo 清单声明 Rust 1.75+，不需要 Python 环境

## 快速开始

```sh
cd labs/ivm
python3 -m unittest discover -s pyivm -p 'test_*.py' -v   # join 与增量公式用例
cd dbsp && python3 -m pytest -q                        # DBSP 代数结构用例
```

Rust 实验从仓库根目录运行：

```sh
cargo test --offline --locked --manifest-path labs/ivm/rust/Cargo.toml
cargo run --offline --locked --manifest-path labs/ivm/rust/Cargo.toml --example time_series
```

## 目录

```text
labs/ivm/
├── pyivm/                      # Python join 与增量公式
│   ├── ivm.py                  # 批式 join 与增量 join 公式
│   └── test_left_anti_semi_join.py # left_anti_semi_join 的边界用例
├── dbsp/                       # Python DBSP 代数结构：ZSet、Stream、join
│   ├── dbsp.py
│   └── test_dbsp.py
└── rust/                       # 独立 ZSet / batch / 时间序列 radix tree 实验
    ├── Cargo.toml
    ├── src/
    ├── tests/
    └── examples/time_series.rs
```

## ivm.py 覆盖的内容

- 批式 join：`inner_join`、`left_semi_join`、`left_anti_semi_join`、
  `left_outer_join`、`right_outer_join`、`full_outer_join`，连接键由 `on_key_index` 指定。
- 增量公式：`incremental_inner_join_poc` 等把 ΔR / ΔS 的增删代入
  `ΔV = ΔR ⋈ S + R ⋈ ΔS + ΔR ⋈ ΔS`，得到 ΔV 后与 V1 合并。

## dbsp 覆盖的内容

- `AbelianGroupOperation` 协议：加法、取逆、单位元，以及交换律/结合律/逆元的自检。
- `Stream`、`ZSet`（带重数的集合）及其加法群实现，`join` 用比较函数加上后置投影模拟连接。

## 已知边界

- 表是 Python `set`，`True == 1 == 1.0` 会被当成同一个键；没有 SQL 类型转换与
  NULL 三值逻辑。
- 增量函数是 POC，带 `print` 输出用于教学演示，不做性能优化，也不持久化。
- `dbsp/` 是代数结构的玩具实现，不是可用的流处理引擎。

## Rust 实验

[运行入口](rust/README.md)与[设计/学习教程](rust/TUTORIAL.md)：canonical ZSet、
有序批次与前进游标、节点差分、SUM/COUNT 与 MIN 撤回、对照全量扫描。
对照公开 Feldera 固定提交独立实现，不是其运行时移植；没有 Trace、持久化或并行调度。
