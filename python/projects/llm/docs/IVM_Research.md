
# 竞品调研


## Databrics
- https://www.youtube.com/watch?v=J_jJCwge9OM

DBX基于StructStreaming+Pipeline完成了StreamTable/MV/DLT的概念。
As Databricks engineering blog confirms:
“Under the hood, a Materialized View is powered by an auto-generated and managed Delta Live Tables pipeline…”
Materialized View = Declarative interface + Structured Streaming engine + Delta Lake storage + Managed orchestration
暂时无法在飞书文档外展示此内容
MaterializedView
- https://docs.databricks.com/gcp/en/optimizations/incremental-refresh
A materialized view is a declarative pipeline object. It includes a query that defines it, a flow to update it, and the cached results for fast access. A materialized view:
- Tracks changes in upstream data.
- On trigger, incrementally processes the changed data and applies the necessary transformations.
- Maintains the output table, in sync with the source data, based on a specified refresh interval.
Materialized views are a good choice for many transformations:
- You apply reasoning over cached results instead of rows. In fact, you simply write a query.
- They are always correct. All required data is processed, even if it arrives late or out of order.
- They are often incremental. Databricks will try to choose the appropriate strategy that minimizes the cost of updating a materialized view.
Incremental Operators
暂时无法在飞书文档外展示此内容
NOTE：
- Since updates create correct queries, some changes to inputs will require a full recomputation of a materialized view, which can be expensive.
- They are not designed for low-latency use cases. The latency of updating a materialized view is in the seconds or minutes, not milliseconds.
- Not all computations can be incrementally computed.
An incremental refresh processes changes in the underlying data after the last refresh and then appends that data to the table. Depending on the base tables and included operations, only certain types of materialized views can be incrementally refreshed.
Only materialized views updated using serverless pipelines can use incremental refresh. Materialized views that do not use serverless pipelines are always fully refreshed.
When materialized views are created using a SQL warehouse or serverless Lakeflow Declarative Pipelines, they are automatically incrementally refreshed if their queries are supported. If a query includes unsupported expressions for an incremental refresh, a full refresh is performed, potentially resulting in additional costs.
- Some incremental refresh operations require row-tracking to be enabled on the queried data sources. Row-tracking is a Delta Lake feature only supported by Delta tables, which include materialized views, streaming tables, and Unity Catalog managed tables. See Use row tracking for Delta tables.
DeltaLiveTable
- https://synccomputing.com/databricks-delta-live-tables-101/?utm_source=chatgpt.com
- https://www.databricks.com/blog/introducing-materialized-views-and-streaming-tables-databricks-sql

Struct Streaming
https://spark.apache.org/docs/latest/streaming/apis-on-dataframes-and-datasets.html

暂时无法在飞书文档外展示此内容
StreamTable
- https://docs.databricks.com/gcp/en/dlt/streaming-tables
Streaming tables are a good choice for data ingestion for the following reasons:
- Each input row is handled only once, which models the vast majority of ingestion workloads (that is, by appending or upserting rows into a table).
- They can handle large volumes of append-only data.

You can also use a watermark to bound a stream. A watermark in Spark Structured Streaming is a mechanism that helps handle late data by specifying how long the system should wait for delayed events before considering the window of time as complete. An unbounded stream that does not have a watermark can cause a pipeline to fail due to memory pressure.

https://docs.databricks.com/gcp/en/dlt/stateful-processing
Stream-snapshot joins
Stream-snapshot joins are joins between a stream and a dimension that is snapshotted when streams start. These joins do not recompute if the dimension changes after the stream has started, because the dimension table is treated as a snapshot in time, and changes to the dimension table after the stream starts are not reflected unless you reload or refresh the dimension table. This is reasonable behavior if you can accept small discrepancies in a join. For example, an approximate join is acceptable when the number of transactions is many orders of magnitude larger than the number of customers.

If you want your view to always be correct, you might want to use a materialized view. Materialized views are always correct because they automatically recompute joins when dimensions change
import dlt

@dlt.view
# assume this table contains an append-only stream of rows about transactions
# (customer_id=1, value=100)
# (customer_id=2, value=150)
# (customer_id=3, value=299)
# ... <and so on> ...
def v_transactions():
  return spark.readStream.table("transactions")

# assume this table contains only these two rows about customers
# (customer_id=1, name=Bilal)
# (customer_id=2, name=Olga)
@dlt.view
def v_customers():
  return spark.read.table("customers")

@dlt.table
def sales_report():
  # fact is read as stream
  facts = spark.readStream.table("v_transactions")
  # dims is read as table
  dims = spark.read.table("v_customers")

  return (
    facts.join(dims, on="customer_id", how="inner"
  )
Snowflake
- https://docs.snowflake.com/en/user-guide/dynamic-tables-supported-queries
- https://docs.snowflake.com/en/user-guide/dynamic-tables-performance-incremental-operators

[图片]

[图片]
Streaming Democratized: Ease Across the Latency Spectrum with Delayed View Semantics and Snowflake Dynamic Tables 
[图片]

[图片]
[图片]
Usage
REFRESH_MODE = { AUTO | FULL | INCREMENTAL }
Specifies the refresh mode for the dynamic table.
This property cannot be altered after you create the dynamic table. To modify the property, recreate the dynamic table with a CREATE OR REPLACE DYNAMIC TABLE command.
AUTO
When refresh mode is AUTO, the system attempts to apply an incremental refresh by default. However, when incremental refresh isn’t supported or expected to perform well, the dynamic table automatically selects full refresh instead. For more information, see Dynamic table refresh modes and Best practices for choosing dynamic table refresh modes.
To determine the best mode for your use case, experiment with refresh modes and automatic recommendations. For consistent behavior across Snowflake releases, explicitly set the refresh mode on all dynamic tables.
To verify the refresh mode for your dynamic tables, see View dynamic table refresh mode.
FULL
Enforces a full refresh of the dynamic table, even if the dynamic table can be incrementally refreshed.
INCREMENTAL
Enforces an incremental refresh of the dynamic table. If the query that underlies the dynamic table can’t perform an incremental refresh, dynamic table creation fails and displays an error message.

Supported Operators
暂时无法在飞书文档外展示此内容
Incremental Operators
暂时无法在飞书文档外展示此内容

Aggregate
-- 创建 Incremental Dynamic Table
CREATE DYNAMIC TABLE dt
  TARGET_LAG='5 MIN'
  REFRESH_MODE=INCREMENTAL
AS SELECT id, sum(amount) as total_amt
   FROM orders
   GROUP BY id;
   
 g
Join
- https://www.youtube.com/watch?v=3zf3wq0L-n8
[图片]

Streams
A stream stores an offset for the source object and not any actual table columns or data. When queried, a stream accesses and returns the historic data in the same shape as the source object (i.e. the same column names and ordering) with the following additional columns:
METADATA$ACTION
Indicates the DML operation (INSERT, DELETE) recorded.
METADATA$ISUPDATE
Indicates whether the operation was part of an UPDATE statement. Updates to rows in the source object are represented as a pair of DELETE and INSERT records in the stream with a metadata column METADATA$ISUPDATE values set to TRUE.
Note that streams record the differences between two offsets. If a row is added and then updated in the current offset, the delta change is a new row. The METADATA$ISUPDATE row records a FALSE value.
METADATA$ROW_ID
Specifies a unique, immutable row ID for tracking changes over time. If CHANGE_TRACKING is disabled and later re-enabled on the stream’s source object, the row ID could change.
[图片]
Once updates are made to the underlying tables, selecting ordersByCustomerStream will produce records of orders x Δ customers + Δ orders x customers + Δ orders x Δ customers where:
- Δ orders and Δ customers are the changes that have occurred to each table since the stream offset.
- orders and customers are the total contents of the tables at the current stream offset.
create or replace view ordersByCustomer as select * from orders natural join customers;

insert into orders values (1, 'order1');

insert into customers values (1, 'customer1');

create or replace stream ordersByCustomerStream on view ordersBycustomer;

Streams 无需维护额外的中间状态或者结果表来完成增量计算，主需要通过表的多版本逻辑实现增量CDC的输出；这个是一个很好的概念去输出Snapshot的Delta Read，StarRocks是否也需要类似的概念封装不同Engine的CDC。
Streams are limited to views that satisfy the following requirements:
Underlying Tables
- All of the underlying tables must be native tables.
- The view can apply only the following operations:
  - Projections
  - Filters
  - Inner or cross joins
  - UNION ALL
Nested views and subqueries in the FROM clause are supported as long as the fully expanded query satisfies the other requirements in this requirements table.
View Query
General requirements:
- The query can select any number of columns.
- The query can contain any number of WHERE predicates.
- Views with the following operations are not yet supported:
  - GROUP BY clauses
  - QUALIFY clauses
  - Subqueries not in the FROM clause
  - Correlated subqueries
  - LIMIT clauses
  - DISTINCT clauses
Functions:
- Functions in the select list must be system-defined, scalar functions.
BigQuery
- https://cloud.google.com/bigquery/docs/materialized-views-use#incremental_updates

Bigquery支持的Incremental Update比较初级：
- Aggregate只能支持增量Append；
- Join只能支持左表的增量Append；

For single-table materialized views, this is possible if the base table is unchanged since the last refresh, or if only new data was added. 
For JOIN views, only tables on the left side of the JOIN can have appended data. If one of the tables on the right side of a JOIN has changed, then the view cannot be incrementally updated.

If the base table had updates or deletions since the last refresh, or if the materialized view's base tables on the right side of the JOIN have changed, then BigQuery doesn't use incremental updates and instead automatically reverts to the original query. For more information about joins and materialized views, see Joins. 

Ensure that the largest or most frequently changing table is the first/leftmost table referenced in the view query. Materialized views with joins support incremental queries and refresh when the first or left-most table in the query is appended, but changes to other tables fully invalidate the view cache. In star or snowflake schemas the first or leftmost table should generally be the fact table.

The following example creates an aggregate incremental materialized view with a LEFT JOIN. This view is incrementally updated when data appends to the left table.
CREATE MATERIALIZED VIEW dataset.mv
AS (
  SELECT
    s_store_sk,
    s_country,
    s_zip,
    SUM(ss_net_paid) AS sum_sales,
  FROM dataset.store_sales
  LEFT JOIN dataset.store
    ON ss_store_sk = s_store_sk
  GROUP BY 1, 2, 3
);
Trino
Trino的增量刷新也很初级，只能支持Single Table Predicate Only Plan 。
- https://github.com/trinodb/trino/issues/18673
  - https://github.com/trinodb/trino/pull/20959
ClickHouse
Incremental Materialized View
Unlike in transactional databases like Postgres, a ClickHouse Materialized View is just a trigger that runs a query on blocks of data as they are inserted into a table. The result of this query is inserted into a second "target" table. Should more rows be inserted, results will again be sent to the target table where the intermediate results will be updated and merged. This merged result is the equivalent of running the query over all of the original data.

The principal motivation for Materialized Views is that the results inserted into the target table represent the results of an aggregation, filtering, or transformation on rows. These results will often be a smaller representation of the original data (a partial sketch in the case of aggregations). This, along with the resulting query for reading the results from the target table being simple, ensures query times are faster than if the same computation was performed on the original data, shifting computation (and thus query latency) from query time to insert time.
Refreshable Materialized View
https://clickhouse.com/docs/sql-reference/statements/create/view#refreshable-materialized-view
Hologres
https://help.aliyun.com/zh/hologres/user-guide/dynamic-table-overview/

[图片]

当前市面上，与Dynamic Table功能类似的有OLAP产品的异步物化视图、Snowflake的Dynamic Table等，其差别如下：
暂时无法在飞书文档外展示此内容

Dynamic Table Vs Materialized View
暂时无法在飞书文档外展示此内容

技术原理
创建了增量刷新的Dynamic Table，并通过Stream或Binlog的方式读取基表的增量数据后，系统会在底层创建一个列存的状态表（State表），用于存储Query的中间聚合状态，引擎在编码、存储等方面对中间聚合状态进行了优化，可以加快对中间聚合状态的读取和更新。增量数据会以微批次方式做内存态的聚合，再与状态表中的数据进行合并，然后以BulkLoad的方式将最新聚合结果高效地写入Dynamic Table。微批次的增量处理方式减少了单次刷新的数据处理量，显著提升了计算的时效性。
Streams/Binlog
暂时无法在飞书文档外展示此内容
Support Operators
- 支持任意标量表达式。
- 支持WHERE条件、子查询、CTE、GROUP BY、CUBE、GROUPING SETS、HAVING语句、Agg Filter、UNION ALL、UNNEST。
- 不支持窗口函数、IN子查询、EXISTS或NOT EXISTS、EXCEPT或INTERSECT、ORDER BY、LIMIT或OFFSET。
- V3.0版本仅支持维表等值JOIN（INNER JOIN/LEFT JOIN），且必须使用FOR SYSTEM_TIME AS OF PROCTIME()的方式。不支持多表双流JOIN，详情请参见维表JOIN语句。
  - 维表JOIN的语义是：对每条数据，只会关联当时维表的最新版本数据，即JOIN行为只发生在处理时间（Processing Time）。如果JOIN行为发生后，维表中的数据发生了变化（新增、更新或删除），则已关联的维表数据不会被同步更新。
- 从V3.0.26版本开始，支持多表双流JOIN，即OLAP中的普通JOIN，或者Flink中的双流JOIN，包括INNER JOIN、LEFT/RIGHT/FULL OUTER JOIN。详情请参见CREATE DYNAMIC TABLE。
State
https://help.aliyun.com/zh/hologres/user-guide/view-the-dynamic-table-structure-and-blood-relationship?spm=a2c4g.11186623.0.0.50402974amLK5u#b089affb1a6o0
增量刷新的Dynamic Table，为了加速数据计算，会在底层生成一张状态表（State），用于存放聚合处理结果，默认存储于默认Table Group中，不支持执行重新分片（Resharding），详情见Dynamic Table概述。此外，如果将刷新模式修改为全量刷新，则状态表（State）将默认被清理。
Maxcompute
Materialized View
https://help.aliyun.com/zh/maxcompute/user-guide/materialized-view/

Delta Live MV
MaxCompute增量计算是基于Delta Table增量数据存储和读写能力，通过CDC能力扩展增量物化视图，Time travel 以及 Stream Table 等一系列的增量计算能力。同时增量物化视图（IMV）和周期性调度任务提供了不同的触发频率，从而为用户提供更多手段来平衡延迟（Latency）和吞吐量（Throughput）。
CDC
CDC（Change Data Capture）定义了识别并捕获数据库表中数据的变更场景，用于记录Delta Table增量表行级别的插入、更新和删除等操作，从而可以有效捕捉该表的数据变化事件流，后续可以通过事件驱动辅助增量计算、数据同步、数仓分层等业务需求。

除数据列外，会额外输出如下三个系统列：
- __meta_timestamp：代表数据写入系统时间。
- __meta_op_type：包含1（INSERT）和0（DELETE）。
- __meta_is_update：包含1（TRUE）和0（FALSE）。
__meta_op_type和__meta_is_update可组合成如下四种情况：
暂时无法在飞书文档外展示此内容
Stream
Stream是MaxCompute自动管理Delta Table增量查询数据版本的流对象，记录对增量表所做的数据操作语言（DML）更改，包括插入、更新和删除，以及有关每次更改的元数据，以便您可以使用更改的数据采取操作。本文为您详细介绍Stream操作相关命令。

Delta Live MV
支持源表：
- 已在MaxCompute控制台创建云栖新功能邀测项目。
- 源表（source table）已开启CDC功能。目前支持的源表类型如下：
  - Delta Table增量表（详情请参见Delta Table概述），并且需要开启CDC功能。详情请参见建表DDL。
  - 增量物化视图表。增量物化视图默认已开启CDC功能。
使用限制：
- 增量物化视图不能包含非确定性计算，如RAND函数、UDF等。
- 当前增量物化视图支持的SQL算子包含：PROJECT、FILTER、AGGREGATE、JOIN。其中：
  - AGGREGATE当前仅支持以下常见函数：SUM、COUNT、AVG、MIN、MAX。
  - JOIN当前仅支持维表不发生数据变化的维表JOIN。
ADB
多表Join和复杂聚合计算通常消耗较多计算资源，且查询耗时长。AnalyticDB for MySQL物化视图可以解决此类问题。物化视图会将用户定义的查询提前计算好并将查询结果存储起来。查询时可以直接从物化视图中读取预先计算好的查询结果，从而加快查询响应速度。本文主要介绍如何创建物化视图。
全量刷新物化视图
您可以基于AnalyticDB for MySQL内表、外表、已有的物化视图和视图创建全量刷新的物化视图（以下简称全量物化视图）。
增量刷新物化视图
在创建增量物化视图之前，请完成以下准备工作：
- 检查集群的内核版本是否满足3.1.9.0及以上版本。
- 开启集群级别的Binlog特性及基表的Binlog功能。
- 如果开启基表的Binlog功能报错，解决方案请参见下文的Query execution error: : Can not create FAST materialized view, because demotable doesn't support getting incremental data。
增量物化视图的限制
- 增量物化视图对基表的限制：
  - 当query_body中使用MAX、MIN、APPROX_DISTINCT或COUNT(DISTINCT)聚合函数时，增量物化视图的基表只支持INSERT操作，不支持DELETE、UPDATE、REPLACE、INSERT ON DUPLICATE KEY UPDATE等会导致数据删除的操作。
- 增量物化视图的刷新触发机制的限制：只支持定时自动刷新，不支持手动刷新。刷新间隔最短5秒（s），最长5分钟（min）。
- 增量物化视图，query_body的规则与限制：
  - 不支持非确定性的表达式，如：NOW()、RAND()等。
  - 不支持ORDER BY排序操作。
  - 不支持HAVING子句。
  - 不支持窗口函数。
  - 不支持UNION、EXCEPT、INTERSECT等集合操作。
  - JOIN操作仅支持INNER JOIN。关联字段须满足所有条件：须为表的原始字段，数据类型须相同，且有INDEX索引。最多关联5张表。
  - 仅支持以下聚合函数：COUNT、SUM、MAX、MIN、AVG、APPROX_DISTINCT和COUNT(DISTINCT)。
  - AVG不支持DECIMAL类型。
  - COUNT(DISTINCT)仅支持INTEGER类型。
云器
[图片]
[图片]
ProtonBase
- https://protonbase.com/blogs/incremental-materialized-views
- https://protonbase.com/docs/guides/table/materialized-view
 为了解决这一矛盾，ProtonBase 提出了一种解决方案——增量物化视图。该方案通过将每张表的数据本身作为全量状态存储，并在每次更新时仅计算增量（delta），从而避免了逐级双流 Join 中每层都保存大量中间结果的状态爆炸问题。本文将详细介绍 Flink 的现有做法及其缺陷、ProtonBase 的解决方案及优势，并通过一个 Demo 演示增量计算过程，证明 ProtonBase 在数据一致性和正确性方面的优势。
- 全量状态存储: 在 ProtonBase 中，每张表的数据本身就作为全量状态存储下来。这意味着系统从一开始就完整保存了每个表的所有数据，而不必在 Join 时额外构造庞大的中间状态。通过这种方式，ProtonBase 避免了在逐级双流 Join 过程中不断累积和保存海量中间结果的问题，从而大大降低了状态的规模。
- 增量计算 Delta: 当一张表发生更新时（例如表 L 产生更新），ProtonBase 并不会触发全量 Join，而是仅计算更新部分的增量（delta）。这种基于 delta 的增量计算方式极大地减少了需要处理的数据量，具体包括以下两个场景：
  - 场景 A：如果表 L 更新，而表 R 未更新，此时系统会生成 ΔLΔL，然后利用ΔLΔL 与表 R 的全量数据进行 Join，产生新的结果增量，并将这些增量更新写入到物化视图中。
  - 场景 B：当表 R 后续也有更新时，会生成ΔRΔR，同样利用ΔRΔR与表 L 的全量数据进行 Join，再次更新物化视图。
  这种增量更新机制使得每一次 Join 操作只需要处理变化的数据，而非重新计算全量数据，从而大幅降低了状态存储的需求。
Materialize
Timeplus
IncrementalRead
CDC实现
Iceberg
Paimon
Delta
https://docs.databricks.com/gcp/en/delta/row-tracking
Delta Lake row tracking allows Databricks to track row-level lineage in a Delta table. This feature is required for some incremental updates for materialized views.

Enabling row tracking on existing tables automatically assigns row IDs and row commit versions to all existing rows in the table. This process can result in the creation of multiple new versions of the table and could take a significant amount of time.
CREATE TABLE table_name
TBLPROPERTIES (delta.enableRowTracking = true)
AS SELECT * FROM source_table;
暂时无法在飞书文档外展示此内容
PostgreSQL: Logical Replication
MySQL: Binlog
Snapshot Read