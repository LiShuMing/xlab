package com.starrocks.itest

import java.nio.file.Paths
import kotlin.test.Test

class BasicTest {
    @Test
    fun testDir() {
        val path = Paths.get("").toAbsolutePath().toString()
        println(path)
        val resultPath = "$path/../result"
        val realPath = Paths.get(resultPath).toAbsolutePath().toString()
        println(realPath)
    }

    @Test
    fun testNonMatch() {
        var sql = ""
        for (i in 0..41) {
            if (i < 10){
                sql += "nmock_00${i}, "
            } else {
                sql += "nmock_0${i}, "
            }
        }
        println(sql)
    }
}