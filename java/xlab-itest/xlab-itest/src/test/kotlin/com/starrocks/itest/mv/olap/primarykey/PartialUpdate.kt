package com.starrocks.itest.mv.olap.primarykey

import com.starrocks.itest.framework.MVSuite
import org.junit.jupiter.api.Test

class PartialUpdate : MVSuite() {

    @Test
    fun testPartialUpdate1(){
        val cols = mutableListOf<String>()
        for (i in 0..1000) {
            cols.add("col$i varchar(1024)")
        }
        sql("drop table if exists pk_tbl_with_1000_cols")
        val template = """
           CREATE TABLE IF NOT EXISTS pk_tbl_with_1000_cols ( 
           ${cols.joinToString(",\n")}
) PRIMARY KEY(col0) 
DISTRIBUTED BY HASH(col0) BUCKETS 3 
PROPERTIES ( "replication_num" = "1");
            """
        println(template)
        sql(template)
        for (i in 0..1000) {
            val insertSql = generateInsertSql(i)
            sql(insertSql)
            if (i > 10) {
                val updateSql = generateUpdatetSql(i)
                println(updateSql)
                sql(updateSql)
            }
        }
    }

    fun generateInsertSql(i: Int): String {
        val cols = mutableListOf<String>()
        for (j in 0..1000) {
            cols.add("'$i'")
        }
        return "INSERT INTO pk_tbl_with_1000_cols VALUES (${cols.joinToString(",")});"
    }

    fun generateUpdatetSql(i: Int): String {
        return "UPDATE pk_tbl_with_1000_cols SET col$i = NULL WHERE col$i is not null;"
    }

}