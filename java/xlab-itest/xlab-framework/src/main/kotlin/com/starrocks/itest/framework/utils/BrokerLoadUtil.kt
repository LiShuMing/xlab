package com.starrocks.itest.framework.utils

import com.google.common.base.Preconditions
import com.starrocks.itest.framework.Suite


object BrokerLoadUtil {
    fun getResourceDir(): String {
        val currentDir = System.getProperty("user.dir")
        return "$currentDir/../xlab-framework/src/main/resources"
    }

    fun brokerLoadSql(db: String, tableName: String, format: String, hdfsPath: String, columns: List<String>, columnSeparator: String?): String {
        return Util.renderTemplateFromResources(
            "broker_load.sql.template",
            "db" to db,
            "table" to tableName,
            "labelId" to System.currentTimeMillis().toString(),
            "format" to format,
            "hdfsPath" to hdfsPath,
            "columnList" to (columns),
            "columnSeparator" to columnSeparator
        )
    }

    fun checkBrokerLoadComplete(suite: Suite, db: String) {
        val finishStates = setOf("CANCELLED", "SUCCESS", "FINISHED")
        while (true) {
            val result = suite.query("show load from $db order by CreateTime desc limit 1")
            val state = result!!.first()["State"]!!
            println(result!!.first())
            if (state in finishStates) {
                Preconditions.checkState(state == "FINISHED")
                break
            }
            Thread.sleep(1000)
        }
    }

    fun brokerLoad(
        suite: Suite,
        db: String,
        tableName: String,
        format: String,
        hdfsPath: String,
        columns: List<String>,
        columnSeparator: String?
    ) {
        suite.mustExec(brokerLoadSql(db, tableName, format, hdfsPath, columns, columnSeparator))
        checkBrokerLoadComplete(suite, db)
    }
}