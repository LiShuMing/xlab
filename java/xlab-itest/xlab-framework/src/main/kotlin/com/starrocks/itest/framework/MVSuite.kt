package com.starrocks.itest.framework

import com.google.common.base.Joiner
import com.google.common.base.Preconditions
import com.google.common.base.Strings
import com.starrocks.itest.framework.mv.MVWorker
import com.starrocks.itest.framework.utils.Result
import com.starrocks.schema.MMaterializedView
import com.starrocks.schema.MTable
import org.junit.jupiter.api.TestInstance

class PartialRefreshParam(val start: String,
                          val end: String,
                          val predicates: Array<String>)

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
open class MVSuite: Suite() {
    protected val DEFAULT_MV_NAME = "__itest_mv0"
    protected val MAX_CHECK_MV_TIMES = 300
    protected var IS_DEV_ENV = false

    ///////// MV ////////

    fun setIsDevEnv() {
        IS_DEV_ENV = true
    }

    fun isDevEnv(): Boolean {
        return IS_DEV_ENV
    }

    fun dropMV(mv: String) {
        mustExec("DROP MATERIALIZED VIEW IF EXISTS $mv")
    }

    fun refreshMV(mvName: String, syncMode: Boolean = true, force: Boolean = false) {
        var sql = "refresh materialized view " + mvName
        if  (force) {
            sql += " force "
        }
        if (syncMode) {
            sql += " with sync mode"
        }
        mustExec(sql)
    }

    fun refreshMV(mvName: String, start: String, end: String, force: Boolean = false) {
        var sql = "refresh materialized view ${mvName} PARTITION start ('${start}') end ('${end}')"
        if (force) {
            sql += " force with sync mode"
        } else {
            sql += " with sync mode"
        }
        mustExec(sql)
    }

    fun untilMVReady(mvName: String) {
        val sql = "show materialized views where name='${mvName}'"
        LOG.info(sql)
        var i = 0
        while (true && i < MAX_CHECK_MV_TIMES) {
            val mvStatuses = query(sql)
            if (mvStatuses == null) {
                break
            }
            if (mvStatuses.all {status -> status["last_refresh_state"] == "SUCCESS"}) {
                break
            }
            Thread.sleep(500)
            i += 1
        }
    }

    fun untilSyncMVReady() {
        val sql = "show alter materialized view"
        while (true) {
            val mvStatuses = query(sql)
            if (mvStatuses == null) {
                break
            }
            if (mvStatuses.all {status -> status["State"] == "FINISHED" || status["State"] == "CANCELLED" || status["State"] == "" }) {
                break
            }
            Thread.sleep(500)
        }
    }

    fun assertContains(query: String, vararg expects: String, isDisplayPlan: Boolean = false) {
        val explainPlan = explain(query)
        if (isDisplayPlan) {
            val formatPlan = Joiner.on("\n").join(explainPlan.map { x ->
                Joiner.on("\n").join(x)
            })
            println(formatPlan)
        }
        for (expect in expects) {
            assert(explainPlan.any({p -> p.any({x -> x.contains(expect)})}));
        }
    }

    fun isContains(query: String, vararg expects: String, isDisplayPlan: Boolean = false): Boolean {
        val explainPlan = explain(query)
        if (isDisplayPlan) {
            val formatPlan = Joiner.on("\n").join(explainPlan.map { x ->
                Joiner.on("\n").join(x)
            })
            println(formatPlan)
        }
        for (expect in expects) {
            if (explainPlan.any({p -> p.any({x -> x.contains(expect)})})) {
                return true
            }
        }
        return false
    }

    fun display(result: List<Map<String, Any?>>?) {
        val format = Joiner.on("\n").join(result!!)
        println(format)
    }

    fun assertResultEquals(actual:List<Map<String, Any?>>?, exp: List<Map<String, Any?>>?) {
        if (actual?.size != exp?.size) {
            Preconditions.checkState(false, "actual result size ${actual?.size} " +
                    "is not equal to result with expect size ${exp?.size}")
        }
        val sortedActual = actual?.sortedByDescending { x -> x.toString() }
        val sortedExp = exp?.sortedByDescending { x -> x.toString() }
        for (i in 0..< actual?.size!!) {
            if (sortedActual?.get(i) != sortedExp?.get(i)) {
                Preconditions.checkState(false, "result with mv line $i not equal(mv/without mv): " +
                        "${sortedActual?.get(i)} <---> ${sortedExp?.get(i)}")
            }
        }
    }
    fun assertEqualsWithMV(query: String) {
        LOG.info("Check result: ${query}")
        sql("set enable_materialized_view_rewrite = false;")
        val resultWithoutMV = query(query)
        sql("set enable_materialized_view_rewrite = true;")
        display(query("trace logs mv ${query}"))
        val resultMV = query(query)
        println(resultWithoutMV)
        println(resultMV)
        assertResultEquals(resultMV, resultWithoutMV)
    }

    fun withMV(mvName: String, partBy: String, query: String, action: () -> Unit) {
        var sql = ""
        if (Strings.isNullOrEmpty(partBy)) {
            sql = "CREATE MATERIALIZED VIEW if not exists $mvName \n" +
                    "DISTRIBUTED BY RANDOM \n" +
                    "REFRESH DEFERRED MANUAL\n" +
                    "PROPERTIES (  " +
                    "\"replication_num\"=\"1\"" +
                    ") AS \n $query;";
        } else {
            sql = "CREATE MATERIALIZED VIEW if not exists $mvName \n" +
                    "PARTITION BY $partBy \n" +
                    "DISTRIBUTED BY RANDOM \n" +
                    "REFRESH DEFERRED MANUAL\n" +
                    "PROPERTIES (  " +
                    "\"replication_num\"=\"1\"" +
                    ") AS \n $query;";
        }
        mustExec(sql)
        action()
    }

    fun withMV(mvName: String, partBy: String, distBy: String, query: String, action: () -> Unit) {
        val sql = "CREATE MATERIALIZED VIEW if not exists $mvName \n" +
                "PARTITION BY $partBy \n" +
                "DISTRIBUTED BY hash($distBy) BUCKETS 8\n" +
                "REFRESH DEFERRED MANUAL\n" +
                "PROPERTIES (  " +
                "\"replication_num\"=\"1\"" +
                ") AS \n $query;";
        mustExec(sql)
        action()
    }

    fun withCompleteRefreshMV(mv: MMaterializedView, action: () -> Unit) {
        val mvWorker = MVWorker(mv)
        val mvBlocks = mvWorker.getPermutations()
        for (mvBlock in mvBlocks) {
            // create mv
            val sql = mvBlock.generateCreateSql()
            mustExec(sql)

            // refresh mv
            refreshMV(mv.tableName)

            // check
            action()

            // drop
            if (!isDevEnv()) {
                dropMV(mv.tableName)
            }
        }
    }

    fun withPartialRefreshMV(mv: MMaterializedView, startPartition: String, endPartition: String, action: () -> Unit) {
        val mvWorker = MVWorker(mv)
        val mvBlocks = mvWorker.getPermutations(true)
        for (mvBlock in mvBlocks) {
            // create mv
            val sql = mvBlock.generateCreateSql()
            mustExec(sql)

            // refresh mv
            refreshMV(mv.tableName, startPartition, endPartition)

            // check
            action()

            // drop
            if (!isDevEnv()) {
                dropMV(mv.tableName)
            }
        }
    }

    fun withCompleteRefreshMV(mvName: String, partBy: String, query: String, action: () -> Unit) {
        withMV(mvName, partBy, query) {
            withCompleteRefreshMV(mvName, action)
        }

        if (!isDevEnv()) {
            dropMV(mvName)
        }
    }

    fun withCompleteRefreshMV(mvName: String, partBy: String, distBy: String, query: String, action: () -> Unit) {
        withMV(mvName ,partBy, distBy, query) {
            withCompleteRefreshMV(mvName, action)
        }
        if (!isDevEnv()) {
            dropMV(mvName)
        }
    }

    fun withCompleteRefreshMV(mvName: String, action: () -> Unit) {
        refreshMV(mvName)
        action()
    }

    fun dateTruncList(partBy: String) : List<String> {
        val SECOND = "second"
        val MINUTE = "minute"
        val HOUR = "hour"
        val DAY = "day"
        val MONTH = "month"
        val QUARTER = "quarter"
        val YEAR = "year"
        var arr = listOf(SECOND, MINUTE, HOUR, DAY, MONTH, QUARTER, YEAR)
        return arr.map { x -> "date_trunc('$x', $partBy)" }
            .toList()
    }

    fun withMTable(table: MTable, action: () -> Unit): Unit {
        val createSql = table.createTableSql
        sql(createSql)
        val insertSql = table.generateDataSQL
        sql(insertSql)

        action()

        if (!IS_DEV_ENV) {
            dropTable(table.tableName)
        }
    }

    fun existsMV(name: String): Boolean {
        val r = showMV(name)
        return r.bind { v -> if (v.isEmpty()) false else true}
            .unwrap();
    }

    fun showMV(name: String): Result<List<Map<String, Any>>> {
        val sql = "show materialized views like '$name'"
        return queryResult(sql)
    }

    fun getMVTaskName(name: String): Result<String> {
        return showMV(name).bind { t ->
            t.first()["task_name"] as String
        }
    }

    fun enableMVRewrite(enable: Boolean) {
        sql("set enable_materialized_view_rewrite=${enable}")
    }

    /**
     * Check query's result and total mv's result are equal.
     */
    fun assertEqualQueryAndMVResult(query: String, mvName: String) {
        // query result
        enableMVRewrite(false)
        val queryResult = query(query)

        // mv result
        val mvResult = query("select * from ${mvName}")

        // assert equal
        assertResultEquals(mvResult, queryResult)
    }

    fun assertEqualQueryAndMVResultWithConfig(query: String, config: String) {
        // query result
        enableMVRewrite(false)
        sql("set ${config} = true")
        val queryResult1 = query(query)

        sql("set ${config} = false")
        val queryResult2 = query(query)

        // assert equal
        assertResultEquals(queryResult1, queryResult2)
    }
}