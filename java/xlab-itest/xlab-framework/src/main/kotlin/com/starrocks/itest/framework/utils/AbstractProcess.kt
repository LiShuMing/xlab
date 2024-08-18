package com.starrocks.itest.framework.utils

import com.google.common.base.Preconditions
import java.io.ByteArrayOutputStream
import java.io.File

abstract class AbstractProcess {
    abstract val cmd: String
    abstract val argv: Array<String>
    abstract val baseDir: String
    var proc: Process? = null
    var prepared = false
    var input :ByteArray?=null
    val stdout = ByteArrayOutputStream()
    val stderr = ByteArrayOutputStream()
    val cwd = File(System.getProperty("user.dir")!!)
    val verbose = System.getenv("verbose")

    open val envs = mapOf<String, String>()
    protected abstract fun prepare()
    fun cleanup() {
        Result.wrap {
            val df = File(baseDir)
            df.deleteRecursively()
        }.unwrap()
    }

    fun start() {
        if (!prepared) {
            prepare()
            prepared = true
        }
        proc = Result.wrap {
            val cmdAndArgs = arrayOf(cmd, *argv)
            val cmdAndArgsStr = cmdAndArgs.joinToString(" ")
            var script = "#!/bin/bash\n$cmdAndArgsStr"
            if (envs.isNotEmpty()) {
                val envsStr = envs.map { e -> "${e.key}=${e.value}" }.joinToString(" ")
                script = "#!/bin/bash\nenv $envsStr $cmdAndArgsStr"
            }
            //println("[RUN CMD]: $cmdAndArgsStr")
            //verbose?.let {
            //    println("==========================")
            //    println("[RUN CMD]\n$script")
            //}
            val scriptFile = File(baseDir + File.separator + "script.sh")
            Util.createFile(scriptFile, script)

            val builder = ProcessBuilder(*cmdAndArgs)
            builder.environment().putAll(envs)
            builder.start()
        }.unwrap()
        Preconditions.checkState(proc != null)
    }

    fun startAndWait(check: Boolean) {
        this.start()
        if (check) {
            val status = waitFor()
            Result.wrap {
                Util.streamCopy(proc!!.errorStream, stderr)
                stderr.close()
            }
            Result.wrap {
                Util.streamCopy(proc!!.inputStream, stdout)
                stdout.close()
            }
            if (status != 0) {
                println("stderr:\n${this.stderr}")
                println("stdout:\n${this.stdout}")
                Preconditions.checkState(false, "Fail to exec ${argv.joinToString(" ")}")
            }
        }
    }

    fun eval(): Result<String> {
        this.start()
        proc?.let {p->
            input?.let {i->
                p.outputStream.write(i)
                p.outputStream.flush()
                p.outputStream.close()
            }
        }
        val status = waitFor()
        if (status !=0) {
            return Err(RuntimeException("Fail to evaluate ${this.cmd}"))
        }
        val byteOut = ByteArrayOutputStream()
        return Result.wrap {
            Util.streamCopy(proc!!.errorStream, stderr)
            val err = stderr.toString("UTF-8")
            if (err.isNotEmpty()) {
                println(err)
            }
            Util.streamCopy(proc!!.inputStream, byteOut)
            byteOut.toString("UTF-8")
        }
    }

    fun kill() {
        val p = proc
        p ?: return
        if (p.isAlive) {
            p.destroy()
        }
    }

    fun killForcibly() {
        val p = proc
        p ?: return
        if (p.isAlive) {
            p.destroyForcibly()
        }
    }

    fun waitFor(): Int {
        return proc?.let { it.waitFor() } ?: -1
    }

    fun stop() {
        killForcibly()
        waitFor()
    }
}