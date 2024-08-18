package com.starrocks.itest.mv.olap.createmv

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.TPCQuerySet
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Test
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream

class CreateMvWithTpchSuite: MVSuite() {
    private var loadData = false

    @BeforeAll
    override fun before() {
//        super.before()
//        useTpch1g(false)
    }

    fun getCreateMVTemplate(sql: String): String {
        return """
CREATE MATERIALIZED VIEW $DEFAULT_MV_NAME
DISTRIBUTED BY RANDOM
AS
$sql
            """
    }

    fun getParameters(): Stream<Arguments> {
        return TPCQuerySet.getTPCHQueryList()
            .stream()
            .map { (name, query) -> Arguments.of(name, query)}
    }

    @ParameterizedTest
    @MethodSource("getParameters")
    fun createMVWithTPCHQuerySetEmpty(name: String, query: String) {
        println("Test $name")
        val mvSql = getCreateMVTemplate(query)
        sql("DROP MATERIALIZED VIEW IF EXISTS ${DEFAULT_MV_NAME}")
        sql(mvSql)
        refreshMV(DEFAULT_MV_NAME)

        assertEqualQueryAndMVResult(query, DEFAULT_MV_NAME)
    }

    @ParameterizedTest
    @MethodSource("getParameters")
    fun createMVWithTPCHQuerySetAnd1GbData(name: String, query: String) {
        println("Test $name")
        if (!loadData) {
            useTpch1g(true)
            loadData = true
        }

        val mvSql = getCreateMVTemplate(query)
        sql("DROP MATERIALIZED VIEW IF EXISTS ${DEFAULT_MV_NAME}")
        sql(mvSql)
        refreshMV(DEFAULT_MV_NAME)

        assertEqualQueryAndMVResult(query, DEFAULT_MV_NAME)
    }

    @Test
    fun testIfAndCaseWhen() {
        useDB("test_tpcds_1g")
        dropMV(DEFAULT_MV_NAME)
        useTpch1g(true)
        val query = """
            CREATE MATERIALIZED VIEW $DEFAULT_MV_NAME
            DISTRIBUTED BY RANDOM
            AS
            select l_shipdate, count(distinct  if(l_orderkey>1000000,l_orderkey,null)) from lineitem group by l_shipdate
        """.trimIndent()
        sql(query)
        refreshMV(DEFAULT_MV_NAME)
        val sql = "select l_shipdate, count(distinct (case when(l_orderkey>1000000) then l_orderkey end)) from lineitem group by l_shipdate"
        assertEqualQueryAndMVResult(sql, DEFAULT_MV_NAME)
    }
}