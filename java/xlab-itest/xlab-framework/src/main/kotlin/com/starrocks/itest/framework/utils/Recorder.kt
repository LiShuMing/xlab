package org.example.com.starrocks.itest.framework.utils

import java.io.File
import java.nio.file.Paths

class Recorder(val testName: String) {
    init {
        initOutFile()
    }

    fun initOutFile(): File {
        val path = Paths.get("").toAbsolutePath().toString()
        val resultPath = "$path/../result/${testName}.out"
        val outputFile = File(resultPath)
        if (outputFile.exists()) {
            outputFile.delete()
        }
        outputFile.createNewFile()
        return outputFile
    }

    private fun getOutFile(): File {
        val path = Paths.get("").toAbsolutePath().toString()
        val resultPath = "$path/../result/${testName}.out"
        val outputFile = File(resultPath)
        if (!outputFile.exists()) {
            outputFile.createNewFile()
        }
        return outputFile
    }

    fun write(context: String) {
        val out = getOutFile()
        out.appendText(context)
        out.appendText("\n")
    }

    fun header(header: String): String {
        return "----------- ${header} ----------- "
    }
}