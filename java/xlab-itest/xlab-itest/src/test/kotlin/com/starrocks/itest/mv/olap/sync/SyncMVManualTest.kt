package com.starrocks.itest.mv.olap.sync

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class SyncMVManualTest : MVSuite() {
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
    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_datetime.sql")
        sql(createTableSql)
    }

    override fun after() {
         super.after()
    }

    @Test
    fun testMVWithCountDistinct() {
        val mv = """
            create materialized view sync_mv0 as select lo_orderdate, bitmap_union(bitmap_hash(lo_orderpriority)), sum(lo_linenumber), count(lo_linenumber)
            from lineorder
            group by lo_orderdate;
        """.trimIndent()
        sql(mv)

        untilSyncMVReady()

        val query = "select lo_orderdate, count(distinct lo_orderpriority), avg(lo_linenumber) from lineorder group by lo_orderdate"
        explain(query)
    }
}