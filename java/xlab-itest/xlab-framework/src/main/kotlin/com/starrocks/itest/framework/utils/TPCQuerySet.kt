package com.starrocks.itest.framework.utils

import java.io.File
import java.nio.charset.StandardCharsets

object TPCQuerySet {
    fun getResourceDir(): String {
        val currentDir = System.getProperty("user.dir")
        return "$currentDir/../framework/src/main/resources"
    }

    fun tpcdsQueries(): Map<Int, String> {
        val tpcdsQueries = Array(99) {
            val n = it + 1
            val s = "00$n".takeLast(2)
            n to "tpcds/query$s.sql"
        }
        return tpcdsQueries.map { (n, file) ->
            n to String(this.javaClass.classLoader.getResourceAsStream(file).readBytes(), StandardCharsets.UTF_8)
        }.toMap()
    }

    fun ssbLineOrderFlat(): List<Pair<String, String>> {
        val currentDir = System.getProperty("user.dir")
        val queryDir = File("$currentDir/src/main/resources/ssb_lineorder_flat")
        val filePat = Regex("(Q\\d+\\.\\d)\\.sql")
        return queryDir.listFiles()!!
            .flatMap { f -> filePat.matchEntire(f.name)?.let { listOf(it.groupValues[1] to f!!) } ?: listOf() }
            .map { (n, f) ->
                n to f.readText()
            }.sortedBy { (n, _) -> n }
    }

    fun clickBench(): List<Pair<String, String>> {
        val currentDir = System.getProperty("user.dir")
        val queryDir = File("$currentDir/src/main/resources/ClickBench")
        val filePat = Regex("(Q\\d+)\\.sql")
        val trimTrailing = Regex("[;\n\\s]*$")
        return queryDir.listFiles()!!
            .flatMap { f -> filePat.matchEntire(f.name)?.let { listOf(it.groupValues[1] to f!!) } ?: listOf() }
            .map { (n, f) ->
                n to trimTrailing.replace(f.readText(), "")
            }.sortedBy { (n, _) -> n }
    }

    fun getQueryList(querySet: String, filePat: Regex): List<Pair<String, String>> {
        val queryDir = File("${getResourceDir()}/$querySet")
        val trimTrailing = Regex("[;\n\\s]*$")
        return queryDir.listFiles()!!
            .flatMap { f -> filePat.matchEntire(f.name)?.let { listOf(it.groupValues[1] to f!!) } ?: listOf() }
            .map { (n, f) ->
                n to trimTrailing.replace(f.readText(), "")
            }.sortedBy { (n, _) -> n }
    }

    fun queryOfTPCDS(queryId: Int): String {
        val qName = "query" + ("00$queryId").takeLast(2);
        return getTPCDSQueryList().filter { (n, _) -> n == qName }.map { (_, sql) -> sql }.first()
    }

    fun getTPCHQueryList() = getQueryList("tpch", Regex("(q\\d\\d)\\.sql"))
    fun getTPCDSQueryList() = getQueryList("tpcds", Regex("(query\\d\\d)\\.sql"))


    fun clickBenchDerivation(): List<Pair<String, String>> {
        val querySet = "ClickBenchDerivation"
        val filePat = Regex("(Q\\d+_\\d+)\\.sql")
        return getQueryList(querySet, filePat)
    }
}