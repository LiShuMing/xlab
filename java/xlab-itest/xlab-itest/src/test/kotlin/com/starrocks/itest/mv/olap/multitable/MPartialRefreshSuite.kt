package com.starrocks.itest.mv.olap.multitable

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.PartialRefreshParam
import com.starrocks.itest.framework.mv.Enumerator
import com.starrocks.schema.MMaterializedView
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream

open class MPartialRefreshSuite : MVSuite() {
    val PREDICATE_PLACEHOLDER = "<predicate>"

    fun getJoinTemplate(joinOp: String, defineSql: String, pred: String, withPredicate: Boolean): String {
        val choose = if (joinOp.contains("right")) "b" else "a"
        val predicate = if(withPredicate) pred.replace("lo_orderdate", "${choose}.lo_orderdate") else "true"
        return """
select ${choose}.lo_orderdate, count(1)
from
($defineSql) a
${joinOp} join
($defineSql) b
on a.lo_orderdate = b.lo_orderdate
where true and $predicate
group by ${choose}.lo_orderdate 
""".trimIndent()
    }

    fun getUnionAllTemplate(defineSql: String, pred: String, withPredicate: Boolean): String {
        // TODO: add more agg functions
        val predicate = if (withPredicate) pred else "true"
        return """
select a.lo_orderdate, count(1)
from
($defineSql
union all
$defineSql) a
where true and $predicate
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

    protected open fun assertContainsWithMV(defineSql: String, param: PartialRefreshParam, isScan: Boolean, withPredicate: Boolean, vararg queries: String) {
        // Test with different joins
        val joinOps = Enumerator.joinOps
        val newDefineSql = defineSql.replace(PREDICATE_PLACEHOLDER, "true")
        for (joinOp in joinOps) {
            val mvDefineSql = getJoinTemplate(joinOp, newDefineSql, "", false)
            val mv = buildMV(mvDefineSql)

            withPartialRefreshMV(mv, param.start, param.end) {
                for (query in queries) {
                    for (pred in param.predicates) {
                        val realQuery = getJoinTemplate(joinOp, query, pred, withPredicate).replace(PREDICATE_PLACEHOLDER, pred)
                        if (isScan) {
                            assertContains(realQuery, DEFAULT_MV_NAME)
                        }
                        assertEqualsWithMV(realQuery)
                    }
                }
            }
        }

        // Test with union all operators
        val mvDefineSql = getUnionAllTemplate(newDefineSql, "", false)
        val mv = buildMV(mvDefineSql)

        withPartialRefreshMV(mv, param.start, param.end) {
            for (query in queries) {
                for (pred in param.predicates) {
                    val realQuery = getUnionAllTemplate(query, pred, withPredicate).replace(PREDICATE_PLACEHOLDER, pred)
                    assertEqualsWithMV(realQuery)
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
    val sqls = mapOf(
        //////// select *
        // scan
        "select * from lineorder where <predicate>" to true,
        // scan with 1 non-partition filter
        "select * from lineorder where lo_orderkey > 1 and <predicate>" to true,
        // scan with subquery
        "select * from (select * from lineorder where lo_orderkey > 1 and <predicate>) tt" to true,

        //////// select with column and column alias
        "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where true and <predicate>" to true,
        // scan with 1 non-partition filter
        "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1 and <predicate>" to true,
        // scan with subquery
        "select * from (select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and <predicate>) tt" to true,

        // aggregate
        "select lo_orderdate, count(1) from lineorder where <predicate> group by lo_orderdate" to false,
        // aggregate with filter
        "select lo_orderdate, count(1) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and  <predicate> group by lo_orderdate " to false,
        // aggregate with having filter
        "select lo_orderdate, count(1) from lineorder where <predicate> group by lo_orderdate having count(*) > 100" to false,
        "select lo_orderdate, count(1) from lineorder where  <predicate> and  lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate having count(*) >= 1" to false,

        // aggregate with distinct
        "select lo_orderdate, count(distinct lo_orderkey) from lineorder where <predicate> group by lo_orderdate" to false,
        // TODO: support filter with perfect rewrite
        //  "select lo_orderdate, count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
        "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and <predicate> group by lo_orderdate" to false,
        "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and <predicate> group by lo_orderdate  having count(*) > 100" to false,

        // aggregate with multi distinct
        // TODO: support text based rewrite
        //  "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder group by lo_orderdate",
    )

    protected val partialRefreshParams = arrayOf(
        PartialRefreshParam("1993-01-01 00:00:00", "1994-01-01 00:00:00",
            arrayOf(
                // total rewrite
                "lo_orderdate='1993-01-01'",
                "lo_orderdate='1993-01-01 00:00:00'",
                "date_trunc('day', lo_orderdate)='1993-01-01'",
                "lo_orderdate between '1993-01-01' and '1994-01-01'",
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
        return sqls.keys.zip(partialRefreshParams).map{x -> Arguments.of(x.first, x.second, sqls[x.first])}.stream()
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider1")
    fun testCreateMVWithSingleTableBaseQueries(sql: String, param: PartialRefreshParam, isScan: Boolean) {
        // test base query
        assertContainsWithMV(sql, param, isScan, false, sql)
    }

    val sqls2 = mapOf(
        //////// select *
        // scan
        "select * from lineorder " to true,
        // scan with 1 non-partition filter
        "select * from lineorder where lo_orderkey > 1" to true,
        // scan with subquery
        "select * from (select * from lineorder where lo_orderkey > 1 and <predicate>) tt" to true,

        //////// select with column and column alias
        "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where true " to true,
        // scan with 1 non-partition filter
        "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1 " to true,
        // scan with subquery
        "select * from (select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 ) tt" to true,

        // aggregate
        "select lo_orderdate, count(1) from lineorder where <predicate> group by lo_orderdate" to false,
        // aggregate with filter
        "select lo_orderdate, count(1) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 and  <predicate> group by lo_orderdate " to false,
        // aggregate with having filter
        "select lo_orderdate, count(1) from lineorder where <predicate> group by lo_orderdate having count(*) > 100" to false,
        "select lo_orderdate, count(1) from lineorder where  <predicate> and  lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate having count(*) >= 1" to false,

        // aggregate with distinct
        "select lo_orderdate, count(distinct lo_orderkey) from lineorder where <predicate> group by lo_orderdate" to false,
        // TODO: support filter with perfect rewrite
        //  "select lo_orderdate, count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
        "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000  group by lo_orderdate" to false,
        "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000  group by lo_orderdate  having count(*) > 100" to false,

        // aggregate with multi distinct
        // TODO: support text based rewrite
        //  "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder group by lo_orderdate",
    )

    private fun getArgumentsProvider2(): Stream<Arguments> {
        return sqls2.keys.zip(partialRefreshParams).map{x -> Arguments.of(x.first, x.second, sqls2[x.first])}.stream()
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider2")
    fun testCreateMVWithSingleTableBaseQueries2(sql: String, param: PartialRefreshParam, isScan: Boolean) {
        // test base query
        assertContainsWithMV(sql, param, isScan, true, sql)
    }
}