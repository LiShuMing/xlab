package com.starrocks.itest.mv.olap.multitable

import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll

class MPartialRefreshWithIntSuite : MPartialRefreshSuite() {

    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_int.sql")
        sql(createTableSql)
    }

    override fun withPartColumnType(): String {
        return "int"
    }

    override fun withMVPartColumn(basePartitionColumnName: String): String {
        return basePartitionColumnName
    }
}