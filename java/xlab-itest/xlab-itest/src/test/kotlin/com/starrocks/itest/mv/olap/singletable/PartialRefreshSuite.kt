package com.starrocks.itest.mv.olap.singletable

import com.google.common.collect.ImmutableList
import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.PartialRefreshParam
import com.starrocks.schema.MMaterializedView
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream
import kotlin.test.Ignore

open class PartialRefreshSuite : MVSuite() {

    val PREDICATE_PLACEHOLDER = "<predicate>"

    protected open fun assertContainsWithMV(defineSql: String, param: PartialRefreshParam, vararg queries: String) {
        val newDefineSql = defineSql.replace(PREDICATE_PLACEHOLDER, "true")
        val mv = MMaterializedView(DEFAULT_MV_NAME, "lo_orderdate", newDefineSql)
        withPartialRefreshMV(mv, param.start, param.end) {
            for (query in queries) {
                for (pred in param.predicates) {
                    val newQuery = query.replace(PREDICATE_PLACEHOLDER, pred)
                    assertContains(newQuery, DEFAULT_MV_NAME)
                    assertEqualsWithMV(newQuery)
                }
            }
        }
    }

    /**
     * This is lineorder table's schema, you can add tests to test single table for mv's creatation and rewrite.
     *
     * mysql> desc lineorder;
     * +------------------+-------------+------+-------+---------+-------+
     * | Field            | Type        | Null | Key   | Default | Extra |
     * +------------------+-------------+------+-------+---------+-------+
     * | lo_orderkey      | int         | NO   | true  | NULL    |       |
     * | lo_linenumber    | int         | NO   | false | NULL    |       |
     * | lo_custkey       | int         | NO   | false | NULL    |       |
     * | lo_partkey       | int         | NO   | false | NULL    |       |
     * | lo_suppkey       | int         | NO   | false | NULL    |       |
     * | lo_orderdate     | datetime    | NO   | false | NULL    |       |
     * | lo_orderpriority | varchar(16) | NO   | false | NULL    |       |
     * | lo_shippriority  | int         | NO   | false | NULL    |       |
     * | lo_quantity      | int         | NO   | false | NULL    |       |
     * | lo_extendedprice | int         | NO   | false | NULL    |       |
     * | lo_ordtotalprice | int         | NO   | false | NULL    |       |
     * | lo_discount      | int         | NO   | false | NULL    |       |
     * | lo_revenue       | int         | NO   | false | NULL    |       |
     * | lo_supplycost    | int         | NO   | false | NULL    |       |
     * | lo_tax           | int         | NO   | false | NULL    |       |
     * | lo_commitdate    | int         | NO   | false | NULL    |       |
     * | lo_shipmode      | varchar(11) | NO   | false | NULL    |       |
     * +------------------+-------------+------+-------+---------+-------+
     * 17 rows in set (0.00 sec)
     */
    val sqls = ImmutableList.of(
        //////// select *
        // scan
        "select * from lineorder where <predicate>",
        // scan with 1 non-partition filter
        "select * from lineorder where lo_orderkey > 1 and <predicate>",
        // scan with subquery
        "select * from (select * from lineorder where lo_orderkey > 1 and <predicate>) tt",

        //////// select with column and column alias
        "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where true and <predicate>",
        // scan with 1 non-partition filter
        "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1 and <predicate>",
        // scan with subquery
        "select * from (select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and <predicate>) tt",

        // aggregate
        "select lo_orderdate, count(1) from lineorder where <predicate> group by lo_orderdate",
        // aggregate with filter
        "select lo_orderdate, count(1) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and  <predicate> group by lo_orderdate ",
        // aggregate with having filter
        "select lo_orderdate, count(1) from lineorder where <predicate> group by lo_orderdate having count(*) > 100",
        "select lo_orderdate, count(1) from lineorder where  <predicate> and  lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate having count(*) >= 1",

        // aggregate with distinct
        "select lo_orderdate, count(distinct lo_orderkey) from lineorder where <predicate> group by lo_orderdate",
        // TODO: support filter with perfect rewrite
        //  "select lo_orderdate, count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
        "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and <predicate> group by lo_orderdate",
        "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and <predicate> group by lo_orderdate  having count(*) > 100",

        // aggregate with multi distinct
        // TODO: support text based rewrite
        //  "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder group by lo_orderdate",
    )

    protected open val partialRefreshParams = arrayOf(
        PartialRefreshParam("1993-01-01 00:00:00", "1994-01-01 00:00:00",
            arrayOf(
                // total rewrite
                "lo_orderdate='1993-01-01'",
                "lo_orderdate='1993-01-01 00:00:00'",
                "date_trunc('day', lo_orderdate)='1993-01-01'",
                "lo_orderdate between '1993-01-01' and '1994-01-01",
                "lo_orderdate between '1993-01-01 00:00:00' and '1994-01-01 00:00:00'",
                // partial rewrite
                "lo_orderdate >='1993-01-01'",
                "lo_orderdate >='1993-01-01' and lo_orderdate < '1995-01-01'",
                "lo_orderdate >='1993-01-01 00:00:00' and lo_orderdate < '1995-01-01 00:00:00'",
                "date_trunc('day', lo_orderdate)='1993-01-01' and date_trunc('day', lo_orderdate) < '1995-01-01'",
                "date_trunc('day', lo_orderdate)>='1993-01-01'",
                "lo_orderdate between '1993-01-01' and '1995-01-01",
                "lo_orderdate between '1993-01-01 00:00:00' and '1994-01-01 00:00:00'",
                "lo_orderdate between '1993-01-01 00:00:00' and '1995-01-01 00:00:00'",
                "lo_orderdate between '1993-01-01 00:00:00' and '1996-01-01 00:00:00'",
            )
        ),
        PartialRefreshParam("1993-01-01", "1994-01-01",
            arrayOf(
                "lo_orderdate='1993-01-01 00:00:00'",
                "date_trunc('day', lo_orderdate)='1993-01-01'",
                "lo_orderdate between '1993-01-01 00:00:00' and '1994-01-01 00:00:00'",
            )
        )
    )

    private fun getArgumentsProvider1(): Stream<Arguments> {
        return sqls.zip(partialRefreshParams).map{x -> Arguments.of(x.first, x.second)}.stream()
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider1")
    fun testCreateMVWithSingleTableBaseQueries(sql: String, param: PartialRefreshParam) {
        // test base query
        assertContainsWithMV(sql, param, sql)
    }

    @Ignore
    @ParameterizedTest
    @MethodSource("getArgumentsProvider1")
    fun testCreateMVWithSingleTableWithSubQueries(sql: String, param: PartialRefreshParam) {
        // test subquery
        val subQuery = "select * from (${sql}) t"
        assertContainsWithMV(subQuery, param, sql, subQuery)
    }

    @Ignore
    @ParameterizedTest
    @MethodSource("getArgumentsProvider1")
    fun testCreateMVWithSingleTableWithViews(sql: String, param: PartialRefreshParam) {
        // test view
        val viewName = "view_0"
        val newQuery = "select * from ${viewName}"
        withView(viewName, "select * from (${sql}) t") {
            assertContainsWithMV(newQuery, param, sql, newQuery)
        }
    }

    @Ignore
    @ParameterizedTest
    @MethodSource("getArgumentsProvider1")
    fun testCreateMVWithSingleTableWithCTEs(sql: String, param: PartialRefreshParam) {
        // test cte
        val  newQuery = "with cte0 as ($sql) select * from cte0 "
        assertContainsWithMV(newQuery, param, sql, newQuery)
    }

    protected open fun getArgumentsProvider2(): Stream<Arguments> {
        val params =  arrayOf(
            // refresh by date
            PartialRefreshParam("1994-01-01", "1995-01-01",
                arrayOf(
                    "lo_orderdate='1994-01-01'",
                    "lo_orderdate='1994-01-01 00:00:00'",
                    "date_trunc('day', lo_orderdate)='1994-01-01'",
                    "lo_orderdate between '1994-01-01 00:00:00' and '1995-01-01 00:00:00'",
                    "lo_orderdate between '1994-01-01' and '1995-01-01' and lo_shipmode in ('SHIP', 'AIR') and lo_quantity in (10, 20)",
                    "lo_orderdate in ('1994-01-01') and lo_shipmode in ('SHIP', 'AIR') and lo_quantity in (10, 20)",
                )
            ),
            // refresh by datetime
            PartialRefreshParam("1994-01-01 00:00:00", "1995-01-01 00:00:00",
                arrayOf(
                    "lo_orderdate='1994-01-01'",
                    "lo_orderdate='1994-01-01 00:00:00'",
                    "date_trunc('day', lo_orderdate)='1994-01-01'",
                    "lo_orderdate between '1994-01-01 00:00:00' and '1995-01-01 00:00:00'",
                    "lo_orderdate between '1994-01-01' and '1995-01-01' and lo_shipmode in ('SHIP', 'AIR') and lo_quantity in (10, 20)",
                    "lo_orderdate in ('1994-01-01') and lo_shipmode in ('SHIP', 'AIR') and lo_quantity in (10, 20)",
                )
            ),
            // refresh by datetime(1993-01-01~ 1995-01-01)
            PartialRefreshParam("1993-01-01 00:00:00", "1995-01-01 00:00:00",
                arrayOf(
                    "lo_orderdate='1994-01-01 00:00:00'",
                    "date_trunc('day', lo_orderdate)='1994-01-01'",
                    // TODO: between is inclusive, and this cannobe rewritten by union rewrite
                    // "lo_orderdate between '1994-01-01 00:00:00' and '1995-01-01 00:00:00'",
                    // TODO: fix me
                    // "lo_orderdate between '1994-01-01' and '1995-01-01' and lo_shipmode in ('SHIP', 'AIR') and lo_quantity in (10, 20)",
                    "lo_orderdate in ('1994-01-01') and lo_shipmode in ('SHIP', 'AIR') and lo_quantity in (10, 20)",
                )
            )
        )
        return params.map{x -> Arguments.of(x)}.stream()
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider2")
    fun testAggregateWithExtraPredicates(param: PartialRefreshParam) {
        sql("set materialized_view_rewrite_mode='force'")
        val sql = """
            select 
                lo_orderdate, lo_quantity, lo_shipmode,
                bitmap_union(to_bitmap(lo_orderkey)),
                bitmap_union(to_bitmap(lo_extendedprice)),
                bitmap_union(to_bitmap(lo_ordtotalprice)),
                bitmap_union(to_bitmap(lo_supplycost))
            from lineorder 
            where lo_orderpriority in ('MEDIUM') and <predicate>
            group by lo_orderdate, lo_quantity, lo_shipmode
            """

        val newDefineSql = sql.replace(PREDICATE_PLACEHOLDER, "true")
        val mv = MMaterializedView(DEFAULT_MV_NAME, "lo_orderdate", "lo_orderdate", "lo_orderdate", newDefineSql)
        withPartialRefreshMV(mv, param.start, param.end) {
            for (pred in param.predicates) {
                val newQuery = sql.replace(PREDICATE_PLACEHOLDER, pred)
                assertContains(newQuery, DEFAULT_MV_NAME)
                assertEqualsWithMV(newQuery)
            }
        }
    }
}