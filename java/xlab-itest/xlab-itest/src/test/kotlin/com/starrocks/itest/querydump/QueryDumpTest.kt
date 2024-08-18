package com.starrocks.itest.querydump

import com.starrocks.itest.framework.Suite
import com.starrocks.itest.framework.utils.Util
import kotlin.test.Test

class QueryDumpTest : Suite() {
    @Test
    fun testQueryDump() {
        val str = Util.readContentFromCurrentResource("query_dump/test_grouping_sets.json")
//        println(str)

        var loop = false
        val lines = str.split("\n")
        for (line in lines) {
//            println(line)
            if (!loop && line.contains("table_meta")) {
                loop = true;
            } else if (loop && line.contains("table_row_count")) {
                loop = false
                break
            } else if (loop) {
                val arr = line.split(": ")
                if (arr.size == 2) {
                    val dbTable = arr[0].replace("\"", "")
                    dbTable.split(".").let {
//                        sql("create database if not exists ${it[0]}")
                        // sql("create table if not exists ${it[1]}")
                    }
//                    println(arr[1])
                    val sql = arr[1].replace("\\\"", "'")
                        .replace("\\n", " ")
                        .replace("`", "")
                        .replace("COMMENT\\s+'[^,]+'".toRegex(), "")
                        .replace("'replication_num' = '3', ", "")
                    println(sql)
//                    sql(sql)
                }
            }

        }
    }
}