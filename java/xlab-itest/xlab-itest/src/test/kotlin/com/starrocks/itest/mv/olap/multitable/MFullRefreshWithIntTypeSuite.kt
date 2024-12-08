package com.starrocks.itest.mv.olap.multitable

import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll

open class MFullRefreshWithIntTypeSuite : MFullRefreshSuite() {

    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_int.sql")
        sql(createTableSql)
    }

    @AfterAll
    override fun after() {
        //super.after()
    }

    override fun withPartColumnType(): String {
        return "int"
    }

    override fun withMVPartColumn(basePartitionColumnName: String): String {
        return basePartitionColumnName
    }
}