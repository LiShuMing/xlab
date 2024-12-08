package com.starrocks.itest.mv.external

import com.starrocks.itest.framework.MVSuite
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class HiveSSBSuite : MVSuite() {
    val SSB_DB = "ssb_1g_orc"

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
    private val singleTableSqls = arrayOf(
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
    )

    val SSB_TABLE_MAPPING = mapOf("lineorder" to "hive.${SSB_DB}.lineorder")

    val hiveSingleTableSqls = singleTableSqls.map{x ->
        var r = ""
        for (e in SSB_TABLE_MAPPING.entries) {
            r = x.replace(" ${e.key}", " ${e.value}")
        }
        r
    }.toList()

    @BeforeAll
    override fun before() {
        super.before()
    }

    override fun after() {
         super.after()
    }

    @Test
    fun testHiveCreateMVWithSingleTableBaseQueries() {
        // test base query
        for (sql in hiveSingleTableSqls) {
            withCompleteRefreshMV(DEFAULT_MV_NAME, "dt", sql, {
                assertContains(sql, "test0")
            })
            break
        }
    }
}