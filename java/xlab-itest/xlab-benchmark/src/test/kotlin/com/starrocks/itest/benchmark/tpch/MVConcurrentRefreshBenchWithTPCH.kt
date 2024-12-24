package com.starrocks.itest.benchmark.tpch

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class MVConcurrentRefreshBenchWithTPCH : MVSuite()  {
    override var suiteDbName: String = "test_tpch_1g"

    @BeforeAll
    override fun before() {
        super.before()
    }

    @Test
    fun updateBaseTables() {
        while (true) {
            val sql = """
INSERT INTO ${suiteDbName}.lineitem (L_ORDERKEY, L_PARTKEY, L_SUPPKEY, L_LINENUMBER, L_QUANTITY, L_EXTENDEDPRICE, L_DISCOUNT, L_TAX, L_RETURNFLAG, L_LINESTATUS, L_SHIPDATE, L_COMMITDATE, L_RECEIPTDATE, L_SHIPINSTRUCT, L_SHIPMODE, L_COMMENT) VALUES
(1, 101, 201, 1, 10.5, 150.75, 0.05, 0.02, 'R', 'F', '2023-01-01', '2023-01-02', '2023-01-03', 'Air', 'Express', 'Sample comment for lineitem 1'),
(2, 102, 202, 2, 15.2, 200.45, 0.08, 0.03, 'N', 'O', '2023-02-01', '2023-02-02', '2023-02-03', 'Ground', 'Regular', 'Sample comment for lineitem 2'),
(3, 103, 203, 3, 20.8, 300.60, 0.10, 0.04, 'A', 'F', '2023-03-01', '2023-03-02', '2023-03-03', 'Sea', 'Express', 'Sample comment for lineitem 3');
        """.trimIndent()
            sql(sql)
            Thread.sleep(10000)
        }
    }

    @Test
    fun createDefaultDbMVsWithOtherDB() {
        // create database
        useTpch1g(true, true)
        sql("show tables")
        // load data
        for (i in 0..1) {
            val createTableSql = Util.readContentFromResource("tpch_1g/create_all_tpch_mvs_async.sql")
            val db = "test_db${i}"
            mustCreateAndUseDB(db)
            val sql = createTableSql.replace("<DB>", suiteDbName)
            sql(sql)
        }
    }

    @Test
    fun addMoreMvs() {
        for (i in 1..5) {
            val createTableSql = Util.readContentFromResource("tpch_1g/create_all_tpch_mvs_async_v2.sql")
            val db0 = "test_db${i}"
            val db = "test_nest_db${i}"
            mustCreateAndUseDB(db)
            val sql = createTableSql.replace("<DB>", db0)
            sql(sql)
        }
    }
}