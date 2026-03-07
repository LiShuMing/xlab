

# Velox 与 StarRocks 核心计算引擎深度对比及优化思考

作为追求极致性能的数据库产品设计者，我们必须深入理解业界前沿计算框架的内核设计。本文旨在通过对 Facebook Velox 计算库的源码级分析，剖析其在核心算子（Operator）层面的性能优化策略，并将其与业界领先的MPP（Massively Parallel Processing）数据库 StarRocks 进行横向对比，最终为 StarRocks 的未来演进提供优化建议。

## 1. Velox 核心设计哲学与源码分析

Velox 并非一个完整的数据库，而是一个可复用的、用于构建数据计算引擎的C++组件库。其核心设计哲学是**硬件感知（Hardware-Aware）**与**执行与存储分离（Disaggregated Execution）**。它旨在最大化利用现代CPU和内存的性能，通过提供一套高效、可扩展的执行原语，赋能上层应用（如Presto、Spark）。

### 1.1. 整体架构关键点

- **向量化执行（Vectorized Execution）**: 所有数据以列式（Columnar）的`Vector`形式组织，算子以`Vector`为单位进行批处理，充分利用CPU的SIMD（Single Instruction, Multiple Data）指令集（如AVX2, AVX-512）和缓存局部性。
- **内存管理（Memory Management）**: 通过分层的`MemoryPool`进行精细化内存分配与追踪，避免了高昂的系统调用（`malloc`/`free`），减少了内存碎片，并为算子提供了内存使用超限时的回滚与溢出（Spilling）机制。
- **并发模型（Concurrency Model）**: 采用基于任务（Task）的并行模型。一个查询计划（Query Plan）被分解为多个`Task`，每个`Task`包含一段可独立执行的`Driver`流水线。这种模型非常适合多核CPU环境，能够灵活地进行任务调度和资源分配。

### 1.2. 核心算子实现与优化分析

#### 1.2.1. 聚合（Aggregate）

聚合是OLAP查询中的关键算子，通常是性能瓶颈所在。

- **实现**: Velox的核心实现是 `velox/exec/HashAggregation.cpp`。它支持单阶段（Single-stage）和两阶段（Partial/Final）聚合。
- **性能关键**:
    1.  **高效哈希表（Efficient Hash Table）**: Velox大量借鉴了Folly库中的`F14Vector`等高性能容器。哈希表的设计直接决定了聚合性能。它采用线性探测（Linear Probing）法解决哈-希冲突，并通过向量化技术（如`velox/common/base/VeloxHasher.h`）一次性计算一批key的哈希值，极大提升了CPU效率。
    2.  **智能布局（Intelligent Layout）**: 对于聚合状态（Aggregation State），Velox会将其与`group key`紧凑存储，提升缓存命中率。对于不同类型的key（定长、变长），它有不同的存储策略以优化内存访问。
    3.  **内存溢出（Spilling）**: 当哈希表大小超过`MemoryPool`限制时，Velox能智能地将部分分区（Partitions）的数据溢出到磁盘，待其他分区处理完毕后，再读回溢出的数据进行处理，保证了高基数（High-Cardinality）聚合的稳定性。
- **调度策略**:
    - **串行/并发**: 在一个`Task`内部，聚合算子串行处理输入的`Vector`。并发通过将数据分片（Split）后启动多个并行的`Task`来实现，每个`Task`执行部分聚合（Partial Aggregation），最后由一个`Task`完成最终聚合（Final Aggregation）。
    - **分布式**: 分布式场景与并发场景类似，遵循经典的`Map-Reduce`模式。各个节点分别完成本地数据的部分聚合，然后通过网络Shuffle（洗牌）将相同key的数据汇集到单一节点进行最终聚合。Velox的设计完美支持这种两阶段聚合模式。

#### 1.2.2. 连接（Join）

- **实现**: 主力实现是 `velox/exec/HashJoin.cpp`。同样，`Build`端构建哈希表，`Probe`端进行探测。
- **性能关键**:
    1.  **并行构建与探测（Parallel Build & Probe）**: Velox通过对`Build`和`Probe`两端的数据基于`Join Key`进行分区，可以将一个大的Join任务分解为多个独立的、可以并行执行的小Join任务，这是发挥多核性能的关键。
    2.  **向量化探测（Vectorized Probing）**: 在`Probe`阶段，一次性对一批`Key`进行探测，并利用SIMD指令进行`Key`的比较，减少`branch misprediction`（分支预测失败）的开销。
    3.  **哈希表优化**: 与`Aggregate`类似，`Join`的性能也高度依赖于哈希表的效率。Velox的哈希表实现能够处理复杂的`Join Key`（例如，组合键）。
- **调度策略**:
    - **串行/并发**: 在`Task`内，`Build`阶段完成后，`Probe`阶段开始。并发通过分区实现，多个`Task`可以并行地对自己分区内的数据执行`HashJoin`。
    - **分布式**: 分布式`Join`通常采用`Shuffle Join`或`Broadcast Join`。
        - `Shuffle Join`: 将`Build`和`Probe`两端的数据都按`Join Key`进行`Hash`分区，发送到不同节点，各节点独立完成自己分区的`Join`。
        - `Broadcast Join`: 当`Build`端数据较小时，将其广播（Broadcast）到所有处理`Probe`端数据的节点，每个节点用完整的`Build`表与部分的`Probe`表进行`Join`，避免了`Probe`端的网络`Shuffle`。Velox的`HashJoin`算子本身不决定调度，但其分区能力为上层调度器（如Presto）实现这些策略提供了基础。

#### 1.2.3. 排序（Sort）

- **实现**: `velox/exec/OrderBy.cpp`。当数据能完全放入内存时，执行内存排序；否则，执行外部排序（External Sorting）。
- **性能关键**:
    1.  **TopN优化**: 对于`ORDER BY ... LIMIT N`的场景，Velox会使用`TopN`算子，维护一个大小为N的堆（Heap），避免对全量数据进行排序，极大提升了性能。
    2.  **并行外排（Parallel External Sort）**: 当需要外部排序时，Velox会将数据分区，每个分区由一个`Task`独立进行内存排序并写出到磁盘。最后，通过一个多路归并（Multi-way Merge）的`Task`将所有有序的临时文件合并成最终的有序输出。
    3.  **数据结构**: 排序过程中，Velox并非直接移动`Row`，而是对一个包含行号的指针数组进行排序，减少了数据移动的开销。

#### 1.2.4. 窗口函数（Window）

- **实现**: `velox/exec/Window.cpp`。这是最复杂的算子之一。
- **性能关键**:
    1.  **分区与排序（Partitioning and Sorting）**: `Window`算子的第一步是对数据按`PARTITION BY`的`Key`进行分区，然后对每个分区内的数据按`ORDER BY`的`Key`进行排序。此处的性能依赖于`Hash`分区和`Sort`算子的效率。
    2.  **帧计算（Frame Calculation）**: 在排好序的分区上，`Window`算子会移动一个计算“帧”（Frame），根据`ROWS`或`RANGE`定义，对帧内的数据执行聚合或计算。Velox对这个过程进行了向量化，一次性计算一批行的窗口函数结果。
- **调度策略**: 并发主要通过对`PARTITION BY`的`Key`进行`Hash`分区，将不同的分区交给不同的`Task`独立处理来实现。如果某个分区数据量极大，该分区本身可能成为瓶颈。

## 2. 与 StarRocks 对比分析

StarRocks作为一个完整的MPP数据库，其优化是端到端（End-to-End）的，而Velox专注于执行层。

### 2.1. 架构与执行模型

- **StarRocks**: 采用经典的MPP架构，优化器生成分布式执行计划，数据在节点间的流水线（Pipeline）中流动。其向量化引擎是自研的，与Velox在思路上相似，但在实现上是与自身存储、调度、元数据管理紧密集成的。
- **Velox**: 是一个库，更加灵活和解耦。它可以被集成到不同的系统中，实现计算的“可移植性”。

### 2.2. 优劣势对比

| 特性 | Velox (作为库) | StarRocks (作为系统) |
| :--- | :--- | :--- |
| **优势** | **1. 极致解耦与复用**: 专注于计算，可被多种引擎（Presto, Spark）复用，避免重复造轮子。<br>**2. 硬件感知前沿**: 紧跟硬件发展，能快速集成Folly等库中的最新数据结构与算法。<br>**3. 社区生态**: 开放的生态吸引了众多公司贡献，技术迭代快。 | **1. 端到端优化**: 优化器、执行器、存储层协同工作。例如，能够实现高效的Runtime Filter（运行时过滤器），在Join的Build端生成Filter，下推到Probe端的Scan节点，极大减少扫描数据量。这是Velox库本身无法做到的。<br>**2. CBO优化器**: 拥有成熟的基于成本的优化器（Cost-Based Optimizer），能根据数据统计信息生成更优的执行计划（如Join Order选择）。<br>**3. 存储集成**: 自有的列式存储格式（Colocate Table, Tablet）和索引结构（前缀索引）为上层计算提供了强力支持。 |
| **劣势** | **1. 缺乏系统级视图**: 作为一个库，它无法进行全局的资源调度和跨算子的协同优化（如Runtime Filter）。<br>**2. 集成成本**: 需要上层系统（如Presto）进行封装和调度，才能发挥其价值。 | **1. 相对封闭的体系**: 核心组件自成一体，与外部大数据生态（如Spark）的深度融合不如Velox + Gluten方案来得直接。<br>**2. 技术迭代可能受限于自身**: 某些底层数据结构或算法的演进速度可能不如Folly等专注基础库的社区。 |

### 2.3. 针对StarRocks的优化建议

基于对Velox的分析，StarRocks可以从以下几个方面思考演进方向：

1.  **执行层抽象与解耦**:
    - **建议**: 借鉴Velox的思路，逐步将StarRocks的执行层（算子实现）抽象成一个更为独立的“内核”或“库”。这并非要完全替换，而是进行内部重构。
    - **收益**:
        - **灵活性**: 一个解耦的执行内核可以更容易地被用于不同场景，例如，未来可以探索将StarRocks的计算能力嵌入到Spark（类似Spark-connector但更深度），或用于流处理场景。
        - **加速开发与测试**: 独立的执行层可以进行更专注的性能测试和单元测试，加速新算子和新函数的开发。

2.  **拥抱更前沿的基础库**:
    - **建议**: 评估并引入业界顶尖的C++基础库，如Folly。例如，考察使用`F14`哈希容器替换或增强现有的哈希表实现，以获得在`Aggregate`和`Join`等关键算子上的性能提升。
    - **收益**: 直接受益于外部社区在底层算法上的持续投入和优化，减少内部的维护成本，同时保持技术领先。

3.  **探索更动态的任务调度模型**:
    - **建议**: StarRocks目前的Pipeline模型非常成熟，但在某些复杂查询场景下（如包含多个高基数Join和Aggregate），可以探索借鉴Velox的动态任务（Task-based）调度模型。允许在运行时根据算子的中间数据大小和CPU的繁忙程度，动态地调整并行度或拆分/合并任务。
    - **收益**: 在混合负载场景下实现更精细化的资源管理和更高的CPU利用率，尤其是在NUMA（Non-Uniform Memory Access）架构下，实现亲和性调度。

4.  **强化硬件感知的算子内核**:
    - **建议**: 建立一个更清晰的硬件加速抽象层。除了SIMD，还可以为未来的新硬件（如CXL内存、DPU/IPU）预留接口。允许为特定算子（如Scan, Sort）开发针对特定硬件的内核（Kernel），并在运行时动态加载。
    - **收益**: 保持对前沿硬件的快速适应能力，构建面向未来的“软件定义硬件”计算引擎，持续巩固性能优势。

## 3. 结论

Velox和StarRocks代表了现代高性能数据计算的两种成功范式。Velox以其极致的解耦、硬件感知和开放性，成为了构建下一代计算引擎的基石。StarRocks则以其端到端的整合优化、成熟的MPP架构和强大的CBO，在OLAP数据库领域取得了卓越的性能表现。

对于StarRocks而言，其未来的演进之路，可以在保持自身一体化优势的同时，适度吸收Velox在**“组件化”、“拥抱开源社区”和“动态任务调度”**方面的设计哲学，通过内部的重构与抽象，打造一个既能端到端优化、又具备高度灵活性和前沿性的世界级计算引擎。


> 结合源码，并生成一个markdown文件，深入分析调研如下实现：
> 1. Vector/Column 如何高效地保存各种column类型，以Binary/FixedLength为例，同时有哪些创新点，如何实现LazyColumn、字典编码等等；
> 2. Velox HashJoin/HashAggregate实现原理，及其实现高性能Tips；



# Velox 核心实现深度分析：Vector、Join与Aggregate

本文旨在深入剖析Velox内部的核心数据结构与算法实现。我们将首先探讨`Vector`/`Column`如何高效地组织和表达数据，特别是其对复杂类型、延迟加载和字典编码的实现。随后，我们将深入分析`HashJoin`和`HashAggregate`这两个关键算子的实现原理及其内部蕴含的高性能优化技巧。

## 1. Vector/Column: Velox的数据表示基石

在Velox中，所有数据都以`velox::Vector`的形式进行批处理。`Vector`是一个抽象基类，其具体实现（`FlatVector`, `DictionaryVector`等）针对不同数据特性进行了深度优化。

### 1.1. Vector 的通用结构

所有`Vector`都共享一个基础结构，定义在 `velox/vector/BaseVector.h`：

- `type_`: `TypePtr`，描述该`Vector`的数据类型（如`BIGINT`, `VARCHAR`）。
- `length_`: `vector_size_t`，表示`Vector`中逻辑元素的数量。
- `nulls_`: `BufferPtr`，指向一个位图（Bitmap），用于高效地标记哪些行是`NULL`。将`NULL`信息与数据本身分离是列式引擎的通用优化。
- `rawNulls_`: `const uint64_t*`，是`nulls_`缓冲区的原始指针，用于快速访问。

### 1.2. 定长类型 (Fixed-Length) 的实现: `FlatVector<T>`

对于`INTEGER`, `BIGINT`, `DOUBLE`等定长类型，Velox使用`FlatVector<T>`（定义于`velox/vector/FlatVector.h`）来存储，这是最高效的存储方式。

- **核心实现**:
    - `values_`: 一个`BufferPtr`，指向一块连续的内存区域，直接存储了`T`类型的数据。
    - `rawValues_`: `const T*`，是`values_`缓冲区的原始指针。

- **高效原因**:
    - **内存连续**: 数据紧密排列，无任何额外开销。
    - **随机访问**: 通过`rawValues_[i]`即可实现`O(1)`时间复杂度的随机访问。
    - **SIMD友好**: 连续的内存布局是利用SIMD指令进行向量化计算的完美前提。

```cpp
// Example: A FlatVector<int64_t> for 4 rows: [10, 20, NULL, 40]
// rawValues_ -> | 10 | 20 | (undefined) | 40 |
// rawNulls_  -> a bitmap where the 3rd bit is set to 1 (true)
```

### 1.3. 变长类型 (Variable-Length) 的实现: `FlatVector<StringView>`

对于`VARCHAR`, `VARBINARY`等变长类型，Velox同样使用`FlatVector`，但模板参数是`StringView`。`StringView`是一个不持有数据所有权、指向字符串的轻量级结构（指针+长度）。

- **核心实现**:
    - `values_`: `BufferPtr`，指向一个`StringView`对象的连续数组。
    - `stringBuffers_`: `std::vector<BufferPtr>`，一个`Buffer`的向量，真正存储UTF-8字符串数据的地方。`values_`数组中的`StringView`对象会指向这些`Buffer`中的某个位置。

- **高效原因与权衡**:
    - **数据与元信息分离**: `StringView`数组（元信息）是定长的，便于快速遍历和定位。实际的字符串数据则被集中存放在`stringBuffers_`中。
    - **减少内存碎片**: 通过将多个小字符串打包到大的`Buffer`中，减少了因大量小内存分配而产生的碎片和开销。
    - **开销**: 相比定长类型，访问变长数据需要一次额外的指针解引用（`values_[i].data()`），这会带来轻微的性能开销（可能导致Cache Miss），但这是处理变长数据的标准且高效的方式。

```cpp
// Example: A FlatVector<StringView> for 2 rows: ["hello", "velox"]
// values_ -> | {ptr_A, 5} | {ptr_B, 5} |
// stringBuffers_ -> Buffer1 -> "hellovelox..."
//                     ^      ^
//                     ptr_A  ptr_B
```

### 1.4. 创新与特殊Vector实现

Velox的强大之处在于其丰富的`Vector`实现，可以根据数据特性选择最优的压缩和表达方式。

#### 1.4.1. 延迟加载: `LazyVector`

- **目的**: 在查询执行过程中，并非所有列都会被访问（例如`SELECT a FROM t`，列`b`, `c`就不需要）。`LazyVector`实现了列的延迟物化（Lazy Materialization），只有当该列数据被实际访问时，才触发真正的加载。
- **实现原理** (`velox/vector/LazyVector.h`):
    1. `LazyVector`内部持有一个加载函数`load_` (类型为`std::function<void()>`)和一个`loadedVector_`（`BaseVectorPtr`，初始为`nullptr`）。
    2. 当任何代码首次尝试访问`LazyVector`的数据时（通过调用`loadedVector()`方法），会检查`loadedVector_`是否为空。
    3. 如果为空，则执行`load_`函数。这个函数负责从数据源（如Parquet/ORC文件）读取数据，并创建一个具体的`Vector`（如`FlatVector`），然后将`loadedVector_`指向它。
    4. 所有后续的访问都将直接转发到这个已经加载的`loadedVector_`上。
- **创新点**: 将数据加载的控制权交给了执行引擎，完美适配了列式存储的投影下推（Projection Pushdown）优化，避免了不必要的I/O和反序列化开销。

#### 1.4.2. 字典编码: `DictionaryVector`

- **目的**: 对于低基数（Low-Cardinality）的列（如“国家”列），存在大量重复值。字典编码通过只存储一份唯一值，并用整数索引来表示原数据，从而大幅压缩数据。
- **实现原理** (`velox/vector/DictionaryVector.h`):
    1. `dictionary_`: 一个`BaseVectorPtr`，指向存储了所有唯一值的`Vector`（字典本身）。
    2. `indices_`: 一个`BufferPtr`，指向一个整数数组，其长度与`DictionaryVector`的逻辑长度相同。
- **创新点**:
    - **计算加速**: 许多操作（如`Filter`, `Aggregate`）可以直接在`indices_`这个整数数组上进行，比较整数远快于比较字符串，极大地提升了计算性能。
    - **嵌套能力**: `dictionary_`本身可以是另一个`DictionaryVector`，允许多层嵌套的字典编码。
    - **与`LazyVector`结合**: 字典本身也可以是延迟加载的。

## 2. HashJoin 与 HashAggregate 实现原理及性能优化

这两个算子是OLAP查询的性能核心，Velox对其进行了深度优化。它们都依赖于一个高度优化的内部哈希表实现。

### 2.1. 核心组件: `velox/exec/HashTable.h`

Velox的哈希表是其高性能的关键。它借鉴了Folly `F14`的设计思想：

- **分块与元数据分离**: 哈希表内存被划分为块，每个块包含用于快速探测的元数据（部分哈希值）和指向实际数据的槽位。
- **SIMD探测**: 使用SIMD指令并行比较元数据，一次性检查多个槽位，大幅减少分支和比较指令。
- **高负载因子**: 可以在内存占用率很高的情况下依然保持高性能。

### 2.2. HashAggregate 实现原理

- **源码**: `velox/exec/HashAggregation.cpp`
- **流程**:
    1.  **输入**: 一批`Vector`。
    2.  **哈希计算**: 对`GROUP BY`的`Key`列进行向量化哈希计算（`VeloxHasher::hash`），得到一批哈希值。
    3.  **查找/插入**: 遍历每一行，使用哈希值在`HashTable`中查找。
        - **命中**: 如果找到了匹配的`Key`，则定位到该`Key`对应的聚合状态（Accumulator），并调用更新函数（如`sum += value`）。
        - **未命中**: 在`HashTable`中为这个新的`Key`分配一个槽位，并初始化聚合状态。
    4.  **输出**: 当所有输入处理完毕，遍历`HashTable`中的所有条目，生成结果`Vector`。

- **高性能Tips**:
    1.  **向量化哈希**: `VeloxHasher`被设计为一次性处理一整列`Key`，而非逐行计算，充分利用SIMD。
    2.  **聚合状态管理**: 累加器（Accumulator）的内存布局经过精心设计。对于简单的聚合（如`SUM(BIGINT)`），其状态可以直接内联在哈希表行中。对于复杂状态（如`APPROX_DISTINCT`的HyperLogLog对象），则存储指针。
    3.  **并行化**: 通过对`Key`进行分区，可以将聚合任务分发到多个线程，每个线程构建自己的`HashTable`（部分聚合）。最后由一个阶段将所有线程的结果合并（最终聚合）。
    4.  **内存溢出(Spilling)**: 当`HashTable`内存占用超出预算时，Velox能智能地选择一部分分区的数据写入磁盘，待处理完内存中的分区后，再读回磁盘上的数据继续处理。

### 2.3. HashJoin 实现原理

- **源码**: `velox/exec/HashJoin.cpp`
- **流程**:
    1.  **Build Phase (构建阶段)**:
        - 选择`Join`中较小的一侧作为`Build`侧。
        - 流式读取`Build`侧的所有数据，对`Join Key`进行哈希计算。
        - 将`Key`和需要输出的`Payload`列存入`HashTable`。
    2.  **Probe Phase (探测阶段)**:
        - 流式读取`Probe`侧的数据，同样对`Join Key`进行哈希计算。
        - 在`HashTable`中查找该哈希值。
        - 如果哈希匹配，则进一步精确比较`Join Key`是否完全相等。
        - 如果`Key`相等，则将`Probe`侧的行与`HashTable`中存储的`Build`侧的行拼接起来，生成输出结果。

- **高性能Tips**:
    1.  **并行Join**: 与`Aggregate`类似，通过对`Join Key`进行分区，`Build`和`Probe`阶段都可以在多个线程上并行执行。每个线程处理一个分区，构建和探测自己独立的`HashTable`。
    2.  **高效的Key打包**: 对于多列`Join Key`（`ON t1.a = t2.a AND t1.b = t2.b`），Velox会将多个`Key`列的数据打包（Pack）成一个连续的内存块作为哈希表的`Key`，这比逐列比较更高效。
    3.  **Runtime Filter (运行时过滤器)**: 虽然Velox本身作为库不直接实现，但其架构支持上层引擎（如Presto）实现此优化。即在`Build`阶段结束后，根据`Build`侧`Key`的范围或集合生成一个过滤器（如Bloom Filter），并将其下推到`Probe`侧的扫描节点，提前过滤掉不可能`Join`成功的数据。
    4.  **内存管理**: `Join`的`HashTable`同样受`MemoryPool`管理，并支持`Spilling`，保证了大数据量`Join`的稳定性。

### 结论

Velox通过其富有表现力且高度优化的`Vector`系统，为上层算子提供了坚实的数据基础。其`LazyVector`和`DictionaryVector`等设计，体现了在数据表示层面追求极致效率的哲学。而在`HashJoin`和`HashAggregate`等核心算子中，Velox将向量化计算、SIMD指令、硬件感知的数据结构（如`F14`思想的哈希表）以及精细的内存管理和并行策略深度融合，从而实现了业界顶尖的计算性能。

>  结合源码，并生成一个markdown文件，深入分析调研如下实现：
> 1. 介绍Velox的pipeline调度逻辑，支持动态调整Dop吗？
> 2. 如何做到在Aggregate/Join算子，并行多个线程计算的？这个设计同pipeline调度如何结合的？如何进行并发资源控制