package com.starrocks.itest.mv.external


import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.Suite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class HiveSingleTableManual2Suite : MVSuite() {
    @BeforeAll
    override fun before() {
        super.before()
//        val createTableSql = Util.readContentFromResource("materialization/hive_2.sql")
//        sql(createTableSql)
    }

    override fun after() {
         super.after()
    }

    @Test
    fun testPartitionMVWithEmptyPartition1() {
        val sql =
            """
                create materialized view ${DEFAULT_MV_NAME}
                distributed by random
                partition by str2date(dt,'%Y-%m-%d-%H')
                as select * from hive.hive_mv_test.tbl1
            """.trimIndent()
        sql(sql)
        refreshMV(DEFAULT_MV_NAME)
    }
}