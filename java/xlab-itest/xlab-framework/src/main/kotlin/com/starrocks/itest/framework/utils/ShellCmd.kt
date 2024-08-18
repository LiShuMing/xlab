package com.starrocks.itest.framework.utils

import com.google.common.base.Preconditions
import java.io.File

/**
 * Created by grakra on 18-9-4.
 */
class ShellCmd(override val baseDir: String) : AbstractProcess() {
    override var cmd = ""
    override var argv = arrayOf<String>()
    override fun prepare() {
        if (prepared) {
            return
        }
        prepared = true
        cleanup()
        Result.wrap { File(baseDir).mkdirs() }.unwrap()
    }

    fun run_nocheck(vararg cmdAndArgs: String) {
        run_and_check(false, *cmdAndArgs)
    }

    fun run(vararg cmdAndArgs: String) {
        run_and_check(true, *cmdAndArgs)
    }

    fun run_and_check(check: Boolean, vararg cmdAndArgs: String) {
        val args = cmdAndArgs.flatMap { s ->
            s.trim().split(Regex("\\s+"))
        }.toTypedArray()
        this.cmd = args[0]
        this.argv = args.drop(1).toTypedArray()
        startAndWait(check)
    }

    fun eval(vararg cmdAndArgs: String): Result<String> {
        this.cmd = cmdAndArgs[0]
        val args = cmdAndArgs.drop(1).toTypedArray()
        val idx = args.flatMapIndexed { i, e ->
            if (e == "--") {
                listOf(i)
            } else {
                emptyList<Int>()
            }
        }
        if (idx.isEmpty()) {
            this.argv = args
        } else {
            val i = idx.first()
            this.argv = args.sliceArray(0 until i)
            val s = args.slice(i + 1 until args.size).reduce { a, b -> a + b }
            this.input = s.toByteArray(Charsets.UTF_8)
        }
        return eval()
    }

    fun run_script(name: String, script: String) {
        prepare()
        this.cmd = "/bin/bash"
        Preconditions.checkState(Regex("^\\w+$").matches(name))
        val scriptFile = File(baseDir + File.separator + name)
        Util.createFile(scriptFile, script)
        this.argv = arrayOf(scriptFile.canonicalPath)
        startAndWait(true)
    }
}
