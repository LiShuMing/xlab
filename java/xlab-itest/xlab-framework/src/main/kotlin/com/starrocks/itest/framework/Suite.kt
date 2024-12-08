package com.starrocks.itest.framework

import com.google.common.base.CaseFormat
import com.google.common.base.Joiner
import com.google.common.base.Preconditions
import com.google.common.base.Stopwatch
import com.google.common.collect.Sets
import com.starrocks.itest.framework.conf.SRConf
import com.starrocks.itest.framework.schema.Table
import com.starrocks.itest.framework.utils.*
import com.starrocks.schema.MTable
import org.example.com.starrocks.itest.framework.utils.Recorder
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.TestInstance
import org.slf4j.LoggerFactory
import org.springframework.jdbc.core.ColumnMapRowMapper
import org.springframework.jdbc.core.RowMapperResultSetExtractor
import java.io.StringReader
import java.nio.file.Paths
import java.sql.Statement
import java.util.*
import java.util.concurrent.atomic.AtomicReference

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
open class Suite {
    protected val LOG = LoggerFactory.getLogger(Suite::class.java)!!

    protected open var suiteName = CaseFormat.LOWER_CAMEL.to(CaseFormat.LOWER_UNDERSCORE, this.javaClass.simpleName)
    // default suit db's name is the same as the suite name
    protected open var suiteDbName = suiteName

    //////////// Do Before and After
    @BeforeAll
    open fun before() {
        mustCreateAndUseDB(suiteDbName)
    }

    @AfterAll
    open fun after() {
        // mustDropDB(suiteDbName)
    }

    ///////// Connection / Session
    private val connSession = AtomicReference<MySQLSession>();
    private val srConf = SRConf.parse(Paths.get("../conf", "sr.yaml"))
//    private val srConf = SRConf.parse(Paths.get("../conf", "tsp.yaml"))

    private fun getOrInitSession(connNum : Int = 1): MySQLSession {
        if (connSession.get() == null) {
            val host = srConf.mysqlClient.host
            val port = srConf.mysqlClient.port
            println("host: $host, port: $port")
            Result.wrap {
                val sh = ShellCmd(".shell_cmds")
                sh.run_script(
                    "ssh_proxy", """
        ssh -f -L ${port}:${host}:${port} lishuming@39.99.136.234 sleep 36000
        """.trimIndent()
                )
            }
            val hostPort = "127.0.0.1:${port}"
            println(hostPort)
            val session = MySQLSession(MySQLUtil.newMySQLConnectionPool(hostPort,
                srConf.mysqlClient.user, connNum).getCxn())
            connSession.set(session)
        }
        return connSession.get()!!
    }
    private val rd: Recorder by lazy {
        Recorder(suiteName)
    }

    init {
        getOrInitSession()
    }

    private fun getConn(): MySQLSession {
        return connSession.get()
    }

    fun showTablet(t: String) = query("show tablet from $t")!!

    fun mustCreateAndUseDB(db: String) {
        val result = query("SHOW DATABASES")
        if (!result!!.any { x -> x.values.contains(db) }) {
            mustExec("CREATE DATABASE $db")
        }
        mustExec("USE $db")
    }

    fun useDB(db: String) {
        mustExec("set catalog default_catalog")
        mustExec("USE $db")
    }

    fun mustDropDB(db: String) {
        mustExec("DROP DATABASE IF EXISTS $db")
    }

    fun createTable(table: Table) {
        mustExec(table.sql())
    }

    fun query(sql: String): List<Map<String, Any?>>? {
        val f = { stmt: Statement, sql: String ->
            val rsExtractor = RowMapperResultSetExtractor(ColumnMapRowMapper())
            rsExtractor.extractData(stmt.executeQuery(sql))
        }
        LOG.info(sql)
        return getConn().execImpl(sql, f)
    }

    fun existsFunction(name: String): Boolean {
        val rs = query("SHOW functions like '$name'")!!
        return rs.isNotEmpty() && rs.first().isNotEmpty() && name.equals(rs.first().values.first() as String, true)
    }

    fun existsTable(name: String): Boolean {
        val rs = query("SHOW tables like '$name'")!!
        return rs.isNotEmpty() && rs.first().isNotEmpty() && name.equals(rs.first().values.first() as String, true)
    }

    fun existsDb(name: String): Boolean {
        val rs = query("SHOW databases like '$name'")!!
        return rs.isNotEmpty() && rs.first().isNotEmpty() && name.equals(rs.first().values.first() as String, true)
    }

    fun queryFingerprint(sql: String): Long {
        val rs = query(sql)
        return rs!!.first()["fingerprint"]!! as Long
    }

    fun explainCosts(q:String):String {
        val lines = query("EXPLAIN costs $q")!!.map { m -> m["Explain String"] as String }
        return lines.joinToString("\n")
    }

    fun assertContains(plan: List<List<String>>, expect: String) {
        Preconditions.checkState(plan.any { f -> f.any { ln -> ln.contains(expect)} })
    }

    fun explain(q: String): List<List<String>> {
        val lines = query("EXPLAIN verbose $q")!!.map { m -> m["Explain String"] as String }
        val fragRe = Regex("^\\s*PLAN FRAGMENT\\s*(\\d+)\\((\\S+)\\)")
        val blankRe = Regex("^\\s*$")
        var firstFragHit = false
        val fragments = mutableListOf<MutableList<String>>()
        lines.forEach { ln ->
            val m = fragRe.matchEntire(ln)
            if (m == null) {
                if (!firstFragHit) {
                    return@forEach
                }
            } else {
                firstFragHit = true
                fragments.add(mutableListOf(ln))
                return@forEach
            }
            if (blankRe.matchEntire(ln) != null) {
                return@forEach
            }
            fragments.last().add(ln)
        }
        return fragments
    }

    fun mustExec(sql: String) {
        if (!sql.endsWith(";")) {
            println("$sql;")
        } else {
            println(sql)
        }

        Result.wrap {
            getConn().exec(sql)!!
        }.let {
            it.ifErrThen { err ->
                err.printStackTrace();
            }
            Preconditions.checkState(it.isOk())
        }
    }

    fun sql(sql: String) {
        return mustExec(sql)
    }

    fun withView(viewName: String, sql: String, action: () -> Unit) {
        sql("create view ${viewName} as select * from (${sql}) t")
        action()
        sql("drop view ${viewName}")
    }

    private fun waitLoadReady() {
        val sql = "show load;"
        while (true) {
            val loadStatuses = query(sql)
            if (loadStatuses == null) {
                break
            }
            if (loadStatuses.all { status -> status["State"] == "FINISHED" || status["State"] == "CANCELLED" || status["State"] == "" }) {
                break
            }
            Thread.sleep(1000)
        }
    }

    fun dropTable(table: String, isThrows: Boolean = false) {
        try {
            sql("drop table if exists $table")
        } catch (e: Exception) {
            if (isThrows) {
                throw e
            }
        }
    }

    fun generatePartitionValues(partValues: Array<String>): String {
        val parts = Joiner.on("\',\'").join(partValues)
        return "'${parts}'"
    }


    fun rdSql(sql: String, header: String) {
        rd.write(rd.header(header))
        query(sql)!!.let { result ->
            println(result)
            result!!.forEach { rows ->
                rows.entries.joinToString { (k, v) -> "$k=$v" }.let { rd.write(it) }
            }
        }
    }

    fun rdExplainTime(sql: String, h: String = "") {
        rdTime("explain ${sql}", h)
    }

    fun rdTime(sql: String, h: String = "") {
        rd.write(rd.header(h))
        val stopwatch = Stopwatch.createStarted()
        sql(sql)
        stopwatch.stop()
        val duration = stopwatch.elapsed()
        rdContent(duration.toMillis().toString())
    }

    fun rdHeader(str: String) {
        rdContent(rd.header(str))
    }

    fun rdContent(str: String) {
        rd.write(str)
    }

    fun sql(mtable: MTable, loadData: Boolean) {
        sql(mtable.createTableSql)
        if (loadData) {
            sql(mtable.generateDataSQL)
        }
    }

    ///////// OTHER FUNCTIONS
    fun catalogExists(catalog: String): Boolean {
        val result = query("show catalogs")
        val catalogs = result?.map { x -> x.get("Catalog") }?.toCollection(Sets.newHashSet())
        return catalogs!!.contains("hive")
    }

    fun queryResult(s: String): Result<List<Map<String, Any>>> {
        return Result.wrap {
            query(s)!!.map { t -> t.map { (k, v) -> k!! to (v ?: "NULL") }.toMap() }.toList()
        }
    }

    ///////// PREPARE DATAS
    fun brokerLoad(db: String, props: Properties) {
        val tableName = props["brokerLoad.table"] as String
        val format = props["brokerLoad.format"] as String
        val columns = (props["brokerLoad.columns"] as String).split(",")
        val columnSeparator = props.getProperty("brokerLoad.columnSeparator", null)
        val hdfsPath = props["brokerLoad.hdfsPath"] as String
        BrokerLoadUtil.brokerLoad(this, db, tableName, format, hdfsPath, columns, columnSeparator)
    }

    fun brokerLoad(
        db: String,
        tableName: String,
        format: String,
        hdfsPath: String,
        columns: List<String>,
        columnSeparator: String?
    ) {
        BrokerLoadUtil.brokerLoad(this, db, tableName, format, hdfsPath, columns, columnSeparator)
    }


    fun useSsb1g(se: MySQLSession, db: String) {
        mustCreateAndUseDB(db)
        val createTableSql = Util.readContentFromResource("ssb_1g/create_table.sql")
        val lineorderBrokerLoadParams = Util.readPropertiesFromResource("ssb_1g/lineorder.broker_load.properties")
        val datesBrokerLoadParams = Util.readPropertiesFromResource("ssb_1g/dates.broker_load.properties")
        val customerBrokerLoadParams = Util.readPropertiesFromResource("ssb_1g/customer.broker_load.properties")
        val partBrokerLoadParams = Util.readPropertiesFromResource("ssb_1g/part.broker_load.properties")
        val supplierBrokerLoadParams = Util.readPropertiesFromResource("ssb_1g/supplier.broker_load.properties")
        mustExec(createTableSql)
        brokerLoad(db, lineorderBrokerLoadParams)
        brokerLoad(db, datesBrokerLoadParams)
        brokerLoad(db, customerBrokerLoadParams)
        brokerLoad(db, partBrokerLoadParams)
        brokerLoad(db, supplierBrokerLoadParams)
    }

    fun useTpch1g(createTables: Boolean = true, loadData: Boolean = false, dir: String = "tpch_1g") {
        val tableNames = listOf(
            "orders",
            "region",
            "partsupp",
            "supplier",
            "nation",
            "lineitem",
            "part",
            "customer",
        )

        val db = suiteDbName
        if (createTables) {
            tableNames.forEach { tableName ->
                val resourceDir = Util.getResourceDir()
                val createTableSql = Util.readContentFromPath("${resourceDir}/${dir}/$tableName.sql")
                mustExec(createTableSql.replace("default_replication_num", "1"))
            }
        }
        if (loadData) {
            tableNames.forEach { tableName ->
                val brokerLoadParams = Util.readPropertiesFromResource("${dir}/$tableName.broker_load.properties")
                brokerLoad(db, brokerLoadParams)
            }
        }

    }

    fun useTpcds1G(loadData: Boolean = false) {
        if (loadData) {
            val brokerLoadSqls = TPCQuerySet.getQueryList("tpcds_1g", Regex("(\\w+)\\.broker_load\\.properties"))
            brokerLoadSqls.forEach { (name, s) ->
                println("Load $name");
                val properties = Properties()
                properties.load(StringReader(s))
                brokerLoad(suiteDbName, properties)
            }
        } else {
            val createTableSqls = TPCQuerySet.getQueryList("tpcds_1g", Regex("([_a-z]*)\\.sql"))
            mustCreateAndUseDB(suiteDbName);
            createTableSqls.forEach { (name, sql) ->
                mustExec(sql)
            }
        }
    }
}