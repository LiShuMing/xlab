package com.starrocks.itest.benchmark.cases.refresh

import com.starrocks.itest.framework.MVSuite
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.Arguments
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream
import kotlin.test.Ignore

@Ignore
class HiveRefreshMultiMVsBench: MVSuite() {
    private val MV_NAME = "lineorder_flat_mv"

    @BeforeAll
    override fun before() {
        super.before()
        prepareHiveCatalog()
    }

    fun prepareHiveCatalog() {
        // TODO: make it configurable
        if (!catalogExists("hive")) {
            sql("create external catalog hive PROPERTIES(\"type\" = \"hive\", \"hive.metastore.uris\" = \"thrift://172.26.194.238:9083\");")
        }
    }

    val HIVE_SSB_DB = "hive.ssb_100g_orc_zlib"

    fun getMvName(i: Int): String {
        return "${MV_NAME}_${i}"
    }

    fun getSSBMVDefine(i: Int): String {
        return "CREATE MATERIALIZED VIEW ${getMvName(i)}\n" +
                "DISTRIBUTED BY HASH(LO_ORDERDATE, LO_ORDERKEY) BUCKETS 48\n" +
                "REFRESH DEFERRED MANUAL\n" +
                "PROPERTIES (\n" +
                "    \"replication_num\" = \"1\"\n" +
                ")" +
                "AS SELECT\n" +
                "       l.LO_ORDERKEY AS LO_ORDERKEY,\n" +
                "       l.LO_LINENUMBER AS LO_LINENUMBER,\n" +
                "       l.LO_CUSTKEY AS LO_CUSTKEY,\n" +
                "       l.LO_PARTKEY AS LO_PARTKEY,\n" +
                "       l.LO_SUPPKEY AS LO_SUPPKEY,\n" +
                "       l.LO_ORDERDATE AS LO_ORDERDATE,\n" +
                "       l.LO_ORDERPRIORITY AS LO_ORDERPRIORITY,\n" +
                "       l.LO_SHIPPRIORITY AS LO_SHIPPRIORITY,\n" +
                "       l.LO_QUANTITY AS LO_QUANTITY,\n" +
                "       l.LO_EXTENDEDPRICE AS LO_EXTENDEDPRICE,\n" +
                "       l.LO_ORDTOTALPRICE AS LO_ORDTOTALPRICE,\n" +
                "       l.LO_DISCOUNT AS LO_DISCOUNT,\n" +
                "       l.LO_REVENUE AS LO_REVENUE,\n" +
                "       l.LO_SUPPLYCOST AS LO_SUPPLYCOST,\n" +
                "       l.LO_TAX AS LO_TAX,\n" +
                "       l.LO_COMMITDATE AS LO_COMMITDATE,\n" +
                "       l.LO_SHIPMODE AS LO_SHIPMODE,\n" +
                "       c.C_NAME AS C_NAME,\n" +
                "       c.C_ADDRESS AS C_ADDRESS,\n" +
                "       c.C_CITY AS C_CITY,\n" +
                "       c.C_NATION AS C_NATION,\n" +
                "       c.C_REGION AS C_REGION,\n" +
                "       c.C_PHONE AS C_PHONE,\n" +
                "       c.C_MKTSEGMENT AS C_MKTSEGMENT,\n" +
                "       s.S_NAME AS S_NAME,\n" +
                "       s.S_ADDRESS AS S_ADDRESS,\n" +
                "       s.S_CITY AS S_CITY,\n" +
                "       s.S_NATION AS S_NATION,\n" +
                "       s.S_REGION AS S_REGION,\n" +
                "       s.S_PHONE AS S_PHONE,\n" +
                "       p.P_NAME AS P_NAME,\n" +
                "       p.P_MFGR AS P_MFGR,\n" +
                "       p.P_CATEGORY AS P_CATEGORY,\n" +
                "       p.P_BRAND AS P_BRAND,\n" +
                "       p.P_COLOR AS P_COLOR,\n" +
                "       p.P_TYPE AS P_TYPE,\n" +
                "       p.P_SIZE AS P_SIZE,\n" +
                "       p.P_CONTAINER AS P_CONTAINER,\n" +
                "       d.d_date AS d_date,\n" +
                "       d.d_dayofweek AS d_dayofweek,\n" +
                "       d.d_month AS d_month,\n" +
                "       d.d_year AS d_year,\n" +
                "       d.d_yearmonthnum AS d_yearmonthnum,\n" +
                "       d.d_yearmonth AS d_yearmonth,\n" +
                "       d.d_daynuminweek AS d_daynuminweek,\n" +
                "       d.d_daynuminmonth AS d_daynuminmonth,\n" +
                "       d.d_daynuminyear AS d_daynuminyear,\n" +
                "       d.d_monthnuminyear AS d_monthnuminyear,\n" +
                "       d.d_weeknuminyear AS d_weeknuminyear,\n" +
                "       d.d_sellingseason AS d_sellingseason,\n" +
                "       d.d_lastdayinweekfl AS d_lastdayinweekfl,\n" +
                "       d.d_lastdayinmonthfl AS d_lastdayinmonthfl,\n" +
                "       d.d_holidayfl AS d_holidayfl,\n" +
                "       d.d_weekdayfl AS d_weekdayfl\n" +
                "   FROM ${HIVE_SSB_DB}.lineorder AS l\n" +
                "            INNER JOIN ${HIVE_SSB_DB}.customer AS c ON c.C_CUSTKEY = l.LO_CUSTKEY\n" +
                "            INNER JOIN ${HIVE_SSB_DB}.supplier AS s ON s.S_SUPPKEY = l.LO_SUPPKEY\n" +
                "            INNER JOIN ${HIVE_SSB_DB}.part AS p ON p.P_PARTKEY = l.LO_PARTKEY\n" +
                "            INNER JOIN ${HIVE_SSB_DB}.dates AS d ON l.lo_orderdate = d.d_datekey;\n"
    }

    private fun getParameters(): Stream<Arguments> {
        return (0..10).map{x -> Arguments.of(x)}.stream()
    }

    @ParameterizedTest
    @MethodSource("getParameters")
    fun testRefreshHiveSSB(mvNum: Int) {
        for (i in 0 until mvNum) {
            val mvSql = getSSBMVDefine(i)
            sql(mvSql)
        }

        // refresh
        for (i in 0 until mvNum) {
            val mvName = getMvName(i)
            refreshMV(mvName, syncMode = false)
        }

        // wait ready
        for (i in 0 until  mvNum) {
            val mvName = getMvName(i)
            untilMVReady(mvName)
        }
    }
}