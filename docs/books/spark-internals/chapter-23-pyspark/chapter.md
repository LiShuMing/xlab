# 第 23 章：PySpark DataFrame & Python-JVM 桥接

## 设计动机

Spark 的内核是 Scala/Java（JVM）。但数据科学家和工程师写的是 Python。这两者的和谐共存需要一个"跨语言通道"——把 Python 的 `df.filter("age > 30").groupBy("dept").count()` 变成 JVM 中 `Dataset.filter().groupBy().count()` 的执行。

最笨的做法是"每个方法调用都启动一个子进程执行 spark-submit"。最聪明的做法是找到一个"零序列化开销 + 零语言切换开销"的通道。现实中的 PySpark 走了一条中间的工程路径——**Py4J socket 网关 + Arrow 列式传输**。它不是完美的（有序列化开销、有 GIL 约束），但在工程上的代价/收益比是合理的。

PySpark 的价值不在于"性能"（它不如纯 Scala/Java），而在于"可及性"——让世界上最庞大的数据从业群体（Python 用户）能够用他们的母语处理 PB 级数据。

## 核心原理

### 23.1 Py4J — Socket 上的 JVM 对象代理

PySpark 的 Python-JVM 通信基于 Py4J——一个通过 TCP Socket 在 Python 和 JVM 之间传递对象引用的库：

```
Python 进程                                JVM 进程 (Executor/Driver)
────────────                              ──────────────────────────
pyspark.sql.SparkSession                  
  └── _jsparkSession: JavaObject           SparkSession (Scala)
        │ (Py4J reference)                      ↑
        │                                       │
        └── GatewayClient ───TCP Socket──→ GatewayServer
              (localhost:25333)                  │
                                          GatewayServer 维护:
                                            objectId → JVM object 映射表

Python:  df._jdf.filter("age > 30")
  → Py4J: 发送命令 "call object#12345 method 'filter' with arg 'age > 30'"
  → JVM:   收到命令 → lookup object#12345 = Dataset[Row] → dataset.filter("age > 30")
  → Py4J:  返回新对象 reference object#12346
  → Python: 包装为新的 JavaObject
```

Py4J 的核心是一个 **引用表**（Reference Map）。JVM 端维护一个 `Map<String, Object>`，key 是由 GatewayServer 生成的目标名称（如 `obj123`），value 是 JVM 对象。Python 端持有这些 key 的引用，通过 socket 向 GatewayServer 发送指令：

```python
# 在 pyspark 中的实际使用:
# python/pyspark/sql/session.py
class SparkSession:
    def _create_shell_session(self):
        # 通过 Py4J 调用 JVM 的 SparkSession.builder
        jsparkSession = self._jvm.SparkSession.builder()
            .appName("PySparkShell")
            .getOrCreate()
        return jsparkSession
```

**关键限制**：Py4J 是 **request-response** 模型——Python 发送请求 → JVM 执行 → 返回结果。它不是异步的，不能做 streaming 推数据。对于 Data 的传输（大数据量），Py4J 是瓶颈——每次方法调用的参数和返回值都要序列化。PySpark 为此将"元数据操作"（如创建 DataFrame、定义转换）走 Py4J，将"数据传输"（如 collect、toPandas）走**独立的 Arrow 通道**。

### 23.2 PySpark 进程模型

```
PySpark Driver (Python 进程):
  ├── Py4J GatewayClient ──TCP──→ JVM Driver (SparkSubmit)
  │                                  ├── SparkContext
  │                                  ├── SparkSession
  │                                  └── Py4J GatewayServer
  ├── Python SparkSession
  │     └── _jsparkSession (Py4J reference → JVM SparkSession)
  └── PySpark DataFrame
        └── _jdf (Py4J reference → JVM Dataset[Row])

PySpark Executor (Python 进程):
  ├── Py4J GatewayClient ──TCP──→ JVM Executor (CoarseGrainedExecutorBackend)
  │     (sidecar 模式: Python 进程与 JVM 在同一容器)
  └── Python UDF Runner (处理 UDF/Pandas UDF)

数据传输路径:
  Python ←→ JVM:
    小数据 (metadata/配置): Py4J (TCP Socket)
    大数据 (rows/columns):  Arrow (Socket 或 shared memory, 通过 Spark's RPC)
```

### 23.3 DataFrame 操作 — Python 到 JVM 的翻译

当用户写 `df.filter(df.age > 30).groupBy("dept").count()` 时，Python 在做什么：

```python
# pyspark/sql/dataframe.py
class DataFrame:
    def filter(self, condition):
        # condition 是一个 Column 对象，包装了 JVM 的 Column 表达式
        if isinstance(condition, Column):
            jcondition = condition._jc  # 取 JVM 侧的 Column 引用
        else:
            jcondition = condition
        # 通过 Py4J 调用 JVM 的 filter
        jdf = self._jdf.filter(jcondition)
        return DataFrame(jdf, self.sparkSession)
    
    def groupBy(self, *cols):
        jcols = self._to_java_column_seq(cols)  # Python Column → JVM Column 列表
        jgd = self._jdf.groupBy(jcols)
        return GroupedData(jgd, self.sparkSession)
```

整个过程是 **lazy 的**——所有 Python 层面的 `filter`/`select`/`groupBy` 都只是往 JVM 的 `Dataset[Row]` 上追加逻辑计划节点。直到 `.collect()` 或 `.show()` 才触发真正的执行。

**Column 表达式**：`df.age > 30` 在 Python 中调用 `Column.__gt__` → 创建 `Column(jvm_column.gt(30))`。Column 对象的 `_jc` 字段持有一个 Py4J 引用指向 JVM 的 `Column` 对象。整个表达式树在 JVM 侧构建，Python 只持有根节点的引用。

### 23.4 Python UDF — 逐行序列化的代价

最简单的 Python UDF 每行数据需要穿越 Python ↔ JVM 边界两次：

```
DataFrame.withColumn("new_col", udf(lambda x: x + 1, IntegerType())("age"))

执行过程（逐行）:
  1. JVM 将 InternalRow 序列化为 Python 对象 (pickle / cloudpickle)
  2. 通过 Socket 发送给 Python worker 进程
  3. Python 执行 udf(x + 1)
  4. 结果 pickled 并发送回 JVM
  5. JVM 反序列化 → InternalRow

每行的代价:
  - 2 次序列化/反序列化 (pickle)
  - 2 次 socket 通信（跨进程）
  - 1 次 Python 函数调用（GIL 持有）
  - 数据类型转换 (Java → Python → Java)
```

这就是为什么 "普通 UDF" 比内置函数慢 **10-100 倍**——不是 Python 慢，是**序列化 + 跨进程通信**慢。一条 row 可能只需要 1μs 的 Python 操作，但要花费 50μs 的序列化+传输。

### 23.5 Pandas UDF (Vectorized UDF) — Arrow 列式传输

Spark 2.3 引入的 Pandas UDF（又名 Vectorized UDF）根本改变了这个范式——不是逐行传，而是**按 batch（列式）传**：

```
Pandas UDF (SCALAR 类型):
  from pyspark.sql.functions import pandas_udf
  
  @pandas_udf("long")
  def add_one(v: pd.Series) -> pd.Series:
      return v + 1

执行过程（按 batch）:
  1. JVM 收集一个 batch（默认每 10000 行）的列数据
  2. 通过 Arrow IPC 格式发送给 Python worker
     → Arrow 是列式格式: 整列数据是连续的字节数组
     → 不需要逐行 pickle!
  3. Python 将 Arrow 列数据零拷贝转换为 pd.Series
  4. Pandas UDF 在整个 Series 上做向量化运算（利用 NumPy C 扩展）
  5. 结果通过 Arrow 传回 JVM

每 batch 的代价:
  - 1 次 Arrow 序列化 (列式, 比 pickle 快 ~10×)
  - 1 次 socket 通信 (传输列式字节流)
  - 1 次 Numpy/Pandas 向量运算 (释放 GIL)
  - 0 次 data type 转换 (Arrow types ↔ Spark types 原生映射)
```

**Arrow 格式的优势**：

| 维度 | 逐行 Pickle (普通 UDF) | Arrow 列式 (Pandas UDF) |
|------|----------------------|------------------------|
| 序列化 | 逐行 pickle (Python object → bytes) | 列式 Arrow IPC (columnar bytes) |
| 压缩 | 无 | 内置 dictionary encoding |
| 类型映射 | 需要 Python↔Java 转换 | Arrow types 原生映射 |
| 内存布局 | scattered Python objects | 连续列式内存 |
| 每个 batch 开销 | N × (pickle + send + recv + unpickle) | 1 × (Arrow serialize + send + recv + deserialize) |

一个典型的 10 万行、从字符串到整数加一的 Pandas UDF 比普通 UDF 快 **5-20 倍**。

**Pandas UDF 的四种类型**：

| 类型 | 输入 | 输出 | 用途 |
|------|------|------|------|
| SCALAR | `pd.Series → pd.Series` | 相同长度 | 标量变换 (e.g. abs, log) |
| GROUPED_MAP | `pd.DataFrame → pd.DataFrame` | 任意 | groupBy + apply |
| GROUPED_AGG | `pd.Series → scalar` | 一个值 | 自定义聚合 |
| GROUPED_MAP_ITER | `Iterator[pd.DataFrame] → Iterator[pd.DataFrame]` | 任意 | 流式 group apply (Spark 4.0) |

### 23.6 Arrow 加速的 toPandas 与 collect

`.toPandas()` 的整体流程也受益于 Arrow：

```
df.toPandas() 的两种模式:

模式 A (无 Arrow, fallback):
  1. df.collect() → JVM 收集所有 InternalRow
  2. 逐行 pickle → Python
  3. Python 逐行反序列化为 Python 对象
  4. 构建 pandas DataFrame (逐列 append)
  → 最慢, 10 万行可能需要 10-30 秒

模式 B (有 Arrow, 默认):
  1. df._collectAsArrow() → JVM 将 InternalRow batch 转为 ArrowRecordBatch
  2. Arrow 二进制流 → Python (通过 Socket)
  3. pyarrow.RecordBatch → pandas DataFrame (零拷贝)
  → 10 万行约 0.5-2 秒
```

`spark.sql.execution.arrow.pyspark.enabled = true`（默认）是这个加速的背后支撑。

### 23.7 内存模型 — Python 与 JVM 的双重占用

PySpark 的一个重要但容易被忽略的设计问题是**双内存占用**——Python 进程和 JVM 进程分别在吃内存：

```
PySpark Executor 的内存占用:
  JVM 进程:
    ├── Heap (execution + storage + user): 默认 driver/executor memory 的 60%
    └── Off-heap (Tungsten pages, Netty buffers, GC overhead)
  
  Python 进程 (sidecar):
    ├── Python interpreter + loaded modules (~50-100MB baseline)
    ├── Pandas/NumPy arrays (toPandas, Pandas UDF)
    └── Pickle serialization buffers

如果 executor.memory = 8GB:
  JVM: ~4.6GB for unified pool + ~1-2GB for JVM overhead + GC
  Python: ~0.5-2GB for Pandas/NumPy (取决于 toPandas 或 Pandas UDF 的 batch 大小)

→ 实际可用内存 < 8GB，OS 可能看不到 Python 的内存和 JVM 的内存加在一起超限
→ 这经常是 YARN/K8s 中 OOM 的隐性原因
```

`spark.pyspark.python` 和 `spark.pyspark.driver.python` 可以指定 Python 解释器版本——这对虚拟环境管理至关重要。

## 关键代码片段

### 示例：PySpark Collect 的完整路径

```python
# python/pyspark/sql/dataframe.py
def collect(self):
    with SCCallSiteSync(self._sc):
        sock_info = self._jdf.collectToPython()  # JVM 执行全部 Stage → 收集结果
    # sock_info 包含: JVM 开启了临时 R 的 socket, Python 要在其上读取数据
    return list(_load_from_socket(sock_info, ...))

# 实际上 Spark 3.4+ 及以后版本中, collect 直接通过 Arrow 或 batch 传输
# python/pyspark/sql/pandas/serializers.py 中有 ArrowCollectSerializer
# 将 Arrow 批次从 JVM 传输到 Python
```

### 示例：Pandas UDF 的类型定义

```python
# python/pyspark/sql/pandas/functions.py
def pandas_udf(f=None, returnType=None, functionType=None):
    # returnType: 输出的 Spark SQL 类型
    # functionType: SCALAR / GROUPED_MAP / GROUPED_AGG
    #
    # 检查 Arrow 是否可用:
    # if not _pandas_udf_enabled_and_arrow_installed():
    #     raise RuntimeError("Pandas UDF requires PyArrow")
    #
    # 包装函数, 注册 UDF
    pass
```

## 硬件视角

**Python Subprocess 的 NUMA 效应**：

PySpark 的 Python worker 进程与 JVM Executor 在同一台机器上（同一 NUMA 节点或不同）。如果是 Pandas UDF，Arrow 数据从 JVM → Python 的内存拷贝跨越了进程边界——这意味着要么通过 Socket buffer（TCP memcpy），要么通过共享内存（更好的方案）。

在多 NUMA 节点环境中，进程调度策略影响 Arrow 传输的效率：如果 Python worker 运行在 NUMA-1，JVM 运行在 NUMA-0，Arrow 的数据写入 Socket → kernel socket buffer（NUMA-0）→ Python 读取 → NUMA-1。跨 NUMA 节点的内存访问比本地 NUMA 慢 20-40%。PySpark 在这方面没有显式的 NUMA affinity 控制——它在大型 NUMA 机器上可能产生性能退化。

**Pandas UDF 的 CPU 缓存效应**：

Pandas UDF 的一个 batch 通常是 10000 行 × 10 列。对于 `double` 类型，一个 batch 的列数据是 10000 × 8 = 80KB——正好比 L1 cache 大（32KB），但比 L2 cache 小（256KB）。如果 UDF 操作是"读一列、写一列"的模式，L2 命中率很高。

但如果 UDF 是 GROUPED_MAP 类型——接收 100MB 的 pd.DataFrame → 排序 100MB 的数据 → 输出——100MB >> L3 cache（~40MB） → 每个操作都是 DRAM access（~100ns）→ 性能退化明显。

## AI 时代反思

PySpark 的 Python-JVM 桥接是 LLM Agent 的一个"高频接触区"。因为大多数数据科学家通过 PySpark 与 Spark 交互，LLM 在这种情况下最常做的事情是**生成 PySpark 代码**（`df.groupBy(...).agg(...).collect()`）——这件事 LLM 做得还不错。

但 LLM 几乎从不做的是 **PySpark 性能诊断**：
- "这个 Pandas UDF 每 batch 只处理 100 行，Arrow batch size 默认是 10000 → 建议增大 batch 或改用内置函数"
- "这个 toPandas 返回了 500 万行 DataFrame，Arrow 传输时会将整个结果加载到 Driver 的 Python 进程内存中 → 建议先 aggregate 到较小数据集再 collect"

这是因为 LLM 训练数据中 PySpark 的性能调优内容远少于语法内容——和整个 Spark 技术栈的模式相同。

从这个角度，**PySpark 的 AI-native 优化工具**应该是一个"Python → Optimized JVM"的透明加速器——它分析 Python 代码，识别出"这个 UDF 实际上可以用一个内置的 SQL expression 替代"的模式，然后在 JVM 侧自动做替换。这类似于 SQL optimizer 的 rule-based rewrite，但目标语言是 Python + PySpark API。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `python/pyspark/sql/session.py` | SparkSession Python 实现，SparkSession.Builder，getOrCreate | |
| `python/pyspark/sql/dataframe.py` | DataFrame Python API，filter/select/groupBy/agg 映射到 _jdf，collect/toPandas | |
| `python/pyspark/sql/column.py` | Column 表达式包装，_jc 引用 JVM Column，__gt__/__lt__/__add__ 运算符重载 | |
| `python/pyspark/sql/functions.py` | Python 内置函数（col, lit, when, udf, pandas_udf） | |
| `python/pyspark/sql/pandas/functions.py` | Pandas UDF 装饰器，SCALAR/GROUPED_MAP/GROUPED_AGG 类型分发 | |
| `python/pyspark/sql/pandas/serializers.py` | Arrow 序列化器，ArrowCollectSerializer，ArrowStreamSerializer | |
| `python/pyspark/rdd.py` | RDD API，PythonRDD 逻辑 | |
| `python/pyspark/java_gateway.py` | Py4J Gateway 初始化，launch_gateway | |
| `core/src/main/scala/org/apache/spark/api/python/PythonRDD.scala` | PythonRDD，JVM 端 Python worker 交互 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/python/ArrowEvalPythonExec.scala` | Arrow 模式 Pandas UDF 物理执行算子 | |
