package com.starrocks.itest.benchmark.ssb

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream

class SSBWithMVRewriteTest : MVSuite() {
    val SSB_FLAT_MV_NAME = "lineorder_flat_mv"
    val SSB_SQLS = arrayOf(
        "q1-1.sql", // 0
        "q1-2.sql", // 1
        "q1-3.sql", // 2

        "q2-1.sql", // 3
        "q2-2.sql", // 4
        "q2-3.sql", // 5

        "q3-1.sql", // 6
        "q3-2.sql", // 7
        "q3-3.sql", // 8
        "q3-4.sql", // 9
        "q4-1.sql", // 10
        "q4-2.sql", // 11
        "q4-3.sql", // 12
    )

    @BeforeAll
    override fun before() {
        super.before()

        // create base tables
        val createTableSql = Util.readContentFromResource("ssb/create_table.sql")
        sql(createTableSql)

        // add constraints
        val addConstraintsSql = Util.readContentFromResource("ssb/add_constraints.sql")
        sql(addConstraintsSql)

        // mock data
        val insertDataSql = Util.readContentFromResource("ssb/insert.sql")
        sql(insertDataSql)

        // create mv
        val createMVSql = Util.readContentFromResource("ssb/lineorder_flat_mv.sql")
        sql(createMVSql)
        refreshMV(SSB_FLAT_MV_NAME)
    }

    @AfterAll
    override fun after() {
//        super.after()
    }

    private fun getMethodSource(): Stream<Arguments> {
        return (0..12).map{x -> Arguments.of(x)}.stream()
    }

    @ParameterizedTest
    @MethodSource("getMethodSource")
    fun testQueries0() {
        val query = Util.readContentFromResource("ssb/${SSB_SQLS[0]}")
        assertContains(query, SSB_FLAT_MV_NAME)
    }
}