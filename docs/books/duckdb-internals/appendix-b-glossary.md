# 附录 B：DuckDB 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| Arena 分配器 | Arena Allocator | 批量分配/释放的内存管理器，Reset O(1) |
| 附加数据库 | Attached Database | 通过 ATTACH 语句挂载的数据库实例 |
| 基数估算 | Cardinality Estimation | 估算查询中间结果的行数 |
| 块 | Block | DuckDB 的 256KB 基础 I/O 单元 |
| 块管理器 | BlockManager | 管理块的分配、释放、读写 |
| 绑定 | Bind | 将 SQL 名称解析为实际对象（表、列、函数） |
| 绑定上下文 | BindContext | Binder 内部的名字解析数据结构 |
| 缓冲区管理器 | BufferManager | 管理内存中的块缓冲区，实现 Pin/Unpin |
| 缓冲池 | BufferPool | 全局共享内存管理器，实现 LRU 驱逐 |
| 列绑定 | ColumnBinding | 全局唯一的列标识（表 ID + 列索引） |
| 列裁剪 | Column Pruning | 移除查询不需要的列 |
| 列数据 | ColumnData | 列存储容器，管理 ColumnSegment 段树 |
| 列段 | ColumnSegment | 物理存储单元，压缩后的列数据 |
| 列式存储 | Columnar Storage | 每列独立存储，适合 OLAP 扫描 |
| 提交序列号 | Commit Sequence Number | 事务提交时分配的时间戳，确定可见性 |
| 常量向量 | ConstantVector | 所有元素相同值的向量 |
| 数据块 | DataChunk | 一组等长 Vector + 基数，批量执行的载体 |
| 数据表 | DataTable | 逻辑表的物理存储表示 |
| 数据跳过 | Data Skipping | 利用 Zone Map 跳过不相关数据 |
| 延迟物化 | Lazy Materialization | 延迟数据拷贝直到必须 |
| 延迟加载 | Lazy Loading | 首次访问时才从磁盘加载数据 |
| 字典向量 | DictionaryVector | 通过选择向量引用另一向量的向量 |
| 双头切换 | Dual-Header Switching | 两个 DatabaseHeader 交替写入实现崩溃安全 |
| Dual Execution | 双引擎执行 | 本地 DuckDB 与云端 MotherDuck 协同计算 |
| Hypertenancy | 超租户 | 每用户独立计算实例的多租户模型 |
| 逻辑计划 | Logical Plan | 关系代数的逻辑表达 |
| 逻辑类型 | LogicalType | SQL 层面的类型（INTEGER, VARCHAR, STRUCT 等） |
| Morsel | 数据切片 | Pipeline 中一个线程处理的数据量（一个 DataChunk） |
| Morsel-Driven | 切片驱动 | 多线程各取一个 Morsel 独立执行的并行模式 |
| 元数据块 | Metadata Block | 4KB 小块，存储目录元信息 |
| 元数据管理器 | MetadataManager | 管理元数据块的分配和读写 |
| MVCC | 多版本并发控制 | 通过版本链实现读写不阻塞 |
| 乐观写入 | Optimistic Write | 提交前数据已落盘，成功后复用 Block 指针 |
| 物理计划 | Physical Plan | 具体的执行算法选择 |
| 物理类型 | PhysicalType | 底层存储的类型（INT32, INT64, DOUBLE 等） |
| Pipeline | 执行管线 | 可线性执行的算子链 |
| Pipeline Breaker | 管线断点 | Sink 算子打断了 Pipeline 的连续性 |
| Pin | 钉住 | 将块加载到内存并增加引用计数 |
| 谓词下推 | Predicate Pushdown | 将过滤条件推到数据源附近执行 |
| 前缀范围过滤器 | PrefixRangeFilter | 利用前缀位图进行过滤下推 |
| 快照隔离 | Snapshot Isolation | 每个事务看到一致的数据快照 |
| Radix Partitioning | 基数分区 | 按哈希值高位分区数据 |
| 行组 | RowGroup | 122,880 行的固定大小数据块 |
| 行组集合 | RowGroupCollection | RowGroup 的容器 |
| 行版本管理器 | RowVersionManager | 追踪行组内的 MVCC 版本信息 |
| SALT | 盐 | Hash 表条目中的 16 位哈希前缀，用于预过滤 |
| 选择向量 | SelectionVector | 延迟物化的行索引数组 |
| 序列向量 | SequenceVector | 表示等差数列的向量 |
| Sink | 汇聚点 | Pipeline 的终点算子，消费 DataChunk |
| Source | 数据源 | Pipeline 的起点算子，产生 DataChunk |
| 存储扩展 | StorageExtension | 自定义存储后端的插件接口 |
| TableFunction | 表函数 | 返回表的函数（如 read_csv, read_parquet） |
| 事务 ID | Transaction ID | 未提交事务的标识（从 2^62 开始） |
| Undo 缓冲区 | UndoBuffer | 行级版本链的存储 |
| Unified 格式 | UnifiedVectorFormat | 统一不同向量形态的访问接口 |
| Unpin | 解钉 | 减少引用计数，可能触发驱逐 |
| 有效性掩码 | ValidityMask | NULL 位图 |
| 向量化执行 | Vectorized Execution | 一次处理一批数据（2048 行） |
| Zone Map | 区域映射 | 每个列段的 min/max 统计信息，用于数据跳过 |
