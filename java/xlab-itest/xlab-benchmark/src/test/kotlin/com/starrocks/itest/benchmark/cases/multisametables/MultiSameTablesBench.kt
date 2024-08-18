package com.starrocks.itest.benchmark.cases.multisametables

import com.carrotsearch.junitbenchmarks.BenchmarkOptions
import com.google.common.collect.Lists
import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import com.starrocks.schema.MSSBSchema
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream

class MultiSameTablesBench : MVSuite() {

    private val MV_NAME = "lineorder_flat_mv"

    private fun getMVName(i: Int): String {
        return "${MV_NAME}_${i}"
    }

    @BeforeAll
    override fun before() {
        super.before()

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
    }

    @AfterAll
    override fun after() {
        super.after()
    }

    private fun getMVDefine(i: Int, query: String): String {
        return "CREATE MATERIALIZED VIEW ${MV_NAME}_${i}\n" +
                "DISTRIBUTED BY RANDOM \n" +
                "PARTITION BY (lo_orderdate) \n" +
                "REFRESH DEFERRED MANUAL\n" +
                "AS $query"
    }

    private val lineorder = MSSBSchema.LINEORDER.withProperties(Lists.newArrayList());
    private val customer = MSSBSchema.CUSTOMER
    private val dates = MSSBSchema.DATES
    private val supplier = MSSBSchema.SUPPLIER
    private val part = MSSBSchema.PART
    private val JOIN_TYPE = "inner"

    private fun generateMultiJoinsQuery(tableNum: Int): String {
        val multiJoinQuerySB = StringBuilder()
        // TODO: simple join + agg
        multiJoinQuerySB.append("SELECT lo_orderdate, count(*) FROM \n")
        multiJoinQuerySB.append("${lineorder.tableName} ")

        multiJoinQuerySB.append(" ${JOIN_TYPE} join ${customer.tableName} on ${customer.tableName}.C_CUSTKEY=${lineorder.tableName}.LO_CUSTKEY\n")
        multiJoinQuerySB.append(" ${JOIN_TYPE} join ${dates.tableName} on ${dates.tableName}.D_DATEKEY=${lineorder.tableName}.LO_ORDERDATE\n")
        multiJoinQuerySB.append(" ${JOIN_TYPE} join ${supplier.tableName} on ${supplier.tableName}.S_SUPPKEY=${lineorder.tableName}.LO_SUPPKEY\n")
        multiJoinQuerySB.append(" ${JOIN_TYPE} join ${part.tableName} on ${part.tableName}.P_PARTKEY=${lineorder.tableName}.LO_PARTKEY\n")

        for (i in 0.. tableNum) {
            val c1 = customer
            multiJoinQuerySB.append(" ${JOIN_TYPE} join ${c1.tableName} as c${i} on c${i}.C_CUSTKEY=${lineorder.tableName}.LO_CUSTKEY\n")
        }
        multiJoinQuerySB.append("GROUP BY lo_orderdate")

        val multiJoinsQuery = multiJoinQuerySB.toString()
        println(multiJoinsQuery)
        return multiJoinsQuery
    }

    private fun testMultiJoinsWithTableNum(tableNum: Int) {
        val multiJoinsQuery = generateMultiJoinsQuery(tableNum)
        val realTableNum = 1 + tableNum

        val mvName = getMVName(tableNum)
        sql("drop materialized view if exists ${mvName}")
        val mvDefine = getMVDefine(tableNum, multiJoinsQuery)
        sql(mvDefine)

        refreshMV(mvName)

        rdExplainTime(multiJoinsQuery, "explain join with the same table with multiplier ${realTableNum}")
        assertContains(multiJoinsQuery, mvName)
        //rdSql(multiJoinsQuery, "query multi joins(mv) with multiplier ${realTableNum}")
    }

    private fun multiJoinParameters(): Stream<Arguments> {
        return (0..10).map{x -> Arguments.of(x)}.stream()
    }

    @ParameterizedTest
    @MethodSource("multiJoinParameters")
    fun testMultiJoinsWithMV(i: Int) {
        testMultiJoinsWithTableNum(i)
    }

    val defaultMultiJoinsQuery = generateMultiJoinsQuery(10)
    @org.junit.jupiter.api.Test
    @BenchmarkOptions(warmupRounds = 1, benchmarkRounds = 10)
    fun testExplainBench() {
        rdExplainTime(defaultMultiJoinsQuery)
    }
}