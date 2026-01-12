# Incremental Materialized View
- Set refresh_mode to incremetanl, if StarRocks cannot support it, throw exceptions in creating.
- Only iceberg tables are supported to create an incremental materialized view;

```
create materialzied view test_mv1
refresh async  
properties (
    "refresh_mode" = "incremental"
) as 
select  
    sum(l_suppkey) as sum_l_suppkey, 
    avg(l_orderkey) as min_l_orderkey
from lineitem 
group by l_shipmode;
```

## Incremental Refresh
- Only some patterns can be supported in current design, eg: agg/join-agg/join/select/project/union all, otherwise exceptions will be thrown at creating;
- (Current) Only append-only changes are supported to refresh an incremental materialized view; if non append-only changes (upsert/delete, eg), trigger complete refresh based on pct or full refresh mode instead.
- (Further) If base table can produce changes with non append-only, we may further refresh materialized view incrementally.
## Initial Refresh
Base tables can contain a large amount of data, especially for LakeHouse scenes; users will rarely refresh the total base table's data.
- Solution 1: We may use PCT refresh implement with partition_ttl to filter some unsatisfied partitons but in some cases, we may also need to scan all base table's history datas.
- Solution 2: Add a specific period of time to filter unused history data.
```
create materialzied view test_mv1
refresh async  
properties (
    "refresh_mode" = "incremental"
) as 
select  
    sum(l_suppkey) as sum_l_suppkey, 
    avg(l_orderkey) as min_l_orderkey
from lineitem 
where dt >= '2025-01-01'
group by l_shipmode;
```
## Partial Refresh
- Refresh mv with start and end is not supported yet for incremental mv, because incremental mv needs to be refreshed continually. 
- But partial refresh will try to use PCT based refresh to overwrite specific partitions.
```
REFRESH MATERIALIZED VIEW [database.]mv_name
[PARTITION START ("<partition_start_date>") END ("<partition_end_date>")]
[FORCE]
[WITH { SYNC | ASYNC } MODE]
```
## Refresh Mode
- AUTO : Automatically determine the refresh mode based on the materialized view's properties.
- PCT :  Partition-based refresh mode(partition-change-tracking), only refresh the partitions that have changed since the last refresh.
- INCREMENTAL : Incremental refresh mode, only refresh the incremental changed rows since the last refresh.
- FULL: Full refresh mode, refresh all partitions of the materialized view.

```
/**
 * Refresh mode for materialized view.
 */
public enum RefreshMode {
    /**
     * AUTO: Automatically determine the refresh mode based on the materialized view's properties.
     */
    AUTO,
    /**
     * PCT: Partition-based refresh mode(partition-change-tracking), only refresh the partitions that have changed since
     * the last refresh.
     */
    PCT,
    /**
     * FULL: Full refresh mode, refresh all partitions of the materialized view.
     */
    FULL,
    /**
     * INCREMENTAL: Incremental refresh mode, only refresh the incremental changed rows since the last refresh.
     */
    INCREMENTAL;
}
```
## Transparent MV Rewrite
Transparent mv rewrite cannot be used by default, this is because transparent mv rewrite depends on original MV refresh's version map heavily.
- Solution 1: If users change query_rewrite_consistency = loose , the mv still can be used for rewriting, but there may be consistent problems.
- Solution 2: Even in incremental mv refresh, we still maintain PCT refresh's version map to be compatible with original mv rewrite conditions.
## Partition TTL
Incremental MV can still support partition ttl like ordinary OlapTables, which will be used for dropping expired partitions. 
- Like MVs with PCT refresh, Partition TTL can be used in incremental mv refresh stage; but it will introduce overhead or corner cases since the partition decouple between base tables and the mv.
- We may use pct refresh's implements to deduce partitions to refresh and partitions to be filtered.