package com.starrocks.itest.framework.utils

import com.mysql.jdbc.Driver
import com.mysql.jdbc.MySQLConnection
import java.sql.DriverManager

object MySQLUtil {
    fun newMySQLConnectionPool(hostPort: String, user: String, size: Int): ConnectionPool<MySQLConnection> {
        val cxnString = "jdbc:mysql://$hostPort/?user=$user&zeroDateTimeBehavior=convertToNull&connectTimeout=600000&socketTimeout=300000"
        return newMySQLConnectionPool(cxnString, size)
    }

    fun newMySQLConnectionPool(cxnString: String, size: Int): ConnectionPool<MySQLConnection> {
        val init = {
            Class.forName(Driver::class.java.canonicalName)
            Unit
        }
        val newCxn = {
            DriverManager.getConnection(cxnString).unwrap(MySQLConnection::class.java)!!
        }
        return ConnectionPool(init, newCxn, size)
    }
}
