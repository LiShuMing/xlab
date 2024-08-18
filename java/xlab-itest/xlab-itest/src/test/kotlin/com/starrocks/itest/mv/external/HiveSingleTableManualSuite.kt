package com.starrocks.itest.mv.external


import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.Suite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class HiveSingleTableManualSuite : MVSuite() {
    @BeforeAll
    override fun before() {
        super.before()
//        val createTableSql = Util.readContentFromResource("materialization/hive_1.sql")
//        sql(createTableSql)
    }

    override fun after() {
         super.after()
    }

    @Test
    fun testPartitionMVWithEmptyPartition0() {
        val sql =
            """
                create materialized view ${DEFAULT_MV_NAME}
                distributed by random
                partition by str2date(dt,'%Y-%m-%d')
                properties('partition_ttl_number'='1')
                as select * from hive.hive_mv_test.tbl1
            """.trimIndent()
        sql(sql)
        refreshMV(DEFAULT_MV_NAME)
    }

    @Test
    fun testPartitionMVWithEmptyPartition1() {
        val sql = "select * from hive.hive_mv_test.tbl2"
        withCompleteRefreshMV(DEFAULT_MV_NAME, "dt", sql) {
            assertContains(sql, DEFAULT_MV_NAME)
            val partValues = arrayOf(
                "2023-09-24",
                "2023-09-25",
                "2023-09-26",
                "2023-09-27",
            )
            val newQuery = "select * from hive.hive_mv_test.tbl2 where dt in (${generatePartitionValues(partValues)})"
            assertContains(newQuery, DEFAULT_MV_NAME)
        }
    }

    @Test
    fun testPartitionMVWithEmptyPartition2() {
        setIsDevEnv()
        val sql = "select * from hive.hive_mv_test.tbl1"
        withCompleteRefreshMV(DEFAULT_MV_NAME, "str2date(dt, '%Y%m%d')", sql) {
            assertContains(sql, DEFAULT_MV_NAME)
            val partValues = arrayOf(
                "20230924",
                "20230925",
                "20230926",
                "20230927",
            )
            val newQuery = "select * from hive.hive_mv_test.tbl1 where dt in (${generatePartitionValues(partValues)})"
            assertContains(newQuery, DEFAULT_MV_NAME)
        }
    }

    @Test
    fun testPartitionMVWithEmptyPartition3() {
        setIsDevEnv()
        val sql = "select dt, sum(d), count(b) from hive.hive_mv_test.tbl1 group by dt "
        withMV(DEFAULT_MV_NAME, "str2date(dt, '%Y%m%d')", sql) {
            assertContains(sql, DEFAULT_MV_NAME)
            refreshMV(DEFAULT_MV_NAME, "20230928", "20230929")
            val partValues = arrayOf(
                "20230924",
                "20230925",
                "20230926",
                "20230927",
            )
            val newQuery = "select dt, sum(d), count(b) from hive.hive_mv_test.tbl1  " +
                    "where dt in (${generatePartitionValues(partValues)}) group by dt "
            assertContains(newQuery, DEFAULT_MV_NAME)
        }
    }
}