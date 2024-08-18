# 第 24 章 · 格式层与序列化加速

## 导读

- **一句话**：本章解剖 Flink 的 Format 层——从 SPI 分层到 Parquet/ORC 向量化读取，从列下推到过滤器下推，从 Avro 逐行反序列化到零拷贝路径，完整走读序列化性能关键路径上的每一个设计抉择。
- **前置知识**：第 21 章 ColumnarRowData、Parquet/ORC 文件格式基础、Java SPI 机制。
- **读完本章你能回答**：
  - Flink 的 Format SPI 长什么样——BulkFormat → DecodingFormat → BulkDecodingFormat 的分层为什么必要
  - Parquet Vectorized Reader 如何从 RowGroup 逐列批量读取并构建 ColumnarRowData batch
  - 列下推和过滤器下推分别在什么层级生效、如何配置
  - Avro/CSV/JSON 逐行格式与 Parquet/ORC 向量化格式的性能差距根源
  - 零拷贝在 Flink 序列化路径中的真实边界

---

## 24.1 — 设计动机

### 为什么需要 Format SPI 层

在 Flink 1.12 之前，Connector 和 Format 是绑定的——FileSystem Connector 只能配 CSV，Kafka Connector 只能配 JSON。Format SPI 层的设计目标是将 **"从哪里读"（Connector）和"怎么解析"（Format）彻底解耦**。

为什么这样设计？解决的核心问题是 **N:M 的组合爆炸**——N 个 Connector × M 种 Format 的全量适配不现实。放弃的替代方案是"Connector 内嵌 Format 逻辑"——虽然内嵌方案可以在特定场景下做更激进的优化（比如 Kafka + JSON 的一体化解析），但代价是代码膨胀和无法复用。

### 为什么序列化是性能关键路径

在典型 ETL 场景中，I/O 读取 + 反序列化占作业执行时间的 40%-60%。对于列式格式，如果逐行反序列化，每条记录都经过 "Column Chunk → 单值提取 → Java 对象装箱"，CPU 在对象分配和 GC 上的开销远超 I/O 本身。向量化读取通过 **批量处理整列数据**，让 CPU 在连续内存上做连续运算，将反序列化 CPU 开销降低一个数量级。这就是 `BulkFormat` 直接以 batch 为单位返回数据的原因——从 API 层面驱动实现者走向量化路径。

---

## 24.2 — 核心数据结构

### Format 接口层次

```
Format (标记接口)
├── DecodingFormat<I>               ← 读取：createRuntimeDecoder → 运行时解码器
│   └── ProjectableDecodingFormat<I> ← 扩展：支持列下推 projections
│   └── BulkDecodingFormat<T>       ← 扩展：返回 BulkFormat + 支持 applyFilters
└── EncodingFormat<I>               ← 写入：createRuntimeEncoder → 运行时编码器

BulkFormat<T, SplitT>               ← 底层：逐批读取，Source API v2 的核心接口
```

### BulkFormat

`BulkFormat` 定义在 `org.apache.flink.connector.file.src.reader.BulkFormat`（`:L96`），是 Source API v2 的底层读取接口。它不关心 Schema，只关心 Split → Reader 的映射：

```java
// <org.apache.flink.connector.file.src.reader.BulkFormat:L104>
BulkFormat.Reader<T> createReader(Configuration config, SplitT split) throws IOException;
// <org.apache.flink.connector.file.src.reader.BulkFormat:L112>
BulkFormat.Reader<T> restoreReader(Configuration config, SplitT split) throws IOException;
```

核心方法是 `Reader.readBatch()`，返回 `RecordIterator<T>`。Batch 从 I/O 线程以整批 handover 到 Mailbox 线程，比逐条传递减少线程切换开销。

为什么这样设计？BulkFormat 定位为"无 Schema 的批量读取器"——Schema 感知和投影下推交给上层 DecodingFormat，让同一个 BulkFormat 实现被不同 Table Schema 复用。

### DecodingFormat

`DecodingFormat<I>`（`<org.apache.flink.table.connector.format.DecodingFormat:L88>`）引入 Schema 感知：

```java
// <org.apache.flink.table.connector.format.DecodingFormat:L98>
I createRuntimeDecoder(DynamicTableSource.Context context, DataType physicalDataType);
```

`physicalDataType` 描述序列化记录的完整字段结构。DecodingFormat 知道"数据长什么样"，但不知道"你只需要哪些列"。

### EncodingFormat

`EncodingFormat<I>`（`<org.apache.flink.table.connector.format.EncodingFormat:L36>`）是写入侧的对称接口：

```java
// <org.apache.flink.table.connector.format.EncodingFormat:L42>
I createRuntimeEncoder(DynamicTableSink.Context context, DataType physicalDataType);
```

写入路径不需要投影和过滤下推，只需将 RowData 按格式编码输出。

### ProjectableDecodingFormat

`ProjectableDecodingFormat<I>`（`<org.apache.flink.table.connector.format.ProjectableDecodingFormat:L37>`）扩展列下推能力：

```java
// <org.apache.flink.table.connector.format.ProjectableDecodingFormat:L61>
I createRuntimeDecoder(
    DynamicTableSource.Context context, DataType physicalDataType, int[][] projections);
```

`projections` 是嵌套索引数组，例如 `[[0, 2, 1]]` 表示只取第 1 个字段的第 3 个子字段的第 2 个子字段。对于 `SELECT a, c FROM t`（50 列取 2 列），Format 在读取文件时就跳过不用的列。如果不走 ProjectableDecodingFormat，Connector 只能用 `ProjectedRowData` 在读取全量数据后再做投影，等于白读了 48 列。

### BulkDecodingFormat

`BulkDecodingFormat<T>`（`<org.apache.flink.connector.file.table.format.BulkDecodingFormat:L33>`）是 DecodingFormat 和 BulkFormat 的桥接：

```java
// <org.apache.flink.connector.file.table.format.BulkDecodingFormat:L33>
public interface BulkDecodingFormat<T> extends DecodingFormat<BulkFormat<T, FileSourceSplit>> {
    // :L36
    default void applyFilters(List<ResolvedExpression> filters) {}
}
```

它同时提供两个能力：(1) 返回 BulkFormat 作为运行时解码器；(2) 通过 `applyFilters` 接收 Planner 下推的过滤表达式。Parquet 的 `ParquetBulkDecodingFormat`（`:L144`）和 ORC 的 `OrcBulkDecodingFormat`（`:L132`）都同时实现了 `ProjectableDecodingFormat` 和 `BulkDecodingFormat`。

### FormatFactory SPI 加载机制

FormatFactory 通过 Java SPI 加载，入口在 `FactoryUtil.discoverFactory()`（`<org.apache.flink.table.factories.FactoryUtil:L529>`），底层用 `ServiceLoader.load(Factory.class, classLoader)`（`:L792`）遍历 classpath 上的 `META-INF/services/org.apache.flink.table.factories.Factory` 文件。加载流程：DDL 声明 `'format' = 'parquet'` → `FactoryUtil` 按 factoryIdentifier 匹配 `ParquetFileFormatFactory` → 调用 `createDecodingFormat()` → `FileSystemTableSource` 检测 Format 是否实现 `ProjectableDecodingFormat` / `BulkDecodingFormat`，是则分别调用投影和过滤方法。

---

## 24.3 — 关键流程走读

### 24.3.1 Parquet Vectorized Reader 完整读取流程

入口是 `ParquetVectorizedInputFormat`（`<org.apache.flink.formats.parquet.ParquetVectorizedInputFormat:L80>`）。

```
1. createReader(config, split)
   ├─ ParquetFileReader.open() → 读取 Footer → 解析 Schema + RowGroup 元数据
   ├─ clipParquetSchema() 按投影字段裁剪出 requestedSchema  (:L186)
   ├─ filterRowGroups(filter, blocks, fileSchema) → RowGroup 级过滤
   ├─ 创建 WritableColumnVector[] + VectorizedColumnBatch
   └─ 返回 ParquetReader

2. ParquetReader.readBatch()  [循环调用]
   ├─ nextBatch(batch)
   │   ├─ RowGroup 已读完 → readNextRowGroup()
   │   │   ├─ reader.readNextRowGroup() → PageReadStore
   │   │   └─ ParquetSplitReaderUtil.createColumnReader() 为每列创建 ColumnReader (:L308)
   │   ├─ 计算本批行数：min(batchSize, totalCountLoadedSoFar - rowsReturned)
   │   └─ 逐列 columnReaders[i].readToVector(num, writableVectors[i])
   │       └─ AbstractColumnReader.readToVector() (:L144)
   │           ├─ 逐 Page：pageReader.readPage()
   │           ├─ Dictionary 编码页 → 延迟解码
   │           └─ Plain 编码页 → 批量二进制拷贝
   └─ 返回 ColumnarRowIterator → ColumnarRowData.setRowId(nextRow++)
```

**延迟字典解码**：当 Page 使用字典编码时，`AbstractColumnReader` 不立即将字典 ID 解码为实际值，而是将 `ParquetDictionary` 设置到 `WritableColumnVector`（`:L176`）。后续算子按需解码——如果下游只做过滤，字典 ID 比对就够了。

**IntColumnReader 的批量读取**：以整型列为例（`<org.apache.flink.formats.parquet.vector.reader.IntColumnReader:L84>`），`readIntegers()` 一次读取 `total * 4` 字节到 ByteBuffer，通过 `setIntsFromBinary()` 批量写入 ColumnVector。**整列 4K 整数在连续内存路径上处理**，CPU Cache 命中率远高于逐行读取。

### 24.3.2 ORC Vectorized Reader 完整读取流程

入口是 `AbstractOrcFileInputFormat`（`<org.apache.flink.orc.AbstractOrcFileInputFormat:L52>`）。

```
1. createReader(config, split)
   ├─ shim.createRecordReader(conf, schema, selectedFields, conjunctPredicates, ...)
   │   └─ ORC RecordReader 内部：Stripe 定位 → 解压 → 填充 ColumnVector
   └─ 返回 OrcVectorizedReader

2. OrcVectorizedReader.readBatch()
   ├─ shim.nextBatch(orcReader, batch) → ORC 内部：Stripe → ColumnStream → 解压 → ColumnVector
   └─ OrcReaderBatch.convertAndGetIterator()
       └─ flinkColumnBatch.setNumRows(batchSize) → ColumnarRowIterator
```

核心差异：Parquet 的 ColumnReader 是 Flink 自研，ORC 直接使用 ORC 库的 RecordReader。Flink 的 ColumnVector 包装了 ORC 的 ColumnVector，**两者共享底层数组**（`<org.apache.flink.orc.OrcColumnarRowInputFormat:L131>`："no copying from the ORC column vectors to the Flink columns vectors necessary, because they point to the same data arrays internally"），完全不复制。

### 24.3.3 Avro 格式的反序列化流程

Avro 是逐行格式，通过 `AbstractAvroBulkFormat`（`<org.apache.flink.formats.avro.AbstractAvroBulkFormat:L46>`）实现 BulkFormat，但内部逐条反序列化：

```
AvroReader.readBatch()
  ├─ readNextBlock() → DataFileReader 按 Sync Marker 分 Block
  └─ AvroBlockIterator → reader.next(reuse) → GenericDatumReader 反序列化
      └─ converter.apply(avroRecord) → GenericRecord → RowData
```

GenericRecord → RowData 转换由 `AvroToRowDataConverters`（`<org.apache.flink.formats.avro.AvroToRowDataConverters:L56>`）完成。核心在 `createRowConverter()`（`:L71`），为每个字段生成类型分派的 converter：

```java
// <org.apache.flink.formats.avro.AvroToRowDataConverters:L84>
return avroObject -> {
    IndexedRecord record = (IndexedRecord) avroObject;
    GenericRowData row = new GenericRowData(arity);
    for (int i = 0; i < arity; ++i) {
        row.setField(i, fieldConverters[i].convert(record.get(i)));
    }
    return row;
};
```

唯一的优化是对象复用——`Pool<GenericRecord>` 复用 Avro 记录对象。但 GenericRowData 逐条构建，这是逐行格式无法避免的开销。

### 24.3.4 CSV/JSON 的逐行解析流程

CSV 通过 `CsvReaderFormat`（`<org.apache.flink.formats.csv.CsvReaderFormat:L74>`）实现 `SimpleStreamFormat`（不是 BulkFormat），每次只返回一条记录。底层用 Jackson `CsvMapper` + `MappingIterator` 逐行迭代。JSON 类似，通过 `JsonRowDataDeserializationSchema`（`<org.apache.flink.formats.json.JsonRowDataDeserializationSchema:L46>`）将 byte[] 解析为 JsonNode 再转 RowData。

CSV/JSON 没有列式结构，无法做列裁剪或向量化——即使只 SELECT 1 列也必须解析整行。

### 24.3.5 列下推（Projection Pushdown）在 Parquet/ORC 中的实现

**Parquet 列下推路径**：
1. Planner 确定投影列 → `int[][] projections`
2. `FileSystemTableSource` 检测 Format 是 `ProjectableDecodingFormat`，调用 `createRuntimeDecoder(context, type, projections)`（`<org.apache.flink.formats.parquet.ParquetFileFormatFactory$ParquetBulkDecodingFormat:L156>`）
3. `Projection.of(projections).project(producedDataType)` 计算投影后的 RowType
4. `clipParquetSchema()`（`<org.apache.flink.formats.parquet.ParquetVectorizedInputFormat:L186>`）裁剪 Parquet Schema，只保留投影列
5. `ParquetFileReader.setRequestedSchema()` → 只读投影列的 Column Chunk

**ORC 列下推路径**：projections → `Projection.of(projections).toTopLevelIndexes()` 转为 `selectedFields` → 传入 ORC RecordReader 只读指定列的 ColumnStream。

### 24.3.6 过滤器下推（Filter Pushdown）的实现

**Parquet 过滤器下推**：
1. `FileSystemTableSource.applyFilters()`（`<org.apache.flink.connector.file.table.FileSystemTableSource:L313>`）将表达式传递给 `BulkDecodingFormat.applyFilters(filters)`
2. Parquet Filter 通过 Hadoop Configuration 传递——`ParquetInputFormat.getFilter(conf)`
3. `filterRowGroups(filter, blocks, fileSchema)` 在 RowGroup 级别过滤

注意：Parquet 过滤器下推是 **RowGroup 级别的粗粒度过滤**——只能跳过整个 RowGroup，不能跳过 RowGroup 内的单条记录。

**ORC 过滤器下推**：
1. `OrcBulkDecodingFormat.applyFilters()`（`<org.apache.flink.orc.OrcFileFormatFactory$OrcBulkDecodingFormat:L178>`）保存过滤表达式
2. `OrcFilters.toOrcPredicate(pred)` 将 Flink 表达式转换为 ORC `SearchArgument`。`OrcFilters`（`<org.apache.flink.orc.OrcFilters:L51>`）支持 IS_NULL / EQUALS / NOT_EQUALS / GREATER_THAN / LESS_THAN / AND / OR / IN 等操作符
3. SearchArgument 传入 ORC RecordReader，在 Stripe 和 RowGroup 级别做谓词过滤

### 24.3.7 零拷贝路径的详细走读

Flink 的零拷贝是"尽可能减少不必要拷贝，用所有权转移代替物理复制"。

**Parquet 零拷贝环节**：
```
文件 → Page Cache → ParquetFileReader 解压 → ByteBuffer
  → IntColumnReader.readDataBuffer() → ByteBuffer.slice(length)  [切片，共享底层数组] (:L273)
  → WritableColumnVector.setIntsFromBinary() [批量写入]
  → ColumnarRowData 包装 VectorizedColumnBatch [仅引用，不复制]
```

**ORC 零拷贝**更彻底——Flink 的 ColumnVector 与 ORC 的 ColumnVector 共享同一个 Java 数组。

**网络传输路径**：同一 TaskManager 内，`LocalInputChannel` 实现真正零拷贝——上游 Buffer 直接被下游 InputGate 引用。跨 TaskManager 必须走网络序列化。

---

## 24.4 — 横向对比（Spark / StarRocks / MaxCompute）

### vs Spark FileFormat + ColumnarBatch

| 维度 | Flink | Spark |
|------|-------|-------|
| 格式抽象 | BulkFormat + DecodingFormat + ProjectableDecodingFormat | FileFormat + BatchRead |
| 列下推 | ProjectableDecodingFormat 接口 | buildReaderWithPartitionValues() 内部裁剪 Schema |
| 过滤下推 | BulkDecodingFormat.applyFilters() | FileFormat PushedFilters |
| Batch 结构 | VectorizedColumnBatch + ColumnarRowData | ColumnarBatch + ColumnarRow |
| Parquet Reader | 自研 AbstractColumnReader + RunLengthDecoder | 自研 VectorizedParquetRecordReader |
| ORC Reader | OrcShim 适配多版本 | OrcColumnarBatchReader 直接用 Hive ORC |

**核心差异**：Flink 将列下推和过滤下推作为 Format 接口的一部分，新增能力只需定义新接口，符合开闭原则；Spark 把所有能力一次性传入 buildReader 参数，更直接但扩展时需修改签名。

### vs StarRocks 的 Parquet/ORC Reader

| 维度 | Flink | StarRocks |
|------|-------|-----------|
| 过滤粒度 | RowGroup 级别粗过滤 | Zone Map + Dictionary Filter + Bloom Filter 多级过滤 |
| I/O 模式 | 单线程顺序读取 | 异步 Prefetch + I/O 和 CPU 流水线化 |
| 晚物化 | 延迟字典解码（单列内部） | 全面晚物化——过滤列只读字典 ID，跨列协调 |

StarRocks 的全面晚物化适合高选择性过滤场景——排除 99% 行时，只对 1% 的行解码非过滤列。Flink 的延迟字典解码只在一列内部生效。

### vs MaxCompute 的列式存储读取

| 维度 | Flink | MaxCompute |
|------|-------|-----------|
| 格式 | Parquet / ORC / Avro / CSV / JSON | 自研 Columnar（CFile） |
| 过滤下推 | RowGroup 级别 | Block + Index 级别（Bloom Filter / Min-Max） |
| 代码生成 | 无 | 运行时 CodeGen 生成专用列解析器 |

MaxCompute 的 CodeGen 为每个查询生成专用解析代码，消除虚方法调用和分支判断。Flink 选择不引入 CodeGen，保持可维护性，代价是极端性能场景不如 CodeGen 方案。

---

## 24.5 — 调优与实战陷阱

### Parquet Row Group Size 对读取性能的影响

Row Group 是向量化读取的基本调度单位。写入时设置 `parquet.block.size` = 128MB-256MB（默认 128MB）：
- 太小（< 64MB）：Row Group 多，Footer 元数据开销大，过滤下推效果差
- 太大（> 512MB）：单 Row Group 无法并行读取，内存压力大（所有列同时驻留）
- Flink 读取的 `batch-size`（`ParquetFileFormatFactory.BATCH_SIZE`，默认 2048）决定 readBatch() 返回行数，不影响 Row Group 大小

### 列下推和过滤器下推的正确配置

**陷阱 1**：FileSystem Table Source 默认支持列下推和过滤器下推，前提是 Format 实现 `ProjectableDecodingFormat` 或 `BulkDecodingFormat`。

**陷阱 2**：Avro/CSV/JSON 不支持列下推——即使 SQL 只 SELECT 1 列也读取解析所有列。宽表场景性能差距可达 10-50 倍。

**陷阱 3**：过滤器下推是 best-effort——Format 不能处理的表达式仍会在运行时二次过滤。查看 Execution Plan 确认实际下推情况。

**陷阱 4**：ORC 的 `conjunctPredicates` 只支持 AND 语义（CNF），`WHERE a = 1 OR b = 2` 不会下推到 ORC Reader。

### Avro vs Parquet 的选择决策

| 维度 | Avro | Parquet |
|------|------|---------|
| 读取模式 | 逐行反序列化 | 向量化批量读取 |
| 列下推 | 不支持 | 支持 |
| Schema 演化 | 原生支持 | Flink 当前不支持 Schema Evolution |
| 写入延迟 | 低（追加写入） | 较高（需缓冲 Row Group） |

选择建议：流式写入 + 批量读取 → 写 Avro，定期转 Parquet；纯批量 → 直接 Parquet；宽表少列查询 → 必须 Parquet。

### 序列化成为瓶颈的识别方法

1. **Source busyTimeMs**：busy time 接近 100% 且 I/O wait 低 → 反序列化是瓶颈
2. **GC 压力**：Avro/CSV/JSON 逐行解析产生大量短命对象，Young GC 每秒超 5 次需关注
3. **火焰图**：readBatch()/nextRecord() CPU 占比超 30% 且热点在 GenericDatumReader/CsvMapper/ObjectMapper → 序列化瓶颈
4. **吞吐对比**：Parquet 向量化 200-500MB/s/core vs Avro 逐行 30-80MB/s/core，低于预期先确认 Format 是否支持向量化

---

## 本章要点回顾

1. **Format SPI 分三层**——BulkFormat（底层批量读取）→ DecodingFormat（Schema 感知）→ ProjectableDecodingFormat / BulkDecodingFormat（列下推 + 过滤下推），解耦 Connector 和 Format。
2. **Parquet 向量化读取的核心**——ColumnReader 批量解压 + 延迟字典解码，整列数据在连续内存上处理。
3. **ORC 向量化读取复用 ORC 核心库**——Flink 的 ColumnVector 与 ORC 的 ColumnVector 共享底层数组，零拷贝。
4. **列下推是 Parquet/ORC 性能优势的核心**——50 列宽表只读 2 列可减少 96% I/O 和 CPU 开销，Avro/CSV/JSON 不支持。
5. **过滤器下推是 RowGroup/Stripe 级别粗粒度过滤**——不能替代运行时行级过滤，但可跳过大量不满足条件的数据块。
6. **零拷贝的真实边界**——ORC ColumnVector 共享数组是真正零拷贝；Parquet ByteBuffer.slice 是切片共享；同 TaskManager 的 LocalInputChannel 是网络层零拷贝；跨 TaskManager 必须走网络序列化。

## 源码导航

| 组件 | 全限定路径 |
|------|-----------|
| Format 基接口 | `org.apache.flink.table.connector.format.Format` |
| BulkFormat | `org.apache.flink.connector.file.src.reader.BulkFormat` |
| DecodingFormat | `org.apache.flink.table.connector.format.DecodingFormat` |
| EncodingFormat | `org.apache.flink.table.connector.format.EncodingFormat` |
| ProjectableDecodingFormat | `org.apache.flink.table.connector.format.ProjectableDecodingFormat` |
| BulkDecodingFormat | `org.apache.flink.connector.file.table.format.BulkDecodingFormat` |
| FormatFactory | `org.apache.flink.table.factories.FormatFactory` |
| SPI 加载 | `org.apache.flink.table.factories.FactoryUtil` |
| Parquet BulkFormat 入口 | `org.apache.flink.formats.parquet.ParquetVectorizedInputFormat` |
| Parquet ColumnarRow SplitReader | `org.apache.flink.formats.parquet.vector.ParquetColumnarRowSplitReader` |
| Parquet ColumnReader 抽象 | `org.apache.flink.formats.parquet.vector.reader.AbstractColumnReader` |
| Parquet IntColumnReader | `org.apache.flink.formats.parquet.vector.reader.IntColumnReader` |
| Parquet ColumnReader 工厂 | `org.apache.flink.formats.parquet.vector.ParquetSplitReaderUtil` |
| Parquet FormatFactory | `org.apache.flink.formats.parquet.ParquetFileFormatFactory` |
| ORC BulkFormat 入口 | `org.apache.flink.orc.AbstractOrcFileInputFormat` |
| ORC ColumnarRow SplitReader | `org.apache.flink.orc.OrcColumnarRowSplitReader` |
| ORC SplitReader | `org.apache.flink.orc.OrcSplitReader` |
| ORC FormatFactory | `org.apache.flink.orc.OrcFileFormatFactory` |
| ORC Filter 转换 | `org.apache.flink.orc.OrcFilters` |
| Avro BulkFormat | `org.apache.flink.formats.avro.AbstractAvroBulkFormat` |
| Avro → RowData 转换 | `org.apache.flink.formats.avro.AvroToRowDataConverters` |
| CSV ReaderFormat | `org.apache.flink.formats.csv.CsvReaderFormat` |
| JSON DeserializationSchema | `org.apache.flink.formats.json.JsonRowDataDeserializationSchema` |
| FileSystemTableSource | `org.apache.flink.connector.file.table.FileSystemTableSource` |
| ColumnarRowData | `org.apache.flink.table.data.columnar.ColumnarRowData` |
| VectorizedColumnBatch | `org.apache.flink.table.data.columnar.vector.VectorizedColumnBatch` |
