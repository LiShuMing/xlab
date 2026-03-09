# Incremental Materialized View

- Set `refresh_mode` to `incremental`. If StarRocks cannot support it, throw exceptions when creating.
- Only Iceberg tables are supported to create an incremental materialized view.

```sql
CREATE MATERIALIZED VIEW test_mv1
REFRESH ASYNC
PROPERTIES (
    "refresh_mode" = "incremental"
) AS
SELECT
    SUM(l_suppkey) AS sum_l_suppkey,
    AVG(l_orderkey) AS min_l_orderkey
FROM lineitem
GROUP BY l_shipmode;
```

## Incremental Refresh

- Only some patterns can be supported in current design, e.g., agg/join-agg/join/select/project/union all; otherwise exceptions will be thrown at creation.
- **(Current)** Only append-only changes are supported to refresh an incremental materialized view. If non append-only changes (upsert/delete, etc.), trigger complete refresh based on PCT or full refresh mode instead.
- **(Further)** If base tables can produce changes with non append-only, we may further refresh the materialized view incrementally.

## Initial Refresh

Base tables can contain a large amount of data, especially for LakeHouse scenarios; users will rarely refresh the total base table's data.

- **Solution 1**: Use PCT refresh implementation with `partition_ttl` to filter some unsatisfied partitions, but in some cases we may also need to scan all base table's historical data.
- **Solution 2**: Add a specific period of time to filter unused historical data.

```sql
CREATE MATERIALIZED VIEW test_mv1
REFRESH ASYNC
PROPERTIES (
    "refresh_mode" = "incremental"
) AS
SELECT
    SUM(l_suppkey) AS sum_l_suppkey,
    AVG(l_orderkey) AS min_l_orderkey
FROM lineitem
WHERE dt >= '2025-01-01'
GROUP BY l_shipmode;
```

## Partial Refresh

- Refreshing MV with start and end is not supported yet for incremental MV, because incremental MV needs to be refreshed continuously.
- Partial refresh will try to use PCT-based refresh to overwrite specific partitions.

```sql
REFRESH MATERIALIZED VIEW [database.]mv_name
[PARTITION START ("<partition_start_date>") END ("<partition_end_date>")]
[FORCE]
[WITH { SYNC | ASYNC } MODE]
```

## Refresh Mode

- **AUTO**: Automatically determine the refresh mode based on the materialized view's properties.
- **PCT**: Partition-based refresh mode (partition-change-tracking), only refresh the partitions that have changed since the last refresh.
- **INCREMENTAL**: Incremental refresh mode, only refresh the incremental changed rows since the last refresh.
- **FULL**: Full refresh mode, refresh all partitions of the materialized view.

```java
/**
 * Refresh mode for materialized view.
 */
public enum RefreshMode {
    /**
     * AUTO: Automatically determine the refresh mode based on the materialized view's properties.
     */
    AUTO,
    /**
     * PCT: Partition-based refresh mode (partition-change-tracking), only refresh the partitions
     * that have changed since the last refresh.
     */
    PCT,
    /**
     * FULL: Full refresh mode, refresh all partitions of the materialized view.
     */
    FULL,
    /**
     * INCREMENTAL: Incremental refresh mode, only refresh the incremental changed rows
     * since the last refresh.
     */
    INCREMENTAL;
}
```

## Transparent MV Rewrite

Transparent MV rewrite cannot be used by default, because transparent MV rewrite depends heavily on the original MV refresh's version map.

- **Solution 1**: If users set `query_rewrite_consistency = loose`, the MV can still be used for rewriting, but there may be consistency problems.
- **Solution 2**: Even in incremental MV refresh, we still maintain PCT refresh's version map to be compatible with original MV rewrite conditions.

## Partition TTL

Incremental MV can still support partition TTL like ordinary OLAP tables, which will be used for dropping expired partitions.

- Like MVs with PCT refresh, Partition TTL can be used in incremental MV refresh stage, but it will introduce overhead or corner cases since the partition decoupling between base tables and the MV.
- We may use PCT refresh's implementation to deduce partitions to refresh and partitions to be filtered.