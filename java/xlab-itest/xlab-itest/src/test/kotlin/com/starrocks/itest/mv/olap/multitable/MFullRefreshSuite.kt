package com.starrocks.itest.mv.olap.multitable

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.mv.Enumerator
import com.starrocks.schema.MMaterializedView
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream

open class MFullRefreshSuite : MVSuite() {
    fun getJoinTemplate(joinOp: String, defineSql: String): String {
        val choose = if (joinOp.contains("right")) "b" else "a"
        return """
select ${choose}.lo_orderdate, count(1)
from
($defineSql) a
${joinOp} join
($defineSql) b
on a.lo_orderdate = b.lo_orderdate
group by ${choose}.lo_orderdate 
""".trimIndent()
    }

    fun getUnionAllTemplate(defineSql: String): String {
        // TODO: add more agg functions
        val choose = "a"
        return """
select a.lo_orderdate, count(1)
from
($defineSql
union all
$defineSql) a
group by a.lo_orderdate 
""".trimIndent()
    }

    protected open fun withPartColumnType(): String {
        return ""
    }

    protected open fun withMVPartColumn(basePartitionColumnName: String): String {
        return basePartitionColumnName
    }

    private fun buildMV(defineSql: String): MMaterializedView {
        val mvPartitionColumn = withMVPartColumn("lo_orderdate")
        val mv = MMaterializedView(DEFAULT_MV_NAME, mvPartitionColumn, defineSql)
        mv.withPartColumnType(withPartColumnType())
        return mv;
    }

    protected open fun assertContainsWithMV(defineSql: String, isScan: Boolean, vararg queries: String) {
        // Test with different joins
        val joinOps = Enumerator.joinOps
        for (joinOp in joinOps) {
            val mvDefineSql = getJoinTemplate(joinOp, defineSql)
            val mv = buildMV(mvDefineSql)

            withCompleteRefreshMV(mv) {
                if (isScan) {
                    assertContains(mvDefineSql, DEFAULT_MV_NAME)
                }
                assertEqualsWithMV(mvDefineSql)
            }
        }
        // Test with union all operators
        val mvDefineSql = getUnionAllTemplate(defineSql)
        val mv = buildMV(mvDefineSql)
        withCompleteRefreshMV(mv) {
            assertEqualsWithMV(mvDefineSql)
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
    private fun getArgumentsProvider(): Stream<Arguments> {
        return mapOf(
            //////// select *
            // scan
            "select * from lineorder" to true,
            // scan with 1 partition filter
            "select * from lineorder where lo_orderdate >= '19930101'" to true,
            // scan with 1 non-partition filter
            "select * from lineorder where lo_orderkey > 1" to true,
            // scan with 1 non-partition filter with redundant predicates
            "select * from lineorder where lo_orderkey > 1 and lo_orderkey is not null" to true,
            // scan with 2 partition filter
            "select * from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101'" to true,
            // scan with 2 partition and non-partition filter
            "select * from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000" to true,
            // scan with subquery
            "select * from (select * from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000) tt" to true,

            //////// select with column and column alias
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder" to true,
            // scan with 1 partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101'" to true,
            // scan with 1 non-partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1" to true,
            // scan with 2 partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101'" to true,
            // scan with 2 partition and non-partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000" to true,
            // scan with subquery
            "select * from (select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000) tt" to true,

            // aggregate
            "select lo_orderdate, count(1) from lineorder group by lo_orderdate"  to false,
            // aggregate with filter
            "select lo_orderdate, count(1) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate " to false,
            // aggregate with having filter
            "select lo_orderdate, count(1) from lineorder group by lo_orderdate having count(*) > 100"  to false,
            "select lo_orderdate, count(1) from lineorder group by lo_orderdate having count(*) >= 1"  to false,
            // aggregate with having filter and filter
            "select lo_orderdate, count(1) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate  having count(*) > 100"  to false,
            // aggregate with distinct
            "select lo_orderdate, count(distinct lo_orderkey) from lineorder group by lo_orderdate"  to false,
            // TODO: support filter with perfect rewrite
            // "select lo_orderdate, count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
            "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate"  to false,
            "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate  having count(*) > 100"  to false,

            // aggregate with multi distinct
            // TODO: support text based rewrite
            // "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder group by lo_orderdate",
            // "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
            // "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate  having count(*) > 100",
        ).map { (x, isScan) -> Arguments.of(x, isScan) }.stream()
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider")
    fun testCreateMVWithSingleTableBaseQueries(sql: String, isScan: Boolean) {
        // test base query
        assertContainsWithMV(sql, isScan, sql)
    }
}