package com.starrocks.itest.mv

import com.google.common.base.Joiner
import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import com.starrocks.schema.MSchema
import kotlin.test.Test

class ManualSuite : MVSuite() {

    @Test
    fun testBasic1() {
        repeat (1) {
            sql("drop table if exists t1")
            sql("create table t1 (a int,b int);")
            sql("insert into t1 values (1,1);")
            sql("drop materialized view if exists mv1;")
            sql("create materialized view mv1 refresh manual as select a,sum(b) from t1 group by a;")
            untilMVReady("mv1")
            sql("select * from t1")
        }
    }

    @Test
    fun testMVWithEmptyPartition() {
        val tbl = MSchema.TABLE_WITH_DAY_PARTITION
        withMTable(tbl) {
            withCompleteRefreshMV(
                DEFAULT_MV_NAME, "id_date",
                "select id_date, sum(t1b) from ${MSchema.TABLE_WITH_DAY_PARTITION.tableName} group by id_date"
            ) {

                val partValues = arrayOf(
                    "1991-03-31",
                    "1991-04-01",
                    "1991-04-02",
                    "1991-04-03",
                )
                val parts = Joiner.on("\',\'").join(partValues)
                val sql = "select id_date, sum(t1b) from ${MSchema.TABLE_WITH_DAY_PARTITION.tableName} " +
                        " where id_date in ('${parts}')" +
                        " group by id_date"
                assertContains(sql, DEFAULT_MV_NAME)
            }
        }
    }

    @Test
    fun readConfFile() {
        val confFile = Util.loadConfig("../conf/sr.conf")
        println(confFile)
    }

    @Test
    fun testCase1() {
        useDB("test")
//        sql("CREATE TABLE IF NOT EXISTS test_order (\n" +
//                "id varchar(150) NOT NULL COMMENT '',\n" +
//                "reset_period_data varchar(32) NULL COMMENT \"\"\n" +
//                ") ENGINE=olap PRIMARY KEY (id) COMMENT '' DISTRIBUTED BY HASH(id) BUCKETS 3 PROPERTIES(\"enable_persistent_index\" = \"true\", \"replication_num\" = \"1\");\n")
//        sql("insert into test_order values('1','2023-10-11 00:00:01.030'), ('2','2023-10-11 00:00:01.031'), ('3','2023-10-13 00:00:01.031'), ('4','2023-10-14 00:00:01.031')")
//
        sql("set new_planner_agg_stage = 3;")
        repeat(100, {
           val result = query("select str_to_jodatime('2024-04-01', 'yyyy-MM-dd'), DATE_FORMAT(reset_period_data, '%Y-%m-%d') from test_order group by DATE_FORMAT(reset_period_data, '%Y-%m-%d');")
            println(result)
        })
    }
}