package com.starrocks.itest.mv.olap.singletable

import com.google.common.base.Joiner
import com.google.common.collect.ImmutableList
import com.google.common.collect.Sets
import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.mv.ColumnTypeEnum
import com.starrocks.itest.framework.mv.Enumerator
import com.starrocks.itest.framework.utils.Util
import com.starrocks.schema.MMaterializedView
import com.starrocks.schema.MSSBSchema
import com.starrocks.schema.MSchema
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream
import kotlin.test.Ignore
import kotlin.test.Test

open class FullRefreshSuite : MVSuite() {
    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_date.sql")
        sql(createTableSql)
    }

    protected open fun assertContainsWithMV(defineSql: String, vararg queries: String) {
        val mv = MMaterializedView(DEFAULT_MV_NAME, "lo_orderdate", defineSql)
        withCompleteRefreshMV(mv) {
            for (query in queries) {
                assertContains(query, DEFAULT_MV_NAME)
                assertEqualsWithMV(query)
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
    private fun getArgumentsProvider(): Stream<Arguments> {
        return ImmutableList.of(
            //////// select *
            // scan
            "select * from lineorder",
            // scan with 1 partition filter
            "select * from lineorder where lo_orderdate >= '19930101'",
            // scan with 1 non-partition filter
            "select * from lineorder where lo_orderkey > 1",
            // scan with 1 non-partition filter with redundant predicates
            "select * from lineorder where lo_orderkey > 1 and lo_orderkey is not null",
            // scan with 2 partition filter
            "select * from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101'",
            // scan with 2 partition and non-partition filter
            "select * from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000",
            // scan with subquery
            "select * from (select * from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000) tt",

            //////// select with column and column alias
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder",
            // scan with 1 partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101'",
            // scan with 1 non-partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderkey > 1",
            // scan with 2 partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101'",
            // scan with 2 partition and non-partition filter
            "select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000",
            // scan with subquery
            "select * from (select lo_orderkey,  lo_linenumber, lo_orderdate, lo_custkey, lo_orderpriority from lineorder where lo_orderdate >= '19930101' and lo_orderdate < '19980101' and lo_orderkey > 1 and lo_orderkey < 10000) tt",

            // aggregate
            "select lo_orderdate, count(1) from lineorder group by lo_orderdate",
            // aggregate with filter
            "select lo_orderdate, count(1) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate ",
            // aggregate with having filter
            "select lo_orderdate, count(1) from lineorder group by lo_orderdate having count(*) > 100",
            "select lo_orderdate, count(1) from lineorder group by lo_orderdate having count(*) >= 1",
            // aggregate with having filter and filter
            "select lo_orderdate, count(1) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate  having count(*) > 100",
            // aggregate with distinct
            "select lo_orderdate, count(distinct lo_orderkey) from lineorder group by lo_orderdate",
            // TODO: support filter with perfect rewrite
            // "select lo_orderdate, count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
            "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
            "select lo_orderdate, count(1), count(distinct lo_orderkey) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate  having count(*) > 100",

            // aggregate with multi distinct
            // TODO: support text based rewrite
            // "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder group by lo_orderdate",
            // "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate",
            // "select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) from lineorder where lo_orderkey > 1 and lo_orderkey < 10000 group by lo_orderdate  having count(*) > 100",
        ).map { x -> Arguments.of(x) }.stream()
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider")
    fun testCreateMVWithSingleTableBaseQueries(sql: String) {
        // test base query
        assertContainsWithMV(sql, sql)
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider")
    fun testCreateMVWithSingleTableWithSubQueries(sql: String) {
        // test subquery
        val subQuery = "select * from (${sql}) t"
        assertContainsWithMV(subQuery, sql, subQuery)
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider")
    fun testCreateMVWithSingleTableWithViews(sql: String) {
        // test view
        val viewName = "view_0"
        val newQuery = "select * from ${viewName}"
        withView(viewName, "select * from (${sql}) t") {
            assertContainsWithMV(newQuery, sql, newQuery)
        }
    }

    @ParameterizedTest
    @MethodSource("getArgumentsProvider")
    fun testCreateMVWithSingleTableWithCTEs(sql: String) {
        // test cte
        val  newQuery = "with cte0 as ($sql) select * from cte0 "
        assertContainsWithMV(newQuery, sql, newQuery)
    }

    @Test
    @Ignore
    fun testMVWithMultiCountDistinct() {
        val sql = """
            select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), 
            count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) 
            from lineorder group by lo_orderdate
        """.trimIndent()
        assertContainsWithMV(sql, sql)
    }

    @Test
    @Ignore
    fun testMVWithMultiCountDistinct2() {
        val sql = """
            select lo_orderdate, count(1), multi_distinct_count(lo_orderkey), multi_distinct_count(lo_linenumber), 
            multi_distinct_count(lo_custkey), multi_distinct_count(lo_suppkey), multi_distinct_count(lo_orderpriority) 
            from lineorder group by lo_orderdate
        """.trimIndent()
        val query = """
            select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), 
            count(distinct lo_custkey), count(distinct lo_suppkey), count(distinct lo_orderpriority) 
            from lineorder group by lo_orderdate
        """.trimIndent()
        assertContainsWithMV(sql, query)
    }

    @Test
    fun testAllAggregateFuncs() {
        val lineorderSchema = """
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
        """.trimIndent()
        val lineorderColNameToType = lineorderSchema.split("\n").map { line ->
            val arr = line.split("|")
            arr.get(1).strip() to arr.get(2).strip()
        }

        val lineOrderColumnMap = lineorderColNameToType
            .filter { (colName, colType) ->
                !setOf("lo_orderdate", "lo_quantity").contains(colName)
            }
            .map { (colName, colType) ->

                if (colType.contains("int") || colType.contains("bigint")
                    || colType.contains("decimal")
                    || colType.contains("double")
                    || colType.contains("float")
                ) {
                    colName to ColumnTypeEnum.NUMBER
                } else if (colType.contains("varchar") || colType.contains("string")) {
                    colName to ColumnTypeEnum.STRING
                } else if (colType.contains("datetime") || colType.contains("date")) {
                    colName to ColumnTypeEnum.DATETIME
                } else if (colType.contains(" bitmap")) {
                    colName to ColumnTypeEnum.BITMAP
                } else {
                    colName to ColumnTypeEnum.STRING
                }
            }
        val typeToLineOrderColumnMap = mutableMapOf<ColumnTypeEnum, MutableSet<String>>()
        lineOrderColumnMap.map { (col, type) ->
            typeToLineOrderColumnMap.computeIfAbsent(type) {
                mutableSetOf<String>()
            }.add(col)
        }
        val result = mutableSetOf<String>()
        for ((funcName, reqTypes) in Enumerator.aggFuncs) {
            for (reqType in reqTypes) {
                if (!typeToLineOrderColumnMap.contains(reqType)) {
                    continue
                }
                typeToLineOrderColumnMap.get(reqType)!!
                    .filterIndexed { index, s -> index < 3 }
                    .map { col ->
                        result.add(funcName.replace("<col>", col))
                    }
            }
        }

        println(result)
       val query = """
select lo_orderdate, ${Joiner.on(",").join(result)}
from lineorder
group by lo_orderdate
        """.trimIndent()
        val queryWithRollup = """
select ${Joiner.on(",").join(result)}
from lineorder
        """.trimIndent()

        val mv = MMaterializedView(DEFAULT_MV_NAME, "lo_orderdate", query)
        withCompleteRefreshMV(mv) {
            // query with no rollup
            assertContains(queryWithRollup, DEFAULT_MV_NAME)
            assertEqualsWithMV(queryWithRollup)
            // query with rollup
        }
    }
}