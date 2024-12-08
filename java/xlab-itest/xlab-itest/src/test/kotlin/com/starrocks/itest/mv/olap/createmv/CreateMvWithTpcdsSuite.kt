package com.starrocks.itest.mv.olap.createmv

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.TPCQuerySet
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Order
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream

class CreateMvWithTpcdsSuite: MVSuite() {
    private var isLoadData = false

    @BeforeAll
    override fun before() {
        super.before()
        useTpcds1G(false)
    }

    fun getCreateMVTemplate(sql: String): String {
        return """
CREATE MATERIALIZED VIEW $DEFAULT_MV_NAME
DISTRIBUTED BY RANDOM
AS
${sql.trim()}
"""
    }

    fun getParameters(): Stream<Arguments> {
        return TPCQuerySet.getTPCDSQueryList()
            .stream()
            .filter { (name, query) ->
                println(name)
                !setOf("query39", "query64").contains(name)
            }.map { (name, query) ->
                Arguments.of(name, query)
            }
    }

//    override var suiteDbName = "test_tpcds_1g"

    @ParameterizedTest
    @MethodSource("getParameters")
    @Order(1)
    fun createMVWithTPCDSQuerySetEmpty(name: String, query: String) {
        println("Test $name")
        val mvSql = getCreateMVTemplate(query)
        sql("DROP MATERIALIZED VIEW IF EXISTS ${DEFAULT_MV_NAME}")
        sql(mvSql)
        refreshMV(DEFAULT_MV_NAME)

        assertEqualQueryAndMVResult(query, DEFAULT_MV_NAME)
    }

    @ParameterizedTest
    @MethodSource("getParameters")
    @Order(2)
    fun createMVWithTPCDSQuerySetAnd1GbData(name: String, query: String) {
        println("Test $name")
        if (!isLoadData) {
            useTpcds1G(true)
            isLoadData = true
        }
        val mvSql = getCreateMVTemplate(query)
        sql("DROP MATERIALIZED VIEW IF EXISTS ${DEFAULT_MV_NAME}")
        sql(mvSql)
        refreshMV(DEFAULT_MV_NAME)
        assertEqualQueryAndMVResult(query, DEFAULT_MV_NAME)
    }
}