package com.starrocks.itest.benchmark.cases.multijoins

import com.carrotsearch.junitbenchmarks.BenchmarkOptions
import com.google.common.collect.Lists
import com.starrocks.itest.framework.MVSuite
import com.starrocks.schema.MSSBSchema
import com.starrocks.schema.MTable
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Test
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream

class MultiJoinsBench : MVSuite() {
    private val MV_NAME = "lineorder_flat_mv"

    private fun getMVName(i: Int): String {
        return "${MV_NAME}_${i}"
    }

    @BeforeAll
    override fun before() {
        super.before()
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

    private fun generateMultiJoinsRequiredTables(tableNum: Int): List<MTable> {
        val reqTables = Lists.newArrayList<MTable>()
        reqTables.add(lineorder)

        for (i in 0.. tableNum) {
            reqTables.add(customer.copyWithName("customer_$i"))
            reqTables.add(dates.copyWithName("dates_$i"))
            reqTables.add(supplier.copyWithName("supplier_$i"))
            reqTables.add(part.copyWithName("part_$i"))
        }
        return reqTables
    }

    private fun generateMultiJoinsQuery(tableNum: Int): String {
        val multiJoinQuerySB = StringBuilder()
        // TODO: simple join + agg
        multiJoinQuerySB.append("SELECT lo_orderdate, count(*) FROM \n")
        multiJoinQuerySB.append("${lineorder.tableName} ")
        for (i in 0.. tableNum) {
            val c1 = customer.copyWithName("customer_$i")
            val d1 = dates.copyWithName("dates_$i")
            val s1 = supplier.copyWithName("supplier_$i")
            val p1 = part.copyWithName("part_$i")
            multiJoinQuerySB.append(" ${JOIN_TYPE} join ${c1.tableName} on ${c1.tableName}.C_CUSTKEY=${lineorder.tableName}.LO_CUSTKEY\n")
            multiJoinQuerySB.append(" ${JOIN_TYPE} join ${d1.tableName} on ${d1.tableName}.D_DATEKEY=${lineorder.tableName}.LO_ORDERDATE\n")
            multiJoinQuerySB.append(" ${JOIN_TYPE} join ${s1.tableName} on ${s1.tableName}.S_SUPPKEY=${lineorder.tableName}.LO_SUPPKEY\n")
            multiJoinQuerySB.append(" ${JOIN_TYPE} join ${p1.tableName} on ${p1.tableName}.P_PARTKEY=${lineorder.tableName}.LO_PARTKEY\n")
        }
        multiJoinQuerySB.append("GROUP BY lo_orderdate")

        val multiJoinsQuery = multiJoinQuerySB.toString()
        println(multiJoinsQuery)
        return multiJoinsQuery
    }

    private fun testMultiJoinsWithTableNum(tableNum: Int) {
        val reqTables = generateMultiJoinsRequiredTables(tableNum)
        for (mtable in reqTables) {
            sql(mtable, true)
        }

        val multiJoinsQuery = generateMultiJoinsQuery(tableNum)
        val realTableNum = 1 + (4 * (tableNum + 1))

        val mvName = getMVName(0)
        sql("drop materialized view if exists ${mvName}")
        val mvDefine = getMVDefine(0, multiJoinsQuery)
        sql(mvDefine)

        refreshMV(mvName)

        rdExplainTime(multiJoinsQuery, "multi joins time with tables(num=${realTableNum}) cost(ms)")
        rdContent(if (isContains(multiJoinsQuery, mvName)) "hit mv" else "no hit mv")
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

    @Test
    @BenchmarkOptions(warmupRounds = 1, benchmarkRounds = 10)
    fun testExplainBench() {
        val multiJoinsQuery = generateMultiJoinsQuery(10)
        explain(multiJoinsQuery)
    }
}