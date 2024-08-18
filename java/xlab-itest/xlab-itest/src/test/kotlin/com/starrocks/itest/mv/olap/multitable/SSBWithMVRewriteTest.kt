package com.starrocks.itest.mv.olap.multitable

import com.google.common.collect.ImmutableMap
import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream
import kotlin.test.Test

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
        val createTableSql = Util.readContentFromResource("ssb/create_table_date.sql")
        sql(createTableSql)

//        // add constraints
//        val addConstraintsSql = Util.readContentFromResource("ssb/add_constraints.sql")
//        sql(addConstraintsSql)

        // mock data
        val insertDataSql = Util.readContentFromResource("ssb/insert_date.sql")
        sql(insertDataSql)

//        // create mv
//        val createMVSql = Util.readContentFromResource("ssb/lineorder_flat_mv.sql")
//        sql(createMVSql)
//        refreshMV(SSB_FLAT_MV_NAME)
    }

    @AfterAll
    override fun after() {
        super.after()
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

    @Test
    fun testCountDistinctWithCount() {
        val v1 = """
create view v1 as
select count(distinct cnt)
from
(
select c_city, count(*) as cnt
from customer
group by c_city
) t;
        """.trimIndent()
        sql(v1)

        val mvName = "mv1"
        sql("drop materialized view if exists ${mvName};")
        sql("CREATE MATERIALIZED VIEW ${mvName} REFRESH ASYNC every (interval 10 minute) AS select * from v1;")
        refreshMV(mvName)
        assertContains("select * from v1", mvName)
    }

    val SAFE_REWRITE_ROLLUP_FUNCTION_MAP: Map<String, String> =
        ImmutableMap.builder<String, String>() // Functions and rollup functions are the same.
            .put("SUM", "SUM")
            .put("MAX", "MAX")
            .put("MIN", "MIN")
            .put("BITMAP_UNION", "BITMAP_UNION")
            .put("HLL_UNION", "HLL_UNION")
            .put("PERCENTILE_UNION", "PERCENTILE_UNION")
            .put("ANY_VALUE", "ANY_VALUE") // Functions and rollup functions are not the same.
            .put("BITMAP_AGG", "BITMAP_UNION")
            .put("ARRAY_AGG_DISTINCT", "ARRAY_UNIQUE_AGG")
            .build()


    private fun getAggFunction(funcName: String, aggArg: String): String {
        var funcName = funcName
        funcName = if (funcName == "ARRAY_AGG") {
            String.format("array_agg(distinct %s)", aggArg)
        } else if (funcName == "BITMAP_UNION") {
            String.format("bitmap_union(to_bitmap(%s))", aggArg)
        } else if (funcName == "PERCENTILE_UNION") {
            String.format("percentile_union(percentile_hash(%s))", aggArg)
        } else if (funcName == "HLL_UNION") {
            String.format("hll_union(hll_hash(%s))", aggArg)
        } else {
            String.format("%s(%s)", funcName, aggArg)
        }
        return funcName
    }


    @Test
    fun testAggPushDownJoin_Basic() {
        sql("set enable_materialized_view_agg_pushdown_rewrite = true;")
        for ((k, v) in SAFE_REWRITE_ROLLUP_FUNCTION_MAP) {
            val func = getAggFunction(k, "LO_REVENUE")
            sql("drop materialized view if exists ${DEFAULT_MV_NAME}")
            sql("CREATE MATERIALIZED VIEW ${DEFAULT_MV_NAME} REFRESH DEFERRED MANUAL as  select LO_ORDERDATE, ${func} as revenue_sum from lineorder l group by LO_ORDERDATE;")
            refreshMV(DEFAULT_MV_NAME)
            val query = "select LO_ORDERDATE, ${func} as revenue_sum\n from lineorder l join dates d on l.LO_ORDERDATE = d.d_date group by LO_ORDERDATE"
            assertContains("${query}", DEFAULT_MV_NAME)
        }
    }

    @Test
    fun testAggPushDown_Basic2() {
        for ((k, v) in SAFE_REWRITE_ROLLUP_FUNCTION_MAP) {
            val func = getAggFunction(k, "LO_REVENUE")
            sql("drop materialized view if exists ${DEFAULT_MV_NAME}")
            sql("CREATE MATERIALIZED VIEW ${DEFAULT_MV_NAME} REFRESH DEFERRED MANUAL as  select LO_ORDERDATE, ${func} as revenue_sum from lineorder l group by LO_ORDERDATE;")
            refreshMV(DEFAULT_MV_NAME)
            val query = "select LO_ORDERDATE, ${func} as revenue_sum\n from lineorder l join dates d on l.LO_ORDERDATE = d.d_date group by LO_ORDERDATE"
            assertEqualQueryAndMVResultWithConfig(query, "enable_materialized_view_agg_pushdown_rewrite")
        }
    }
}