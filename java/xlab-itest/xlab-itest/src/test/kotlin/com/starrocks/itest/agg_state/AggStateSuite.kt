package com.starrocks.itest.agg_state

import com.starrocks.itest.framework.MVSuite
import kotlin.test.Test

class AggStateSuite : MVSuite() {

    // Aggregate functions:
    val APPROX_COUNT_DISTINCT: String = "approx_count_distinct"
    val APPROX_TOP_K: String = "approx_top_k"
    val AVG: String = "avg"
    val COUNT: String = "count"
    val COUNT_IF: String = "count_if"
    val HLL_UNION_AGG: String = "hll_union_agg"
    val MAX: String = "max"
    val MAX_BY: String = "max_by"
    val MIN_BY: String = "min_by"
    val MIN: String = "min"
    val PERCENTILE_APPROX: String = "percentile_approx"
    val PERCENTILE_CONT: String = "percentile_cont"
    val PERCENTILE_DISC: String = "percentile_disc"
    val RETENTION: String = "retention"
    val STDDEV: String = "stddev"
    val STDDEV_POP: String = "stddev_pop"
    val STDDEV_SAMP: String = "stddev_samp"
    val SUM: String = "sum"
    val VARIANCE: String = "variance"
    val VAR_POP: String = "var_pop"
    val VARIANCE_POP: String = "variance_pop"
    val VAR_SAMP: String = "var_samp"
    val VARIANCE_SAMP: String = "variance_samp"
    val COVAR_POP: String = "covar_pop"
    val COVAR_SAMP: String = "covar_samp"
    val CORR: String = "corr"
    val ANY_VALUE: String = "any_value"
    val STD: String = "std"
    val HLL_UNION: String = "hll_union"
    val HLL_RAW_AGG: String = "hll_raw_agg"
    val HLL_RAW: String = "hll_raw"
    val HLL_EMPTY: String = "hll_empty"
    val NDV: String = "ndv"
    val MULTI_DISTINCT_COUNT: String = "multi_distinct_count"
    val MULTI_DISTINCT_SUM: String = "multi_distinct_sum"
    val DICT_MERGE: String = "dict_merge"
    val WINDOW_FUNNEL: String = "window_funnel"
    val DISTINCT_PC: String = "distinct_pc"
    val DISTINCT_PCSA: String = "distinct_pcsa"
    val HISTOGRAM: String = "histogram"

    fun prepare() {
        val ddl = """
 CREATE TABLE `t1` ( 
    `k1`  date, 
    `k2`  datetime,
    `k3`  char(20), 
    `k4`  varchar(20), 
    `k5`  boolean, 
    `k6`  tinyint, 
    `k7`  smallint, 
    `k8`  int, 
    `k9`  bigint, 
    `k10` largeint, 
    `k11` float, 
    `k12` double, 
    `k13` decimal(27,9)
) DUPLICATE KEY(`k1`, `k2`, `k3`, `k4`, `k5`) 
-- PARTITION BY date_trunc('day', %s) 
DISTRIBUTED BY HASH(`k1`, `k2`, `k3`) 
PROPERTIES (  "replication_num" = "1");
        """.trimIndent()
        sql(ddl)
        val data = """
insert into t1 values('2020-01-01', '2020-01-01 10:10:10', 'aaaa', 'aaaa', 0, 1, 1, 1, 1, 1, 1.11, 11.111, 111.1111),('2020-02-01', '2020-02-01 10:10:10', 'bbbb', 'bbbb', 0, 2, 2, 2, 2, 2, 2.22, 22.222, 222.2222);
        """.trimIndent()
        sql(data)
    }

    fun getNumericColumns(): Array<String> {
        return arrayOf("k6", "k7", "k8", "k9", "k10", "k11", "k12", "k13")
    }

    fun getStringColumns(): Array<String> {
        return arrayOf("k3", "k4")
    }

    fun getBooleanColumns(): Array<String> {
        return arrayOf("k5")
    }
    fun getDateTimeColumns(): Array<String> {
        return arrayOf("k2")
    }

    fun getDateColumns(): Array<String> {
        return arrayOf("k1")
    }

    fun getColumns(): Array<String> {
        return getNumericColumns() + getStringColumns() + getBooleanColumns() + getDateTimeColumns() + getDateColumns()
    }

    fun toAggState(agg:String, column: String): String {
        return "${agg}_state($column)"
    }
    fun toAggStateUnion(agg:String, column: String): String {
        return "${agg}_union($column)"
    }
    fun toAggStateMerge(agg:String, column: String): String {
        return "${agg}_merge($column)"
    }

    fun aggFuncsWihColumns(): Array<String> {
        return arrayOf(
            APPROX_COUNT_DISTINCT,
            APPROX_TOP_K,
            AVG,
            COUNT,
            COUNT_IF,
            HLL_UNION_AGG,
            MAX,
            MAX_BY,
            MIN_BY,
            MIN,
            PERCENTILE_APPROX,
            PERCENTILE_CONT,
            PERCENTILE_DISC,
            RETENTION,
            STDDEV,
            STDDEV_POP,
            STDDEV_SAMP,
            SUM,
            VARIANCE,
            VAR_POP,
            VARIANCE_POP,
            VAR_SAMP,
            VARIANCE_SAMP,
            COVAR_POP,
            COVAR_SAMP,
            CORR,
            ANY_VALUE,
            STD,
            HLL_UNION,
            HLL_RAW_AGG,
            HLL_RAW,
            HLL_EMPTY,
            NDV,
            MULTI_DISTINCT_COUNT,
            MULTI_DISTINCT_SUM,
            DICT_MERGE,
            WINDOW_FUNNEL,
            DISTINCT_PC,
            DISTINCT_PCSA,
            HISTOGRAM
        )
    }

    fun aggFuncsWihNumericColumns(): Array<String> {
        return arrayOf(
            AVG,
            COUNT_IF,
            HLL_UNION_AGG,
            MAX,
            MAX_BY,
            MIN_BY,
            MIN,
            PERCENTILE_APPROX,
            PERCENTILE_CONT,
            PERCENTILE_DISC,
            RETENTION,
            STDDEV,
            STDDEV_POP,
            STDDEV_SAMP,
            SUM,
            VARIANCE,
            VAR_POP,
            VARIANCE_POP,
            VAR_SAMP,
            VARIANCE_SAMP,
            COVAR_POP,
            COVAR_SAMP,
            CORR,
            ANY_VALUE,
            STD,
            HLL_UNION,
            HLL_RAW_AGG,
            HLL_RAW,
            HLL_EMPTY,
            NDV,
            MULTI_DISTINCT_COUNT,
            MULTI_DISTINCT_SUM,
            DICT_MERGE,
            WINDOW_FUNNEL,
            DISTINCT_PC,
            DISTINCT_PCSA,
            HISTOGRAM
        )
    }

    @Test
    fun testAggCount() {
        prepare()
        val columns = getColumns()
        columns.map { column ->
            val agg = COUNT
            val aggState = toAggState(agg, column)
            // test agg state
            sql("select $aggState from t1")
            // test agg state union
            val aggStateUnion = toAggStateUnion(agg, aggState)
            sql("select $aggState from t1")
            // test agg state union
            val aggStateMerge = toAggStateMerge(agg, aggStateUnion)
            sql("select $aggStateMerge from t1")
        }
    }
}