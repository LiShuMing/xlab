package com.starrocks.itest.framework.utils

import com.mysql.jdbc.MySQLConnection
import java.sql.Statement

class MySQLSession(val cxn: MySQLConnection) {
    fun <T> execImpl(sql: String, f: (Statement, String) -> T): T? {
        cxn.connectTimeout = 10
        cxn.socketTimeout = 10
        val re = Regex("[\\s;]+$")
        val sql0 = re.replace(sql, "") + ";"
        return f(cxn.createStatement()!!, sql0)
    }

    fun exec(sql: String): Boolean? {
        val f = { stmt: Statement, sql: String ->
            stmt.execute(sql)
        }

        return execImpl(sql, f)
    }
}
