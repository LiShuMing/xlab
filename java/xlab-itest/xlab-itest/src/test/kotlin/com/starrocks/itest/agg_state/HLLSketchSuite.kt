package com.starrocks.itest.agg_state

import com.google.common.base.Joiner
import com.starrocks.itest.framework.MVSuite
import kotlin.system.measureNanoTime
import kotlin.test.Test
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.DurationUnit
import kotlin.time.toDuration

class HLLSketchSuite : MVSuite() {

    fun prepare1() {
        val ddl = """
CREATE TABLE t1 (
  id BIGINT NOT NULL,
  province VARCHAR(64),
  age SMALLINT,
  dt VARCHAR(10) NOT NULL 
)
DUPLICATE KEY(id)
-- PARTITION BY (province, dt) 
DISTRIBUTED BY HASH(id) BUCKETS 16;
        """.trimIndent()
        sql(ddl)
        val data = """
insert into t1 select generate_series, generate_series, generate_series % 100, "2024-07-24" from table(generate_series(1, 100000000));
        """.trimIndent()
        sql(data)
    }

    fun prepare2() {
        val ddl = """
CREATE TABLE t2 (
  id BIGINT NOT NULL,
  province VARCHAR(64),
  age SMALLINT,
  dt VARCHAR(10) NOT NULL 
)
DUPLICATE KEY(id)
-- PARTITION BY (province, dt) 
DISTRIBUTED BY RANDOM BUCKETS 16;
        """.trimIndent()
        sql(ddl)
        val data = """
insert into t2 select generate_series, generate_series, generate_series % 100, "2024-07-24" from table(generate_series(1, 100000000));
        """.trimIndent()
        sql(data)
    }

    fun prepare3() {
        val ddl = """
CREATE TABLE t3 (
  id BIGINT NOT NULL,
  province VARCHAR(64),
  age SMALLINT,
  dt VARCHAR(10) NOT NULL 
)
DUPLICATE KEY(id)
-- PARTITION BY (province, dt) 
DISTRIBUTED BY RANDOM BUCKETS 16;
        """.trimIndent()
        sql(ddl)
        val data = """
insert into t3 select generate_series % 100, generate_series, generate_series % 100, "2024-07-24" from table(generate_series(1, 100000000));
        """.trimIndent()
        sql(data)
    }

    fun prepare4() {
        val ddl = """
CREATE TABLE t4 (
  id BIGINT NOT NULL,
  province VARCHAR(64),
  age SMALLINT,
  dt VARCHAR(10) NOT NULL 
)
DUPLICATE KEY(id)
-- PARTITION BY (province, dt) 
DISTRIBUTED BY RANDOM BUCKETS 16;
        """.trimIndent()
        sql(ddl)
        val data = """
insert into t4 select generate_series % 10000, generate_series, generate_series % 100, "2024-07-24" from table(generate_series(1, 100000000));
        """.trimIndent()
        sql(data)
    }

//    fun prepare5() {
//        val ddl = """
//CREATE TABLE t5 (
//  id BIGINT NOT NULL,
//  province VARCHAR(64),
//  age SMALLINT,
//  dt VARCHAR(10) NOT NULL
//)
//DUPLICATE KEY(id)
//-- PARTITION BY (province, dt)
//DISTRIBUTED BY RANDOM BUCKETS 16;
//        """.trimIndent()
//        sql(ddl)
//        val data = """
//insert into t5 select generate_series % 10000, generate_series % 10000, generate_series % 100, "2024-07-24" from table(generate_series(1, 100000000));
//        """.trimIndent()
//        sql(data)
//    }


    override var suiteDbName: String = "test_hll_sketch"

    @Test
    fun testPrepare() {
        prepare1()
        prepare2()
        prepare3()
        prepare4()
//        prepare5()
    }

    @Test
    fun testAggCount() {
        for (i in 10..21) {
            val arr = mutableListOf<Long>()
            val elapsed = measureNanoTime {
                val query =
                    "select hll_sketch_count(id, ${i}), hll_sketch_count(province, ${i}), hll_sketch_count(age, ${i}), hll_sketch_count(dt, ${i}) from t1;"
                val result = query(query)
                assert(result != null)
                assert(result?.size == 1)

                result?.get(0)?.values?.forEach({x ->
                    arr.add(x as Long)
                })
            }
            //println("hll_sketch_count with ${i} precision costs: ${elapsed.milliseconds} ms")
            val values = Joiner.on(" ").join(arr)

            println("${i} ${values} ${elapsed / 1000000}")
        }
    }

    @Test
    fun testAggCountWholeBefore() {
        val type =  "HLL_6"
        val i = "17"
//        val tables = listOf("t1", "t2", "t3", "t4", "t5")
        val tables = listOf("t1", "t2", "t3", "t4")
//        val tables = listOf("t3")
        val streamingModes = listOf("force_streaming", "auto")
//        val streamingModes = listOf("force_streaming")
//        val streamingModes = listOf("force_streaming", "FORCE_PREAGGREGATION", "auto")
//        sql("set streaming_preaggregation_mode = 'force_streaming';")
//        sql("set enable_profile= 'true';")
//        sql("set query_timeout=10000;")
        for (mode in streamingModes) {
            sql("set streaming_preaggregation_mode = '${mode}';")
            for (t in tables) {
                val arr = mutableListOf<Long>()
                val elapsed = measureNanoTime {
                    val query =
//                    "select APPROX_COUNT_DISTINCT_HLL_SKETCH(id), APPROX_COUNT_DISTINCT_HLL_SKETCH(province), APPROX_COUNT_DISTINCT_HLL_SKETCH(age), APPROX_COUNT_DISTINCT_HLL_SKETCH(dt) from ${t};"
                        "select id, APPROX_COUNT_DISTINCT_HLL_SKETCH(province), APPROX_COUNT_DISTINCT_HLL_SKETCH(age), APPROX_COUNT_DISTINCT_HLL_SKETCH(dt) from ${t} group by id order by id limit 10;"
                    val result = query(query)
                    assert(result != null)
                    result?.get(0)?.values?.forEach({x ->
                        arr.add(x as Long)
                    })
                }
                val values = Joiner.on(" ").join(arr)
                println("${type} ${i} ${mode} ${values} ${elapsed / 1000000}")
            }
        }
    }

    @Test
    fun testAggCountWhole() {
        sql("set streaming_preaggregation_mode = 'force_streaming';")
        val types = listOf("HLL_4", "HLL_6", "HLL_8")
        for (type in types) {

            for (i in 10..21) {
                val arr = mutableListOf<Long>()
                val elapsed = measureNanoTime {
                    val query =
                        "select hll_sketch_count(id, ${i}, '${type}'), hll_sketch_count(province, ${i}, '${type}'), hll_sketch_count(age, ${i}, '${type}'), hll_sketch_count(dt, ${i}, '${type}') from t1;"
                    val result = query(query)
                    assert(result != null)
                    assert(result?.size == 1)

                    result?.get(0)?.values?.forEach({x ->
                        arr.add(x as Long)
                    })
                }
                //println("hll_sketch_count with ${i} precision costs: ${elapsed.milliseconds} ms")
                val values = Joiner.on(" ").join(arr)

                println("${type} ${i} ${values} ${elapsed / 1000000}")
            }
        }
    }
}