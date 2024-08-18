# 附录 A：源码导航索引

> DuckDB 的源码有超过 100 万行，分布在十几个顶级目录中。本索引按模块组织关键文件，帮助读者快速定位。

## 核心入口

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/main/database.hpp` | DatabaseInstance — 全局数据库实例 |
| `src/include/duckdb/main/connection.hpp` | Connection — 客户端连接 |
| `src/include/duckdb/main/client_context.hpp` | ClientContext — 查询执行上下文 |
| `src/main/database.cpp` | 数据库初始化、配置、关闭 |
| `src/main/connection.cpp` | 连接管理、查询提交 |

## 类型系统

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/common/types.hpp` | LogicalType / PhysicalType 定义 |
| `src/include/duckdb/common/types/vector.hpp` | Vector — 列式计算的原子单元 |
| `src/include/duckdb/common/types/data_chunk.hpp` | DataChunk — 批量执行的载体 |
| `src/include/duckdb/common/types/value.hpp` | Value — 单个值的容器 |
| `src/include/duckdb/common/types/selection_vector.hpp` | SelectionVector — 延迟物化 |
| `src/include/duckdb/common/types/validity_mask.hpp` | ValidityMask — NULL 位图 |
| `src/include/duckdb/common/types/string_type.hpp` | string_t — 字符串值类型 |
| `src/include/duckdb/common/types/hugeint.hpp` | hugeint_t — 128 位整数 |

## Parser

| 文件 | 说明 |
|------|------|
| `src/parser/transform/` | PG AST → DuckDB AST 转换 |
| `src/include/duckdb/parser/parsed_data/` | 解析后的语句数据结构 |
| `src/include/duckdb/parser/sql_statement.hpp` | SQLStatement 基类 |
| `src/include/duckdb/parser/expression/` | 表达式节点体系 |
| `src/include/duckdb/parser/tableref/` | 表引用节点体系 |
| `src/include/duckdb/parser/constraints/` | 约束定义 |
| `src/include/duckdb/parser/parsed_expression_iterator.hpp` | AST 遍历工具 |

## Binder

| 文件 | 说明 |
|------|------|
| `src/planner/binder/` | Binder 主目录 |
| `src/planner/binder/tableref/` | 表引用绑定 |
| `src/planner/binder/expression/` | 表达式绑定 |
| `src/include/duckdb/planner/binder.hpp` | Binder 类定义 |
| `src/include/duckdb/planner/bind_context.hpp` | BindContext — 名字解析 |

## Planner

| 文件 | 说明 |
|------|------|
| `src/planner/` | 逻辑计划生成 |
| `src/include/duckdb/planner/logical_operator.hpp` | LogicalOperator — 50+ 种逻辑算子 |
| `src/include/duckdb/planner/logical_operator/` | 各逻辑算子定义 |
| `src/include/duckdb/planner/expression.hpp` | Expression 基类 |
| `src/include/duckdb/planner/expression/` | 各表达式类型 |
| `src/include/duckdb/planner/column_binding.hpp` | ColumnBinding — 列标识 |

## Optimizer

| 文件 | 说明 |
|------|------|
| `src/optimizer/` | 优化规则实现 |
| `src/include/duckdb/optimizer/optimizer.hpp` | Optimizer 框架 |
| `src/optimizer/filter_pushdown.cpp` | 谓词下推 |
| `src/optimizer/remove_unused_columns.cpp` | 列裁剪 |
| `src/optimizer/common_subexpression.cpp` | 公共子表达式消除 |
| `src/optimizer/join_order/` | Join 排序优化 |
| `src/optimizer/statistics_propagator.cpp` | 统计信息传播 |
| `src/include/duckdb/optimizer/matcher/` | 规则匹配引擎 |

## Execution

| 文件 | 说明 |
|------|------|
| `src/execution/` | 物理执行实现 |
| `src/include/duckdb/execution/physical_operator.hpp` | PhysicalOperator — 60+ 种物理算子 |
| `src/execution/operator/scan/` | 扫描算子 |
| `src/execution/operator/join/` | Join 算子 |
| `src/execution/operator/aggregate/` | 聚合算子 |
| `src/execution/operator/filter/` | 过滤算子 |
| `src/execution/operator/order/` | 排序算子 |
| `src/execution/expression_executor.cpp` | 表达式执行器 |
| `src/execution/physical_plan/` | 物理计划生成 |

## Parallel / Pipeline

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/parallel/pipeline.hpp` | Pipeline 定义 |
| `src/include/duckdb/parallel/pipeline_executor.hpp` | Pipeline 执行器 |
| `src/include/duckdb/parallel/task_scheduler.hpp` | 任务调度器 |
| `src/include/duckdb/parallel/meta_pipeline.hpp` | MetaPipeline — Pipeline DAG |
| `src/include/duckdb/parallel/event.hpp` | PipelineEvent — 事件驱动调度 |

## Storage

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/storage/storage_manager.hpp` | StorageManager — 全局存储入口 |
| `src/include/duckdb/storage/block.hpp` | Block / BlockPointer |
| `src/include/duckdb/storage/block_manager.hpp` | BlockManager 抽象 |
| `src/include/duckdb/storage/single_file_block_manager.hpp` | 单文件 BlockManager |
| `src/include/duckdb/storage/buffer_manager.hpp` | BufferManager 抽象 |
| `src/include/duckdb/storage/standard_buffer_manager.hpp` | 标准缓冲区管理器 |
| `src/include/duckdb/storage/buffer/buffer_pool.hpp` | BufferPool — 全局内存仲裁 |
| `src/include/duckdb/storage/data_table.hpp` | DataTable — 逻辑表 |
| `src/include/duckdb/storage/table/row_group.hpp` | RowGroup — 固定大小数据块 |
| `src/include/duckdb/storage/table/column_data.hpp` | ColumnData — 列存储容器 |
| `src/include/duckdb/storage/table/column_segment.hpp` | ColumnSegment — 物理存储单元 |
| `src/include/duckdb/storage/table/column_data_checkpointer.hpp` | 列数据 Checkpointer |
| `src/include/duckdb/storage/storage_info.hpp` | 存储常量（Block大小、RowGroup大小等） |
| `src/include/duckdb/storage/write_ahead_log.hpp` | WAL |
| `src/include/duckdb/storage/checkpoint_manager.hpp` | CheckpointManager |

## Compression

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/function/compression_function.hpp` | CompressionFunction 框架 |
| `src/function/compression_config.cpp` | 压缩算法注册 |
| `src/storage/compression/bitpacking.cpp` | BitPacking 压缩 |
| `src/storage/compression/rle.cpp` | RLE 压缩 |
| `src/storage/compression/dictionary/` | Dictionary 压缩 |
| `src/storage/compression/dict_fsst/` | DictFSST 压缩 |
| `src/storage/compression/alp/` | ALP 浮点压缩 |
| `src/storage/compression/alprd/` | ALP-RD 浮点压缩 |
| `src/storage/compression/roaring/` | Roaring 有效性掩码压缩 |
| `src/storage/compression/zstd.cpp` | ZSTD 长字符串压缩 |

## Transaction

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/transaction/transaction.hpp` | Transaction 基类 |
| `src/include/duckdb/transaction/duck_transaction.hpp` | DuckTransaction — 具体实现 |
| `src/include/duckdb/transaction/duck_transaction_manager.hpp` | 事务管理器 |
| `src/include/duckdb/transaction/meta_transaction.hpp` | 跨数据库事务协调 |
| `src/include/duckdb/transaction/undo_buffer.hpp` | UndoBuffer — 行级版本链 |
| `src/include/duckdb/transaction/update_info.hpp` | UpdateInfo — 更新版本链节点 |
| `src/include/duckdb/transaction/delete_info.hpp` | DeleteInfo — 删除追踪 |
| `src/include/duckdb/transaction/append_info.hpp` | AppendInfo — 追加追踪 |
| `src/include/duckdb/transaction/local_storage.hpp` | LocalStorage — 事务私有缓冲 |

## Index

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/execution/index/art/art.hpp` | ART 索引 |
| `src/include/duckdb/execution/index/art/node.hpp` | ART 节点类型 |
| `src/include/duckdb/execution/index/art/art_key.hpp` | 基数编码键 |
| `src/include/duckdb/execution/index/bound_index.hpp` | BoundIndex 抽象 |
| `src/include/duckdb/storage/index.hpp` | Index 基类 |
| `src/include/duckdb/storage/statistics/base_statistics.hpp` | BaseStatistics — Zone Map |

## Function

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/function/function.hpp` | 函数基类 |
| `src/include/duckdb/function/scalar_function.hpp` | 标量函数 |
| `src/include/duckdb/function/aggregate_function.hpp` | 聚合函数 |
| `src/include/duckdb/function/table_function.hpp` | 表函数 |
| `src/function/` | 内置函数实现 |

## Extension

| 文件 | 说明 |
|------|------|
| `src/include/duckdb/main/extension.hpp` | Extension 定义 |
| `src/main/extension/extension_load.cpp` | 扩展加载逻辑 |
| `src/include/duckdb/main/extension/extension_loader.hpp` | C++ 扩展注册接口 |
| `src/include/duckdb_extension.h` | C API 扩展头文件 |
| `extension/parquet/` | Parquet 扩展 |
| `extension/json/` | JSON 扩展 |
| `extension/delta/` | Delta Lake 扩展 |
| `extension/icu/` | ICU 国际化扩展 |

## C API

| 文件 | 说明 |
|------|------|
| `src/include/duckdb.h` | C API 主头文件 |
| `src/main/capi/` | C API 实现 |
| `src/include/duckdb/main/capi/capi_internal.hpp` | C API 内部类型映射 |
| `src/include/duckdb/main/capi/extension_api.hpp` | 扩展 C API 函数指针表 |
