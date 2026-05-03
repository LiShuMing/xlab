# 第 24 章：Pandas API on Spark — 让 pandas 用户无缝接入 Spark 生态

## 设计动机

数据科学界有一个巨大的断层：pandas 是全球最流行的数据处理库之一（数千万用户），而 Spark 是处理 TB/PB 级数据的工业标准。一个数据科学家用 pandas 写的分析脚本在本地跑 100MB 数据时一切正常，但当数据增长到 100GB 时——pandas 的 in-memory 架构崩塌了。

解决这个问题有三种思路：

1. **给 pandas 加分布式后端**：让 `pd.read_csv()` 背后跑一个 Spark Job。这听起来很理想，但 pandas API 有大量强假设——所有数据都在内存中、索引是有序的、操作是 eager 的——这些假设在分布式环境中全部不成立。

2. **教数据科学家写 PySpark**：`df.filter().groupBy().agg()` 语法和 `df[df.x > 0].groupby('y').sum()` 是完全不同的心智模型。学习曲线陡峭。

3. **实现一个 "pandas-like" API 但底层跑在 Spark 上**：让用户的 pandas 代码无需修改（或仅需微小改动）就能在 Spark 上运行。这就是 Pandas API on Spark 的路线——原先由 Databricks 以 **Koalas** 项目孵化，Spark 3.2 起合并为 `pyspark.pandas`。

这个项目的核心挑战可以浓缩为一句话：**分布式计算缺少 pandas 依赖的那个"全局顺序"**。pandas 的 `iloc[5]` 假设第 5 行是一个明确定义的东西；在分布式分区中，没有天然的"第 5 行"。整个 Pandas API on Spark 的设计都在围绕这个问题展开——如何模拟 pandas 的顺序语义，又不损失分布式并行性。

## 核心原理

### 24.1 从 Koalas 到 pyspark.pandas — 合并的动机与取舍

Databricks 在 2019 年开源 Koalas 时，它的定位是"pandas API on Apache Spark"。用户只需将 `import pandas as pd` 替换为 `import databricks.koalas as ks`，大部分代码就能在 Spark 上运行。

Spark 3.2 将 Koalas 合并为主仓库的 `pyspark.pandas`，原因很简单：
- 作为独立项目，Koalas 的版本节奏和 Spark 不同步——用户经常遇到"Spark 3.1 能用哪个版本的 Koalas?"的兼容性问题
- 合并后，pandas-on-Spark 可以直接使用 Spark 内部 API（如 `InternalFunction`），性能更好
- 更重要的是——消除了"这个 API 是 Koalas 的还是 PySpark 的"这种认知负担。`import pyspark.pandas as ps` 在概念上统一了两种范式

合并的代价是 pandas-on-Spark 的发布周期被绑定到 Spark 的 3-4 个月发布节奏——一些 pandas 新版本引入的 API 需要等待更长时间才能被支持。

### 24.2 核心架构 — DataFrame/Series 对 Spark DataFrame 的包装

Pandas API on Spark 的架构可以理解为三个层次：

```
pandas 用户层:
  ps.DataFrame, ps.Series, ps.Index, ps.MultiIndex
    └── 提供与 pandas 几乎相同的 API 签名

中间元数据层:
  InternalFrame (不可变)
    ├── spark_frame: PySpark DataFrame (包含索引列+数据列)
    ├── data_spark_column_names: 数据列的 Spark 列名
    ├── index_spark_column_names: 索引列的 Spark 列名
    │     (格式: __index_level_0__, __index_level_1__, ...)
    ├── index_names: 外部索引名称 (e.g. [None] 或 ['date'])
    └── data_fields / index_fields: InternalField 列表 (dtype+nullable)

底层执行层:
  Spark DataFrame → Catalyst → Tungsten → 分布式执行
```

**关键设计：索引存储在数据中**。pandas 的 Index 是一个独立的、不可变的对象，位于 DataFrame 的"侧面"。但在 pandas-on-Spark 中，索引被存储为 Spark DataFrame 中的**普通列**——列名前缀为 `__index_level_N__`。这种存储方式打破了 pandas 的认知模型（"索引不是列"），但换来的是分布式处理的一致性——索引和数据的 join/filter/sort 都可以用 Spark 的标准算子完成，不需要特殊的 distributed index 机制。

```python
# 内部表示示例:
psdf = ps.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})

# psdf._internal.spark_frame 中包含:
# +-----------------+---+---+-----------------+
# |__index_level_0__|  A|  B|__natural_order__|
# +-----------------+---+---+-----------------+
# |                0|  1|  4|                0|
# |                1|  2|  5|                1|
# |                2|  3|  6|                2|
# +-----------------+---+---+-----------------+

# index_spark_column_names = ['__index_level_0__']
# data_spark_column_names = ['A', 'B']
# HIDDEN_COLUMNS = {'__natural_order__'}  ← 不暴露给用户
```

`InternalFrame` 是**不可变的**（immutable）。每次操作（filter、drop、rename 等）都产生新的 `InternalFrame`——这模仿了 Spark DataFrame 的不可变性，同时保持 pandas API 的"返回新对象"语义。这种不可变性避免了"共享的 InternalFrame 被一个操作修改而另一个操作还在引用它"的并发风险。

`__natural_order__` 是一个隐藏列，通过 `F.monotonically_increasing_id()`（或 `Window.orderBy` 生成的 row_number）填充。它的作用是保留"数据的最初顺序"——当 pandas-on-Spark 需要在 `head()` 或 `tail()` 操作中恢复顺序时使用。注意它不是全局排序（分布在多个分区中的数据没有严格的全局顺序），但"natural order + 同分区内的相对顺序"在大部分场景下已经足够。

### 24.3 默认索引的三种类型 — 顺序在分布式中的重构

这是整个 Pandas API on Spark 中最微妙的设计决策。当一个 pandas DataFrame 被转换为 pandas-on-Spark DataFrame 时，索引有三种可能的处理方式：

```
compute.default_index_type 的三种取值:

1. sequence (顺序索引):
   - 用 F.monotonically_increasing_id() 生成连续的 64 位整数
   - 最快: O(1) 开销，无需分布式排序
   - 问题: monotonically_increasing_id() 不保证全局连续——
     分区 0 生成 0, 1, 2, ...; 分区 1 生成 2^33, 2^33+1, ...
     所以索引值不是真正的 0, 1, 2, 3, ...
   - 适用于不需要"索引反映行序号"的场景

2. distributed (分布式索引):
   - 通过 Window.rowsBetween 在每个分区内重新编号
   - 需要先确定全局顺序 → 收集分区的边界信息
   - 更慢但更精确: 生成的索引在全局范围内连续
   - 适用于需要精确索引的场景 (e.g. iloc)

3. distributed-sequence (混合索引, 默认):
   - 新数据: 使用 sequence (快速生成)
   - join/concat 等操作: 自动转为 distributed
   - 权衡: 大部分场景下有 sequence 的速度，必要时退回到 distributed 的精度
```

```python
# sequence 模式的实现 (简化):
def default_index_sequence(num_partitions: int) -> PySparkColumn:
    # SPARK_INDEX_NAME_FORMAT = "__index_level_{}__"
    # 生成偏移量 + 分区内递增的 ID
    return F.spark_partition_id() * (1 << 33) + F.monotonically_increasing_id()

# distributed 模式的实现 (简化):
def default_index_distributed(spark_frame: PySparkDataFrame) -> InternalFrame:
    # 先按 natural_order 排序 → 生成 row_number
    # 这需要一个全局排序操作——慢
    return InternalFrame(
        spark_frame=spark_frame.withColumn(
            SPARK_INDEX_NAME_FORMAT(0),
            F.row_number().over(Window.orderBy(NATURAL_ORDER_COLUMN_NAME)) - 1
        ),
        index_spark_column_names=[SPARK_INDEX_NAME_FORMAT(0)],
        ...
    )
```

### 24.4 计算模型 — Shortcut vs Distributed 的双模执行

pandas-on-Spark 的操作不是永远跑在 Spark 上的。它有一个聪明的 **双模执行模型**：

```
DataFrame.some_operation()
  │
  ├── 计算当前 DataFrame 的预估行数
  │
  ├── if 行数 <= compute.shortcut_limit (默认 1000):
  │     → shortcut 路径:
  │       1. to_pandas() → 将数据收集回 Driver
  │       2. 在 pandas DataFrame 上执行真正的操作
  │       3. 将结果封装回 pandas-on-Spark DataFrame
  │       → 优点: 小数据上 pandas 比 Spark 快 (无 Job 调度开销)
  │       → 缺点: 大数据上会打爆 Driver 内存
  │
  └── else:
        → distributed 路径:
          1. 将操作翻译为 Spark DataFrame 的算子组合
          2. 执行 Spark Job
          3. 直接返回 pandas-on-Spark DataFrame
          → 优点: 可处理任意量级的数据
          → 缺点: 每个操作都是至少一个 Spark Job
```

这个双模模型的直接后果是同一个函数在行数 ≤ 1000 和行数 > 1000 时可能走完全不同的代码路径——这意味着前者里 pandas 的 behavior（精确的类型推断、错误处理等）在后者中要用 Spark 来模拟——经常出现 subtle 的语义差异。

`compute.ops_on_diff_frames`（默认为 True）控制一个更根本的行为：是否允许两个来自不同 Anchor（不同 Spark DataFrame 来源）的 pandas-on-Spark DataFrame/Series 进行联合操作。当设为 False 时，`psdf1['A'] + psdf2['B']` 如果 psdf1 和 psdf2 来源不同则直接抛异常——因为底层需要执行一个昂贵的 join 来对齐两者的索引。当设为 True 时，pandas-on-Spark 会自动执行这个 join，但用户可能不意识到这个"简单的加法"背后是一个分布式的 join + shuffle。

### 24.5 缺失功能层 — MissingPandasLike* 的错误引导

pandas 的 API 覆盖面极广（DataFrame 有 400+ 个方法）。Pandas API on Spark 无法全部支持——有些方法在分布式环境中没有意义（如 `to_pickle`），有些因为 Spark 不暴露相应的内部接口而不可能实现（如 `infer_objects`）。

为了让用户面对 unsupported API 时得到有意义的错误提示而不是 `AttributeError`，pandas-on-Spark 实现了一套 "Missing API" 机制：

```python
# python/pyspark/pandas/__init__.py
def __getattr__(key: str) -> Any:
    if hasattr(MissingPandasLikeScalars, key):
        raise getattr(MissingPandasLikeScalars, key)
    if hasattr(MissingPandasLikeGeneralFunctions, key):
        return getattr(MissingPandasLikeGeneralFunctions, key)

# python/pyspark/pandas/missing/frame.py
class MissingPandasLikeDataFrame:
    asfreq = _unsupported_function("asfreq")
    asof = _unsupported_function("asof")
    convert_dtypes = _unsupported_function("convert_dtypes")

# 当用户调用 ps.DataFrame(...).asfreq() 时:
# → 抛 PandaNotImplementedError("...asfreq is not implemented yet...")
```

`missing/` 目录下按功能域拆分了多个文件——`frame.py`、`series.py`、`groupby.py`、`indexes.py`、`window.py`、`resample.py`、`general_functions.py`、`scalars.py`，每个都包含该类不支持的方法/属性及其原因（deprecated、不适用、尚未实现）。这种设计把 "API 兼容性差距" 从一个隐蔽的运行时 bug 变成了一个可以文档化、可搜索、有建设性错误信息的显式问题。

### 24.6 类型运算的分发 — DataTypeOps 体系

pandas 的类型系统与 Spark 有一个根本性的分歧——pandas 的类型运算（如整数除法、字符串拼接）是在 Python 层面由 pandas 库自身实现的；Spark 的类型运算（如 `5 / 2 = 2.5`）是由 Catalyst 和 Tungsten 决定的。当 pandas-on-Spark 中的 `psdf['A'] / psdf['B']` 被调用时，结果必须匹配 pandas 的行为，但底层是 Spark 在执行。

为此，pandas-on-Spark 建立了一套 `DataTypeOps` 体系：

```
DataTypeOps 基类 (base.py)
  ├── NumOps      (num_ops.py)       ← int, float, decimal
  ├── StringOps   (string_ops.py)    ← string
  ├── BooleanOps  (boolean_ops.py)   ← bool
  ├── DateOps     (date_ops.py)      ← date
  ├── DateTimeOps (datetime_ops.py)  ← timestamp
  ├── BinaryOps   (binary_ops.py)    ← binary
  ├── ComplexOps  (complex_ops.py)   ← array, map, struct
  ├── CategoricalOps (categorical_ops.py) ← categorical
  ├── TimeDeltaOps (timedelta_ops.py)     ← timedelta
  ├── NullOps     (null_ops.py)      ← null
  └── UDTOps      (udt_ops.py)       ← user-defined types
```

每个 `DataTypeOps` 子类实现了该类类型上的所有算术/逻辑/比较操作。当一个 `Series.__add__` 被调用时，pandas-on-Spark 根据 Series 的数据类型查找对应的 `DataTypeOps` 实例 → 调用其 `add` 方法 → 该方法生成正确的 Spark Column 表达式。

### 24.7 to_spark 与 to_pandas — 双向互转的桥梁

pandas-on-Spark 最有价值的 pydynamic 之一是 `to_spark()` 和 `to_pandas()` 的双向互转——让用户在 pandas 范式和 Spark 范式之间灵活切换：

```python
# pandas-on-Spark → Spark DataFrame
spark_df = psdf.to_spark(index_col='date')  # 索引可转为 Spark 列

# Spark DataFrame → pandas-on-Spark
psdf = spark_df.to_pandas_on_spark(index_col='date')

# Spark DataFrame → pandas
pdf = spark_df.toPandas()  # 使用 PySpark 的 collect → 注意内存
```

`to_spark()` 返回一个标准的 PySpark DataFrame——这是调用 Spark MLlib 或用户自定义的 Scala UDF 的入口。`to_pandas()` 返回一个本地 pandas DataFrame——适用于数据已聚合到可行的大小（<1GB），后续做 matplotlib/seaborn 可视化或 scikit-learn 训练。

### 24.8 与 pandas UDF 的协同 — 使用 pandas API in Spark Pipeline

pandas-on-Spark 和 Pandas UDF（第 23 章）可以天然协同工作：

```python
# 场景: 先用 pandas-on-Spark 清洗/特征工程 → 再用 Spark ML 训练模型
import pyspark.pandas as ps
from pyspark.sql.functions import pandas_udf
from pyspark.ml.classification import LogisticRegression

# Step 1: 用 pandas-on-Spark 的 pandas-like API 处理特征
psdf = ps.read_parquet("hdfs://...")
features = psdf.groupby("user_id").agg(
    avg_amount=("amount", "mean"),
    total_count=("amount", "count"),
    last_purchase=("timestamp", "max")
)

# Step 2: 转回 Spark 进入 ML pipeline
spark_df = features.to_spark(index_col="user_id")
lr = LogisticRegression()
model = lr.fit(spark_df)
```

这就是 "pandas API on Spark" 的真正价值——不是让 100% 的 pandas 代码都能在 Spark 上运行（这是一种不切实际的期望），而是让 80-90% 的数据清洗/分析代码可以用熟悉的 pandas API 表达，在需要 Spark MLlib、Streaming、GraphX 等原生功能时通过 `to_spark()` 无缝切换。

## 关键代码片段

### 示例：DataFrame 的 filter 操作路径

```python
# python/pyspark/pandas/frame.py
class DataFrame:
    def __getitem__(self, key):
        # key 可以是列名、布尔 Series（mask）、切片等
        if isinstance(key, Series) and isinstance(key.spark.data_type, BooleanType):
            # 布尔索引: df[df['A'] > 0]
            # 这实际翻译为 Spark 的 filter
            return self.loc[self[key]]
        ...

# 底层翻译:
#   df[df['A'] > 0]
# → df['A'] > 0 产生一个 BooleanType Series
# → __getitem__ 调用 self.loc[mask]
# → LocIndexer → 生成 Spark DataFrame.filter(mask_column) 计划
```

### 示例：reshape_flow — NamedAgg 与 pandas 的 agg 语法兼容

```python
# python/pyspark/pandas/groupby.py
# 支持 pandas 的 NamedAgg 风格:
NamedAgg = namedtuple("NamedAgg", ["column", "aggfunc"])

# psdf.groupby("dept").agg(
#     avg_salary=("salary", "mean"),
#     max_age=("age", "max")
# )
# 内部翻译为 Spark 的:
#   spark_df.groupBy("dept").agg(
#       F.mean("salary").alias("avg_salary"),
#       F.max("age").alias("max_age")
#   )
```

## 硬件视角

**shortcut 路径的内存边界**：

`compute.shortcut_limit=1000` 默认值意味着 1000 行的数据通过 Driver 处理。对 10 列 × 1000 行 × 8 bytes (double) = 80KB——微不足道。但如果用户把 `compute.max_rows` 设为 None（关闭行数限制），shortcut 可能被触发在百万行级别：

```
1000 万行 × 50 列 × 8 bytes = 4GB → Driver 内存 + pickle 序列化 = 可能 ~8-10GB
```

这意味着 shortcut 机制对 `compute.max_rows` 非常敏感。一个"把 max_rows 改成 None 然后发现 my_func() 跑在 Driver 上 OOM"的生产事故在用户邮件列表中很常见。真正安全的模式是：先 `.to_spark()` → 用 Spark 宣布式 API 写完逻辑 → 最后再 `.to_pandas()`（当数据已聚合成可行大小）。

**distributed-sequence 索引的缓存开销**：

当默认索引类型为 `distributed-sequence` 且触发 distributed 模式时，pandas-on-Spark 为每个涉及 "行列位置操作"（如 `head`、`iloc`）缓存索引列，默认 StorageLevel 为 `MEMORY_AND_DISK_SER`。对 10 亿行 × 8 bytes 的索引列，这额外消耗 ~8GB 的 Executor 内存——但这比"每次都重算索引"的 CPU 开销要小得多。

## AI 时代反思

pandas API on Spark 可能是 LLM 生成 Spark 代码时最被低估的工具。大多数 LLM 生成的 PySpark 代码遵循 `df.filter().groupBy().agg()` 模式（LLM 在这方面的训练数据丰富）。但当用户需要复杂的 multi-column 操作、自定义索引、merge/join 的特定语义时，生成的 PySpark 代码经常在逻辑上"基本正确"但行为上"微妙错误"（例如 merge 的 indicator 参数、groupby 的 dropna 参数）。

pandas-on-Spark 提供了一种"两步走"的 AI 代码生成策略：
1. 让 LLM 用熟悉且训练数据丰富的 pandas API 生成核心逻辑
2. 用户 review 并确认逻辑正确后，再决定是否迁移到 native PySpark 以获得更快性能

这种策略利用了"LLM 擅长 pandas"这一事实，把 pandas-on-Spark 作为 LLM → Spark 的"中间表示层"——一种 human-readable、LLM-friendly、Spark-executable 的桥梁。

进一步看，pandas-on-Spark 本身是一个"API 兼容性项目"——这在 AI 时代有一个新的含义：**LLM 的 "function calling" 能力可以作为 missing API 的 fallback**。当 pandas-on-Spark 报告 `asof` is not implemented 时，一个 Agent 可以自动生成一个 Pandas UDF 实现该 missing function 的近似值——不是完美的（per-batch 的 asof 不同于全局 asof），但在很多场景中 "close enough" 比 "not at all" 好得多。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `python/pyspark/pandas/__init__.py` | 入口模块，auto_patch 机制，MissingPandasLike 错误引导 | |
| `python/pyspark/pandas/frame.py` | DataFrame 类（14414 行），完整的 pandas DataFrame API 实现 | ~388 (class DataFrame), ~5607 (to_spark), ~5624 (to_pandas) |
| `python/pyspark/pandas/series.py` | Series 类，逐元素操作的分布式实现 | |
| `python/pyspark/pandas/internal.py` | InternalFrame（不可变元数据容器），索引列/数据列映射，InternalField | ~86 (InternalField), ~219 (InternalFrame) |
| `python/pyspark/pandas/generic.py` | Frame 抽象类，DataFrame/Series 共享接口，loc/iloc 分发 | ~90 (class Frame) |
| `python/pyspark/pandas/base.py` | IndexOpsMixin，索引/Series 共享操作 | |
| `python/pyspark/pandas/namespace.py` | 顶层函数（read_csv, concat, merge, to_datetime 等） | |
| `python/pyspark/pandas/groupby.py` | DataFrameGroupBy/SeriesGroupBy，NamedAgg 支持 | |
| `python/pyspark/pandas/config.py` | compute.max_rows, compute.shortcut_limit, compute.ops_on_diff_frames, compute.default_index_type 等配置项 | ~120 (_options list) |
| `python/pyspark/pandas/missing/` | 按类型分类的 MissingPandasLike 类，unsupported 方法/属性 | |
| `python/pyspark/pandas/data_type_ops/` | DataTypeOps 体系，按类型分发运算逻辑 | |
| `python/pyspark/pandas/spark/accessors.py` | SparkIndexOpsMethods / SparkFrameMethods，Spark 独有功能的访问器 | |
| `python/pyspark/pandas/indexes/` | Index / MultiIndex / DatetimeIndex / CategoricalIndex 实现 | |
| `python/pyspark/pandas/plot/` | matplotlib plot 集成 | |
