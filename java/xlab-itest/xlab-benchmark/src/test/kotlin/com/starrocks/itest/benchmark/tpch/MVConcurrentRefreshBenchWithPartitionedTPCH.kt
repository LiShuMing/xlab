package com.starrocks.itest.benchmark.tpch

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class MVConcurrentRefreshBenchWithPartitionedTPCH : MVSuite()  {
    override var suiteDbName: String = "test_partitioned_tpch_1g"

    @BeforeAll
    override fun before() {
        super.before()
    }

    @Test
    fun createDefaultDbMVsWithOtherDB() {
        // create database
        useTpch1g(true, true, "tpch_1g_partitioned")
        sql("show tables")

        sql("admin  set frontend config ('mv_auto_analyze_async' = 'false');")
        sql("set global enable_profile = true;")

        // load data
        for (i in 0 until  1) {
            val createTableSql = Util.readContentFromResource("tpch_1g_partitioned/create_all_tpch_mvs_async.sql")
            val db = "test_db${i}"
            mustCreateAndUseDB(db)
            val sql = createTableSql.replace("<DB>", suiteDbName)
            sql(sql)
        }
    }

    @Test
    fun addMoreMvs2() {
        for (i in 1..5) {
            val createTableSql = Util.readContentFromResource("tpch_1g_partitioned/create_all_tpch_mvs_async_v2.sql")
            val db0 = "test_db${i}"
            val db = "test_nest_db${i}"
            mustCreateAndUseDB(db)
            val sql = createTableSql.replace("<DB>", db0)
            sql(sql)
        }
    }
}