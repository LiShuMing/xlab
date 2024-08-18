# 第 20 章 · CodeGen 与运行时算子

## 导读

- **一句话**：本章回答"Flink 怎样把优化后的 Plan 编译成高性能 Java 字节码——CodeGen 的设计、Janino 编译、以及运行时关键算子的实现思路"。
- **前置知识**：第 19 章优化器。
- **读完本章你能回答**：
  - 为什么要做 CodeGen——不这样做跟直接调用函数有何差别
  - CodeGeneratorContext 如何管理生成代码片段的生命周期
  - GeneratedClass 如何封装源码与编译产物的对应关系
  - SortMergeJoin、HashAgg、Sort、Calc 各自的 CodeGen 细节
  - 流式算子 MiniBatch / TopN 的 CodeGen 特点
  - 与 Spark WholeStageCodeGen、StarRocks Pipeline、MaxCompute 的本质差异
  - Janino 编译超限和 ClassLoader 泄漏的诊断方法

---

## 20.1 — 设计动机：函数调用和虚分派的代价

数据处理中，一行 record 经过多个算子。如果每个算子是一个虚函数调用：
```
record → operatorA.eval() → operatorB.eval() → operatorC.eval() → ...
```
每个虚分派涉及两次内存访问：vtable lookup + method dispatch。100 亿行数据 → 浪费数十亿 CPU 周期。

CodeGen 的答案：**在编译时（Job提交时）将多个算子的数据流转逻辑融合到同一个 Java 方法里，避免中间的函数调用和虚分派**。

为什么这样设计——解决什么问题、放弃什么替代方案？Flink 的目标是在 JVM 上获得接近 C++ 的行处理性能。虚分派是 JVM 数据处理的核心瓶颈，手工内联不可能覆盖所有 SQL 模式。替代方案包括：(1) 运行时反射——更慢；(2) ASM 字节码操纵——学习曲线陡峭且难以调试；(3) 全局 JIT（如 GraalVM）——启动慢、与 Flink 的 ClassLoader 体系冲突。Flink 选择 Janino + 源码级 CodeGen，在可读性和性能间取得平衡。

Flink 没有像 Spark WholeStageCodeGen 那样做全局 Pipeline 融合——而是针对"热点算子内循环"做 CodeGen，并在 1.18+ 引入 Operator Fusion Codegen 作为可选增强。

---

## 20.2 — 核心数据结构

### 20.2.1 CodeGeneratorContext——生成代码的"沙盘"

`CodeGeneratorContext` 是整个 CodeGen 流程的中枢，管理所有生成代码片段的上下文、变量命名和作用域。用 Scala 实现，以可变集合维护各代码区段：

`org.apache.flink.table.planner.codegen.CodeGeneratorContext`

| 成员 | 用途 |
|------|------|
| `references: ArrayBuffer[AnyRef]` | 运行时传入生成类的外部对象引用（序列化器、UDF 实例等） |
| `reusableMemberStatements` | 生成类的成员变量声明（去重、保序） |
| `reusableInitStatements` | 构造函数中的初始化语句 |
| `reusableOpenStatements` | `open()` 方法中的语句 |
| `reusablePerRecordStatements` | 每条记录处理前的公共语句（如 input unboxing） |
| `reusableLocalVariableStatements` | 方法内局部变量声明（按方法名分区） |
| `reusableInputUnboxingExprs` | 输入字段拆箱表达式缓存，避免重复生成 |
| `nameCounter: AtomicLong` | 全局变量名计数器 |
| `parentCtx` | 父上下文，Operator Fusion 时共享命名空间 |

设计核心是"按区段收集、统一拼装"——各算子的 CodeGen 逻辑只管往 context 里塞语句片段，最终由 `OperatorCodeGenerator` 统一拼装成完整 Java 类。`parentCtx` 机制保证 Fusion Codegen 场景下多个算子共享同一个 `nameCounter`，避免变量名冲突。

代码引用：`org.apache.flink.table.planner.codegen.CodeGeneratorContext:L#55`

### 20.2.2 GeneratedClass——源码与编译产物的桥梁

`GeneratedClass<T>` 是所有生成类的统一封装，持有 Java 源码字符串和编译后的 Class 引用：

`org.apache.flink.table.runtime.generated.GeneratedClass`

关键字段：`className`（全限定名）、`code`（原始源码）、`splitCode`（经 `JavaCodeSplitter` 拆分后的源码）、`references`（运行时注入的外部引用）、`compiledClass`（编译缓存）。

编译流程的关键在 `compile()` 方法——先尝试编译 `splitCode`，失败则回退到原始 `code`。`JavaCodeSplitter` 将过长的单个方法拆成多个子方法调用，绕开 JVM 64KB 方法长度限制。

代码引用：`org.apache.flink.table.runtime.generated.GeneratedClass:L#92`

特化子类：

| 子类 | 对应接口 | 用途 |
|------|---------|------|
| `GeneratedOperator` | `StreamOperator` | 完整流算子 |
| `GeneratedJoinCondition` | `JoinCondition` | Join 条件过滤 |
| `GeneratedRecordComparator` | `RecordComparator` | 行比较器（Sort/Join key） |
| `GeneratedRecordEqualiser` | `RecordEqualiser` | 行等值比较器（Retract/Deduplicate） |
| `GeneratedNormalizedKeyComputer` | `NormalizedKeyComputer` | Sort 前缀比较键 |
| `GeneratedProjection` | `Projection` | 行投影（字段提取） |
| `GeneratedAggsHandleFunction` | `AggsHandleFunction` | 聚合函数处理器 |

### 20.2.3 NormalizedKeyComputer——Sort 的二进制前缀键

核心思想：将 RowData 的排序键编码为定长的二进制前缀，使得大部分比较可以直接在 `MemorySegment` 上按字节序完成，避免反序列化整行数据。

`org.apache.flink.table.runtime.generated.NormalizedKeyComputer`

关键方法：`putKey()`（将排序键写入 MemorySegment）、`compareKey()`（字节序比较）、`isKeyFullyDetermines()`（前缀键是否足以确定全序）、`invertKey()`（DESC 排序时反转）。

为什么需要 NormalizedKey？外部排序需要频繁比较两行大小，每次反序列化 RowData 再逐字段比较开销极大。NormalizedKey 预编码为固定长度二进制表示（INT→4B big-endian，LONG→8B，String→UTF8 前缀补零），直接在 MemorySegment 上做字节比较。`isKeyFullyDetermines()==true` 时连 RecordComparator 都不需要调用。

`SortCodeGenerator` 中 `MAX_NORMALIZED_KEY_LEN = 16`——排序键超过 16 字节时前缀键只能粗筛，精确比较仍需 RecordComparator。

代码引用：`org.apache.flink.table.planner.codegen.sort.SortCodeGenerator:L#62`

### 20.2.4 RecordComparator 与 RecordEqualiser

`RecordComparator` 实现 `Comparator<RowData>`，通过 CodeGen 避免泛型擦除的装箱拆箱，用于 Sort 和 SortMergeJoin 的 key 比对。

`RecordEqualiser` 按字段类型精确比较（Decimal 比较值非引用，Timestamp 考虑精度），主要用于 retract 消息匹配和 Deduplicate 去重。`EqualiserCodeGenerator` 为每个字段单独生成 `equalsXxx` 方法再串联调用——方法短小利于 JIT 内联，字段级短路求值提高效率。

代码引用：`org.apache.flink.table.planner.codegen.EqualiserCodeGenerator:L#51`

### 20.2.5 变量命名约定与作用域管理

`CodeGenUtils.newName()` 生成格式为 `基础名$序号` 的变量名（如 `currentKey$0`）。关键内置变量：`in1`/`in2`（左/右输入行）、`out`（输出行）、`outWriter`（输出行写入器）、`c`（Collector）、`ctx`（运行时上下文）。

`nameCounter` 使用 `AtomicLong`，子 context 通过 `parentCtx.getNameCounter` 共享祖先计数器，确保同一生成类内变量名全局唯一。

代码引用：`org.apache.flink.table.planner.codegen.CodeGenUtils:L#133`

---

## 20.3 — 关键流程走读

### 20.3.1 CodeGen 完整生成流程

从 ExecNode 到可执行算子历经六步：

```
ExecNode.translateToPlanInternal()
  → new CodeGeneratorContext(config, classLoader)       // 1. 创建上下文
  → XxxCodeGenerator.genWithKeys(ctx, ...)              // 2. 算子专属生成器
  → OperatorCodeGenerator.generateOneInputStreamOperator  // 3. 拼接完整 Java 源码
  → new GeneratedOperator(className, code, refs, conf)  // 4. 封装为 GeneratedClass
  → new CodeGenOperatorFactory(generatedOperator)        // 5. 包装为算子工厂
// 运行时：
  → GeneratedClass.compile(classLoader)                 // 6. Janino 编译 + 加载
    → JavaCodeSplitter.split() → CompileUtils.doCompile()
    → SimpleCompiler.cook() → classLoader.loadClass()
  → GeneratedClass.newInstance(classLoader)              // 7. 反射实例化
```

第 3 步的拼接是核心——`OperatorCodeGenerator` 将 `CodeGeneratorContext` 中收集的各代码区段组装为完整的算子类：构造函数注入 `references`，`open()` 执行 `reuseOpenCode`，`processElement()` 串联 `reusePerRecordCode` + `reuseLocalVariableCode` + 算子专属 `processCode`。

代码引用：`org.apache.flink.table.planner.codegen.OperatorCodeGenerator:L#72`

### 20.3.2 SortMergeJoin 的 CodeGen 详细流程

涉及多个生成器的协作：

1. **两侧 SortCodeGenerator**——`SorMergeJoinOperatorUtil` 分别为左右输入创建 `SortCodeGenerator`，生成 `NormalizedKeyComputer` + `RecordComparator` 用于排序
2. **ProjectionCodeGenerator 生成 key 投影**——从宽行中提取 join key 列为 `BinaryRowData`
3. **GeneratedJoinCondition 封装非等值条件**——`ON a.id = b.id AND a.amount > b.amount` 中的 `amount > amount` 部分，`apply()` 直接内联比较逻辑
4. **运行时 SortMergeJoinFunction.open() 统一实例化**——`keyComparator.newInstance(cl)`、`condFunc.newInstance(cl)`、`projection1.newInstance(cl)`

Inner Join 的核心 match 循环：两路排序后按 key 顺序推进游标；key 相等时遍历右侧 buffer 中所有 key 相等的行，逐条调用 `condFunc.apply()` 过滤非等值条件。这个 match 循环是 CPU 密集区，CodeGen 让比较逻辑内联在循环体内，JIT 可将整个循环优化为紧凑机器码。

代码引用：`org.apache.flink.table.planner.plan.utils.SorMergeJoinOperatorUtil:L#40`
代码引用：`org.apache.flink.table.runtime.operators.join.SortMergeJoinFunction:L#131`

### 20.3.3 HashAgg 的 CodeGen 详细流程

`HashAggCodeGenerator.genWithKeys()` 生成带分组键的聚合算子：

1. **Group Key 投影**——`ProjectionCodeGenerator` 生成从输入行提取 group key 的代码，输出 `BinaryRowData`
2. **BytesHashMap 初始化**——key 为 group key 二进制表示，value 为聚合缓冲区
3. **聚合函数 CodeGen**——`AggsHandlerCodeGenerator` 按类型走两条路径：
   - `DeclarativeAggregateFunction`（SUM/COUNT/MAX/MIN）：`DeclarativeAggCodeGen` 直接内联 `aggBuffer.setInt(0, aggBuffer.getInt(0) + input.getInt(x))`
   - `ImperativeAggregateFunction`（UDAF）：`ImperativeAggCodeGen` 生成调用 UDF `accumulate()` 的代码，保留一次方法调用
4. **Hash 查找 + 累积**——计算 group key hash → BytesHashMap 查找 → 找到则取出 accumulator 执行累积，未找到则新建 entry 初始化 accumulator
5. **OOM 回退**——BytesHashMap 内存耗尽时 fallback 到 SortAgg，通过 `BufferedKVExternalSorter` 溢写磁盘后继续
6. **输出**——`isFinal=true` 遍历 map 输出最终结果；`isFinal=false`（Local Agg）输出部分聚合结果

代码引用：`org.apache.flink.table.planner.codegen.agg.batch.HashAggCodeGenerator:L#45`

### 20.3.4 Sort 算子的 CodeGen

**NormalizedKeyComputer 生成**——`SortCodeGenerator` 根据排序键类型生成 `putKey()` 代码：INT/LONG 直接 big-endian 写入；String 取 UTF8 前缀补零；Decimal 按精度选择 compact long 或 full bytes；复合键按字段顺序依次写入，总长 ≤ 16 字节时 `isKeyFullyDetermines()=true`。

**RecordComparator 生成**——当 NormalizedKey 无法确定全序时（键长 > 16 字节或含变长字段），生成逐字段比较代码，支持 ASC/DESC 和 null 语义。

代码引用：`org.apache.flink.table.planner.codegen.sort.SortCodeGenerator:L#48`

### 20.3.5 Calc（投影+过滤）的 CodeGen

由 `CalcCodeGenerator` 驱动：条件表达式编译为布尔表达式（支持短路），投影列编译为字段提取 + 类型转换代码，`generateProcessCode()` 先判断条件，条件为 true 时执行投影并 `collect()`。

Calc 的 CodeGen 价值：投影和过滤融合在同一个 `processElement()` 方法中，避免中间 RowData 创建和虚调用。宽表 50+ 列投影时效果显著。

代码引用：`org.apache.flink.table.planner.codegen.CalcCodeGenerator:L#36`

### 20.3.6 流式算子的 CodeGen 特点

流式算子比批处理多一层复杂性——状态访问、retract 消息和时间语义。

**MiniBatch Aggregate**——Local/Global 两阶段架构，Local Agg 通过 `AggsHandlerCodeGenerator` 生成聚合函数，`MapBundleOperator` 攒批后统一处理。核心优化：将逐条状态访问改为批量状态访问，减少状态 I/O 次数。

**Deduplicate**——使用 `GeneratedRecordEqualiser` 判断两行等值，CodeGen 让等值比较在状态访问热路径上无虚分派。

**TopN/Rank**——`StreamExecRank` 使用 `GeneratedRecordComparator` 比较排序键维护 TopN 排序状态，`GeneratedRecordEqualiser` 处理 retract 场景——排名变化时需精确匹配旧记录才能发出撤回消息。

代码引用：`org.apache.flink.table.planner.plan.nodes.exec.stream.StreamExecLocalGroupAggregate:L#71`
代码引用：`org.apache.flink.table.planner.plan.nodes.exec.stream.StreamExecRank:L#32`

---

## 20.4 — 横向对比（Spark / StarRocks / MaxCompute）

### vs Spark WholeStageCodeGen

Spark WSCG 把整条 Pipeline 的多个算子坳成一个方法——从 Scan 到 Filter 到 Project 到 Agg 全部内联在一个 `processNext()` 中。

| 维度 | Flink | Spark WSCG |
|------|-------|------------|
| 融合粒度 | 单算子 CodeGen（默认）/ Operator Fusion（可选） | 全 Pipeline 融合 |
| 生成代码量 | 每算子独立，几百行 | 单方法可达数千行 |
| JIT 友好度 | 单方法短小，JIT 编译快 | 超大方法可能触发 JIT 退避 |
| 调试难度 | 按算子独立查看 | 千行代码中定位问题 |
| 跨算子优化 | 无（默认）/ Fusion Codegen 缓解 | 天然支持 |

Flink 1.18+ 的 `table.exec.operator-fusion-codegen.enabled=true` 开启算子融合，本质是 Volcano 式 produce/consume 模型——`OpFusionCodegenSpec` 定义 `doProcessProduce` / `doProcessConsume`，让相邻算子在同一个生成类中协作。

代码引用：`org.apache.flink.table.planner.plan.fusion.OpFusionCodegenSpec:L#33`

### vs StarRocks Pipeline Engine

StarRocks 用 C++ 实现，没有 CodeGen。C++ 虚分派成本远低于 Java（单次 indirect jump + inline 化概率高），C++ 模板编译期即可特化，相当于静态 CodeGen。StarRocks 通过协程调度消除线程切换开销，而非消除虚分派。

**核心洞察**：CodeGen 是 JVM 特有问题（虚分派 + 类型擦除 + 装箱）的特有解决方案。Native 引擎不需要 CodeGen，但需手动特化或模板元编程实现等价效果。

### vs MaxCompute

MaxCompute 的 Python UDF 调用链：JVM 序列化 → Py4J 桥 → Python 反序列化 → 执行 → 序列化 → Py4J 桥 → JVM 反序列化，单次跨语言开销约 10-100 微秒，是纯 Java CodeGen 的千倍以上。

| 维度 | Flink CodeGen | MaxCompute UDF |
|------|---------------|----------------|
| 调用开销 | 内联字节码，纳秒级 | 跨语言桥接，10-100 微秒 |
| 类型安全 | 编译期检查 | 运行时转换，可能失败 |
| 扩展性 | 仅 Java 生态 | 支持 Python/Java/C++ |

MaxCompute 的优化方向：内置函数走 CodeGen（C++ 后端），UDF 走进程间调用——分层策略在跨语言场景下是合理的工程折衷。

---

## 20.5 — 调优与实战陷阱

### 20.5.1 Janino 编译超限

**现象**：`Table program cannot be compiled. This is a bug.`，伴随 `Method too large` 或 `Too many constants`。

**根因**：超宽表（200+ 列）或复杂嵌套表达式导致生成代码超过 JVM 64KB 方法限制或常量池 65535 条目。

**解决**：
1. `table.generated-code.max-length=4000`（默认）——单方法拆分阈值，一般不需调整
2. `table.generated-code.max-members=10000`（默认）——类成员数阈值
3. `JavaCodeSplitter` 自动将超长方法拆成子方法调用，大多数情况自动生效

代码引用：`org.apache.flink.table.codesplit.JavaCodeSplitter:L#33`

### 20.5.2 CodeGen 导致的 ClassLoader 泄漏

**现象**：TaskManager 的 Metaspace 持续增长，最终 OOM。

**根因**：`CompileUtils` 使用 Janino `SimpleCompiler` 编译，每次编译创建新 ClassLoader。同一 SQL 反复提交（如 failover 重启）时旧 ClassLoader 可能无法 GC。

**缓解**：`COMPILED_CLASS_CACHE` 以 `(classLoaderHashCode, code)` 为 key 缓存编译产物，5 分钟过期、最大 300 条、softValues。相同 SQL 命中缓存时避免重复编译。

```java
static final Cache<ClassKey, Class<?>> COMPILED_CLASS_CACHE =
    CacheBuilder.newBuilder()
        .expireAfterAccess(Duration.ofMinutes(5))
        .maximumSize(300).softValues().build();
```

代码引用：`org.apache.flink.table.runtime.generated.CompileUtils:L#52`

### 20.5.3 Operator Fusion Codegen 调整

`table.exec.operator-fusion-codegen.enabled=true`（默认关闭）。开启后 Calc + HashAgg + HashJoin 可融合到同一个生成类，减少虚调用和中间 RowData 创建。但融合后生成类更大，可能触发编译超限。支持融合的算子：Calc、HashJoin、HashAgg、Sort、SortMergeJoin，通过 `ExecNode.supportFusionCodegen()` 判断。

代码引用：`org.apache.flink.table.planner.plan.nodes.exec.batch.BatchExecHashAggregate:L#233`

### 20.5.4 Debug CodeGen 问题

查看生成 Java 源码的方法：

1. `CompileUtils` 的 `CODE_LOG` 使用 `DEBUG` 级别输出编译类名和源码——设置 `logger.codegen.name = org.apache.flink.table.runtime.generated.CompileUtils` + `logger.codegen.level = DEBUG`
2. `OperatorCodeGenerator` 使用 `TRACE` 级别输出完整生成代码
3. Janino 编译失败时 `CompileUtils.doCompile()` 自动打印带行号源码到 stdout
4. 运行时可通过 `GeneratedClass.getCode()` 获取原始源码字符串

代码引用：`org.apache.flink.table.runtime.generated.CompileUtils:L#98`

---

## 本章要点回顾

1. **CodeGen 消除虚分派**——将热循环数据处理逻辑融合成紧凑 Java 方法，代价是编译时间和可读性损失。
2. **CodeGeneratorContext 是中枢**——按区段收集代码片段，统一拼装；`parentCtx` 支持 Fusion Codegen。
3. **GeneratedClass 封装源码和编译产物**——先 split code 编译，失败回退；编译缓存避免重复 ClassLoader。
4. **NormalizedKeyComputer 是 Sort 加速器**——二进制前缀键让大部分比较无需反序列化；16 字节限制是精度与内存的平衡。
5. **SortMergeJoin 是多生成器协作**——两侧 SortCodeGenerator + ProjectionCodeGenerator + JoinCondition。
6. **HashAgg 区分 Declarative 和 Imperative 聚合**——前者内联、后者保留方法调用；OOM 时 fallback 到 SortAgg。
7. **流式算子 CodeGen 多一层状态语义**——MiniBatch 批量状态访问、Deduplicate/TopN 依赖 RecordEqualiser 处理 retract。
8. **与 Spark WSCG 对比**——Flink 默认更保守（单算子 CodeGen），Fusion Codegen 是可选增强。
9. **与 StarRocks 对比**——C++ 虚分派成本低，CodeGen 是 JVM 特有方案。
10. **实战要点**——编译超限靠 JavaCodeSplitter 自动拆分；ClassLoader 泄漏靠编译缓存缓解；Debug 靠 DEBUG/TRACE 日志。

## 源码导航

- **CodeGeneratorContext**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/CodeGeneratorContext.scala`
- **GeneratedClass**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/generated/GeneratedClass.java`
- **CompileUtils（Janino 编译 + 缓存）**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/generated/CompileUtils.java`
- **JavaCodeSplitter（代码拆分）**：`flink-table-code-splitter/src/main/java/org/apache/flink/table/codesplit/JavaCodeSplitter.java`
- **OperatorCodeGenerator**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/OperatorCodeGenerator.scala`
- **SortCodeGenerator**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/sort/SortCodeGenerator.scala`
- **HashAggCodeGenerator**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/agg/batch/HashAggCodeGenerator.scala`
- **CalcCodeGenerator**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/CalcCodeGenerator.scala`
- **EqualiserCodeGenerator**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/EqualiserCodeGenerator.scala`
- **AggsHandlerCodeGenerator**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/agg/AggsHandlerCodeGenerator.scala`
- **SortMergeJoinFunction**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/operators/join/SortMergeJoinFunction.java`
- **SortMergeJoinOperator**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/operators/join/SortMergeJoinOperator.java`
- **SorMergeJoinOperatorUtil**：`flink-table-planner/src/main/java/org/apache/flink/table/planner/plan/utils/SorMergeJoinOperatorUtil.java`
- **NormalizedKeyComputer**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/generated/NormalizedKeyComputer.java`
- **RecordComparator**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/generated/RecordComparator.java`
- **RecordEqualiser**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/generated/RecordEqualiser.java`
- **CodeGenOperatorFactory**：`flink-table-runtime/src/main/java/org/apache/flink/table/runtime/operators/CodeGenOperatorFactory.java`
- **OpFusionCodegenSpec**：`flink-table-planner/src/main/java/org/apache/flink/table/planner/plan/fusion/OpFusionCodegenSpec.java`
- **CodeGenUtils（变量命名）**：`flink-table-planner/src/main/scala/org/apache/flink/table/planner/codegen/CodeGenUtils.scala`
- **配置项**：`flink-table-api-java/src/main/java/org/apache/flink/table/api/config/TableConfigOptions.java`（`table.generated-code.max-length/max-members`）
- **Fusion 开关**：`flink-table-api-java/src/main/java/org/apache/flink/table/api/config/ExecutionConfigOptions.java`（`table.exec.operator-fusion-codegen.enabled`）
