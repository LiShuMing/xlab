# 第 28 章：Spark Native Engine — 算子 Native 化的效率来源

## 设计动机

Spark 的执行引擎（Tungsten）已经在 Java 堆外内存管理、代码生成、列式执行上做了大量优化。但它的根本限制是**所有计算都发生在 JVM 中**。JVM 不是为数据密集型计算设计的——它是为长时间运行的 Web 服务器设计的。两个最根本的瓶颈：

1. **JIT 编译的预热期**：Whole-Stage Codegen 在 Janino 编译完后，JVM 的 JIT 编译器（C1/C2）还需要数万次执行才能"预热"到最优机器码。对短查询（<1 秒），这段预热期占用了显著的执行时间。

2. **SIMD 无法直接控制**：现代 CPU 的 256-bit AVX2 或 512-bit AVX-512 指令可以在一个周期内完成 8 个 double 的加法。但 HotSpot JVM 的自动向量化（Auto-vectorization）只在特定模式（确定计数 + 确定边界 + 简单循环体）下才触发——稍微复杂一点的逻辑就退化回 scalar 执行。

3. **GC 抖动**：即使 Tungsten 极力使用堆外内存，临时对象（Iterator、ColumnarBatch 的 metadata、expression 的中间结果）仍在对堆施压。一个 100ms 的 batch 运算可能被 20ms 的 GC pause 打断——这导致 P99 延迟远高于 P50。

Native Engine 的答案是：**把最热的那部分算子从 JVM 移到 C++ 中执行**——利用 C++ 编译器（GCC/Clang）的激进向量化、直接的 SIMD intrinsics、更好的内存布局控制和无 GC 的确定性延迟。

这个方向有三个代表性项目：
- **Photon**：Databricks 的闭源 C++ native engine，与 Spark SQL 深度耦合
- **Gluten + Velox**：Intel/Meta 的 OSS 方案，Gluten 作为 Spark → Velox 的桥梁
- **Comet**：Apache 孵化项目，基于 Apache Arrow/DataFusion 的 native 加速插件

## 核心原理

### 28.1 Plug-in 接口 — Native Engine 的挂载点

Spark 通过 `SparkPlugin` 接口允许外部引擎挂载到执行路径中：

```scala
// Spark 的 Plugin API:
trait SparkPlugin {
  def driverPlugin(): DriverPlugin   // Driver 端插件
  def executorPlugin(): ExecutorPlugin  // Executor 端插件
}

// Native Engine 作为 ExecutorPlugin 注入:
trait ExecutorPlugin {
  def init(ctx: PluginContext, extraConf: Map[String, String]): Unit
  def shutdown(): Unit
}
```

但单纯的 ExecutorPlugin 只解决了进程生命周期问题——真正的 native engine 需要拦截**物理算子**的执行。这通过 Spark SQL 的扩展点实现：

```
Native Engine 的注入层次:
  1. Driver Plugin: 注册 SQL extension
     → spark.sql.extensions = com.example.NativeSqlExtension

  2. SQL Extension: 注入物理规划 Strategy
     → injectNativeStrategy(sparkSession) → NativeStrategy

  3. NativeStrategy: 匹配物理算子 → 替换为 native 版本的 Exec
     → HashAggregateExec → NativeHashAggregateExec
     → BroadcastHashJoinExec → NativeBroadcastHashJoinExec
     → ...

  4. NativeExec: 在 Executor 端通过 JNI 调用 C++ 库
     → JNI → vs::HashAggregation::compute()
     → 结果通过 Arrow 列式格式返回
```

整个注入的过程是透明的——Spark 的 Catalyst optimizer 不知道 native engine 的存在，它只看到物理计划中的 `NativeHashAggregateExec` 节点（就像看到 `HashAggregateExec` 一样）。

### 28.2 列式 Native 执行 — 从 Row-at-a-Time 到 Vector-at-a-Time

Native engine 的核心执行范式是 **Vector-at-a-Time**：

```
JVM Tungsten (WholeStageCodegen):
  for (row in batch):
    col1[row] + col2[row] → result[row]    ← 行式循环 (JIT 尝试向量化)

Native Engine (Velox/Photon):
  simd_add_avx2(col1[0..7], col2[0..7]) → result[0..7]   ← SIMD 8 个一次
  simd_add_avx2(col1[8..15], col2[8..15]) → result[8..15]
  ...
  → 每次加法用 _mm256_add_pd() (AVX2 intrinsic), 1 个 CPU 周期
```

列式内存布局让 SIMD 的使用变得自然——同一列的数据在内存中连续，一次 `_mm256_load_pd` 就能加载 4 个 double（AVX2）或 8 个 double（AVX-512）。

```
内存布局对比:
  行式 (InternalRow):  [col1[0], col2[0], col3[0], col1[1], col2[1], col3[1], ...]
    → col1 的数据不连续 → SIMD load 需要对非连续的偏移做 gather → 3-5× 慢于连续 load
  
  列式 (ColumnarBatch): [col1[0], col1[1], col1[2], ..., col1[7]]
                         [col2[0], col2[1], col2[2], ..., col2[7]]
                         [col3[0], col3[1], col3[2], ..., col3[7]]
    → 每列的数据是连续的字节流 → 一次 SIMD load 直接拉入向量寄存器
```

### 28.3 JNI 桥接 — 数据跨越 Java 与 C++ 的边界

Native engine 运行在 C++ 进程内（作为 JVM 的动态库 `.so` / `.dylib`），通过 JNI 与 Spark Executor 通信：

```
JVM Executor                           Native Engine (C++ / .so)
────────────                           ─────────────────────────
NativeHashAggregateExec.doExecute()
  │
  ├── 1. Convert ColumnarBatch → ArrowRecordBatch (in JVM)
  │      (当数据已经在 ColumnarBatch pipeline 中时, 这是零拷贝的)
  │
  ├── 2. JNI call: nativeAggregate(arrowData, aggOps, groupByKeys)
  │      → 传递 Arrow 数据的指针 + 长度
  │      → 不拷贝数据 (Arrow 数据在堆外内存中, JNI 直接访问)
  │
  │     C++ 端:
  │       ├── ArrowRecordBatch → Velox RowVector
  │       ├── HashAggregation::compute()
  │       │     ├── GroupBy hash table (C++ std::unordered_map 或 folly::F14FastMap)
  │       │     ├── Aggregate functions (sum/count/avg 用 SIMD)
  │       │     └── Output: RowVector
  │       └── RowVector → ArrowRecordBatch
  │
  ├── 3. JNI return: Arrow 结果的指针
  │
  ├── 4. ArrowRecordBatch → ColumnarBatch (在 JVM 中零拷贝包装)
  │
  └── 5. 返回 Iterator[ColumnarBatch] → 继续 Spark 的物理计划
```

**关键性能因子是 JNI 的调用频率**。如果每 100 行调用一次 JNI（batch size=100），JNI overhead 可能占 10-30%。如果每 10000 行调用一次（batch size=10000），JNI overhead < 1%。这也是为什么 native engine 倾向于配置大的 batch size——减小 JNI 往返的频率。

### 28.4 Gluten + Velox — 开源的参考实现

Gluten 是最活跃的 OSS Spark Native Engine 项目。它的架构非常清晰：

```
Driver:
  GlutenPlugin.init()
    → 注册 ColumnarRule (拦截 Physical Plan)
    → 注册 GlutenStrategy (将 Spark 物理算子转为 Gluten 算子)

Gluten 的 Plan Rewrite:
  原始计划: HashAggregate → Shuffle → HashAggregate → BroadcastHashJoin
  转换后:   NativeHashAgg → Shuffle → NativeHashAgg → NativeBHJ
            ↑ 每个算子被 Gluten 的 ColumnarExec 替换

Executor:
  NativeHashAgg.doExecuteColumnar()
    → JNIWrapper.nativeAggregate(arrowInput)
      → libvelox.so / libgluten.so 执行
```

Velox（Meta 开源）是 Gluten 最常用的 native 后端。Velox 本身是一个完整的 C++ 查询执行库，包含：
- `VeloxVector`（列式向量格式，类似 Arrow）
- `HashAggregation`，`HashJoin`，`OrderBy`，`Window`，`TableScan` 等算子
- 表达式求值引擎（`VeloxExpr`）——在 C++ 中计算 Spark Expression
- 内存管理（`VeloxMemoryPool`）——类似 Spark 的 UnifiedMemoryManager

Gluten 的双向转换路径：
```
Spark → Gluten:
  Physical Plan → SparkPlanToGlutenPlanConverter
    → GlutenPlanNode (类似 Spark PhysicalPlan 但适配 Velox API)
    
Gluten → Native:
  GlutenPlanNode → C++ Velox PlanNode
  → Velox QueryCtx → Velox Task::execute()
  
Native → Spark:
  Velox RowVector → ArrowRecordBatch → Spark ColumnarBatch
```

Gluten 还会做 **ColumnarShuffle**——将 native 算子的列式输出直接送到 Shuffle，避免"native → JVM row → JVM column → native"的转换链。ColumnarShuffle 使用 Arrow IPC 格式作为 shuffle wire format。

### 28.5 Comet — Arrow-native 的替代路径

Comet（Apache 孵化器）走了一条更"窄"但更"纯净"的路：
- 只实现 native **表达式求值** 和 **算子**，不替换整个计划
- 基于 **Apache Arrow DataFusion** 的核心库（arrow-rs / arrow-cpp）
- 纯 Apache 生态，无 Meta/Databricks 专有依赖

当一个物理算子被 Comet 替换时：
```
CometScanExec.doExecuteColumnar():
  → ParquetScan (Comet 的 native Parquet reader)
    → 直接解码 Parquet → Arrow (跳过 Spark 的 VectorizedParquetReader)
  → 列裁剪 + Filter Pushdown 在 native scan 中完成
  → 按 batch 返回 ColumnarBatch

CometNativeExec (通用 native 表达式求值):
  → 输入: ColumnarBatch
  → JNI → Comet Native Expression Evaluator
    → 在 Arrow 数组上执行 Spark Expression 的 native 翻译
  → 返回: ColumnarBatch
```

Comet 的优点：不需要重写整个物理计划——只需要把 Spark `ColumnarBatch` pipe 中的特定节替换为 native，其余部分继续由 Spark 处理。这意味着集成风险较小，可以逐步启用。

### 28.6 表达式映射 — Spark Expression → Native Expression

将 Spark 表达式翻译为 native 表达式是一个精细的过程：

```
Spark Expression                      Native Equivalent
──────────────────────────────────────────────────────────
Add(a, b)                             plus(a, b)
Cast(a, LongType)                     cast(a, INT64)
If(cond, t, f)                        ifelse(cond, t, f)
Substring(str, pos, len)              substr(str, pos, len)
Like(str, pattern)                    like(str, pattern)
Hash(exprs)                           xxhash64(exprs)

不支持 fallback 的表达式:
  → Spark 的复杂 UDF (PythonUDF, ScalaUDF) → 无法翻译 → 走 Spark fallback
  → Map/Array 的嵌套操作 → 部分支持 (取决于 native engine 的实现)
  → Decimal with precision > 38 → fallback (受限于 SIMD 寄存器的 256/512 位)
```

Expression 翻译的结果是 **fallback 机制**——不是"整个 query 走 native"，而是"能走 native 的算子走 native，不行的走 Spark"。这是从一开 始就内置的降级路径：

```scala
// Gluten 的 ColumnarRule:
def apply(plan: SparkPlan): SparkPlan = {
  val glutenPlan = tryConvertToNative(plan)
  
  // 检查哪些节点被转换:
  val nativeNodes = glutenPlan.collect { case n: NativeExec => n }
  
  // 如果 native 覆盖率高 → 使用 gluten 计划
  // 如果覆盖率低 → 回到原始 Spark 计划
  if (nativeNodes.count / allNodes.count > threshold) glutenPlan
  else plan  // fallback
}
```

### 28.7 内存管理 — 双内存池的协调

Native engine 有自己的内存管理器和 Spark 的 UnifiedMemoryManager 共享同一块物理内存，但彼此不直接通信——这造成了"两个 manager 争抢同一块内存"的风险：

```
Executor 的物理内存 (假设 8GB):
  JVM Heap (4GB):  Spark UnifiedMemoryManager (execution 2GB + storage 1GB)
  Off-Heap (2GB):  Spark Tungsten (netty + unsafe pages)
  Native Memory (2GB): Velox MemoryPool

问题: Velox 的 aggregation spilling 不知道 Spark 的内存状态
  → Velox 认为有 2GB 可用 → 实际 Spark 可能刚 GC → 物理可用 < 2GB
  → 如果 Velox 申请 2GB → OS OOM killer 触发

协调方案:
  1. Gluten 给 Velox 的 MemoryPool 设上限 (spark.gluten.memoryFraction)
  2. Velox 的 spilling 阈值设在此上限的 80%
  3. 互补: Gluten 向 Spark 的 MemoryManager 申请 off-heap execution memory
     (通过 TaskMemoryManager.allocPage) → 将此 page 交给 Velox 使用
  4. 当 Spark 回收 memory 时 → Gluten 通知 Velox 释放相应 page
```

## 关键代码片段

### 示例：GlutenPlan 的转换与 fallback

```
原始 Spark 物理计划:
  TakeOrderedAndProject
    └── HashAggregate (partial)
          └── ShuffleExchange
                └── HashAggregate (final)
                      └── BroadcastHashJoin
                            ├── Project
                            │     └── FileScan parquet
                            └── BroadcastExchange
                                  └── Project
                                        └── FileScan parquet

Gluten 转换后:
  TakeOrderedAndProject  ← [FALLBACK to Spark] 
    └── NativeHashAgg    ← gluten
          └── ColumnarShuffle ← gluten
                └── NativeHashAgg ← gluten
                      └── NativeBHJ  ← gluten
                            ├── NativeFileScan ← gluten
                            └── BroadcastExchange ← [FALLBACK to Spark]
                                  └── NativeFileScan ← gluten

原因: TakeOrderedAndProject 需要全量排序 (TopN) → Velox 不支持当前版本
      BroadcastExchange 的 broadcast 是 Spark 的 driver→executor 机制 → 保持 native 不干预
```

## 硬件视角

**SIMD 的宽度匹配**：

不是所有 CPU 都有 AVX-512。在 AWS EC2 中：
- r6i (Ice Lake) → AVX-512 → 512-bit vectors → 8 doubles/cycle
- r7i (Sapphire Rapids) → AVX-512 + AMX (matrix ops)
- r5 (Skylake) → AVX-512 disabled (Spectre mitigation)
- r6g (Graviton3) → NEON 128-bit (4×32-bit)

Native engine 需要在运行时检测 CPU capabilities 并使用对应的 SIMD path——在编译期决定的 SIMD 设置会产生 "在 AVX-512 机器上编译的 .so 在 AVX2 机器上 crash"。这就是 Gluten 使用 `libvelox.so` 的同时需要针对目标 CPU 使用 `dispatch` 机制的原因。

**Cache 局部性差异**：

native engine 的列式内存布局不仅改善了 SIMD——更重要的是 **cache 利用率**：

```
Tungsten 行式 HashAggregation:
  key = row.get(0); value = row.get(1) → 每个 row 访问跨越多个列的 offset
  → L1 cache line (64 bytes) 可能只包含 1-2 行的 key 数据
  → 大部分 cache line 里是无关列的数据 → cache pollution

Native 列式 HashAggregation:
  keyBuffer[0..7] → load into L1 → SIMD 处理 → next 8 keys
  → 所有 64 bytes 的 cache line 都是 key 数据
  → cache line 命中率接近 100%
```

在 hash aggregation 的 probe 阶段，这种差异可能导致 2-3× 的 L1 命中率差异——足以解释 native engine 3-5× 的速度优势中的大部分。

## AI 时代反思

Native Engine 与 LLM Agent 的交叉点不是"AI 生成 C++ 代码比 JVM 快"（这不是事实）。真正的交叉点是 **native engine 的性能可预测性**——LLM Agent 在进行查询规划时依赖"某操作大概花多长时间"的预测，而 GC 导致的 P99 延迟抖动使得这种预测在实践中不可靠。

Native engine 的确定性延迟（No GC pauses，可控的 memory allocation）使 LLM Agent 在做"查询预算估算"时有更高的准确率——Agent 可以说 "这个 MERGE 操作在 native engine 上花费 12±1 秒"，而不是 "在 JVM 上花费 12±20 秒"。

另一个层面的反思：native engine 的 "JNI 桥接" 在 AI 时代可能被一种更激进的架构取代——**独立的 gRPC sidecar**。Spark Connect 已经把 Client-Server 通信走 gRPC（第 26 章），如果 native engine 也作为一个 gRPC service 运行（独立于 JVM），那么"JNI overhead"就变成了"gRPC overhead"。这样做的价值是：native engine 可以独立 scale（多实例负载均衡）、独立升级（不需要 restart JVM）、独立用 GPU（GPU query engine 不适用于 JNI）。

但这是后 Spark 4.0 时代的方案，尚未有成型实现。

## 源码导航

注：Native Engine 的相关项目大部分在 Spark 主仓库之外，以下是它们在 Spark 内部和关联仓库中的集成点。

| 文件/项目 | 关键内容 | 行号参考 |
|-----------|---------|---------|
| `core/src/main/scala/org/apache/spark/internal/plugin/PluginContainer.scala` | SparkPlugin 容器，Driver/Executor Plugin 生命周期 | ~30 (PluginContainer) |
| `core/src/main/scala/org/apache/spark/api/plugin/SparkPlugin.scala` | SparkPlugin 接口定义 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/SparkStrategies.scala` | Strategy 注册，native strategy 的挂载点 | |
| Apache Gluten: `gluten-core/src/main/scala/.../GlutenPlugin.scala` | GlutenPlugin，SparkPlugin 实现，ColumnarRule 注册 | |
| Apache Gluten: `gluten-core/src/main/scala/.../ColumnarRule.scala` | ColumnarRule，Physical Plan → Gluten Plan 转换，fallback 判断 | |
| Apache Gluten: `cpp/velox/` | Gluten 的 Velox backend，JNI 入口 | |
| Meta Velox: `velox/exec/` | Velox 算子的 C++ 实现，HashAggregation, HashJoin, OrderBy 等 | |
| Comet: `native/core/src/` | Comet 的 Rust/C++ native 代码，Arrow-based 表达式求值 | |
| Comet: `spark/src/main/scala/.../CometExec.scala` | Comet 的 Spark 物理算子 (CometScanExec, CometNativeExec 等) | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/Columnar.scala` | Spark 的列式执行接口，native engine 对接的契约 | |
| `sql/core/src/main/scala/.../arrow/ArrowColumnarBatchSerializer.scala` | Arrow 序列化器，Spark ↔ Native 数据交换的基础格式 | |
