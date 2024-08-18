package com.starrocks.itest.framework.utils

import com.google.common.base.Preconditions
import com.google.common.base.Strings
import org.slf4j.LoggerFactory
import org.stringtemplate.v4.STGroupString
import java.io.*
import java.math.BigDecimal
import java.math.BigInteger
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import java.util.*
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.locks.LockSupport
import java.util.stream.Collectors
import kotlin.math.abs


object Util {
    private val LOG = LoggerFactory.getLogger(Util.javaClass)

    fun getTableSql(table: String): String {
        return this.javaClass.classLoader.getResourceAsStream("$table.sql").bufferedReader().readText()
    }

    fun removeUnit(s: String): String {
        val unit1Re = Regex("^(\\d+(?:.\\d+)?)(K|M|G)?$")
        val unitBytesRe = Regex("^(\\d+(?:.\\d+)?)(KB|MB|GB|B)$")
        var m = unit1Re.matchEntire(s)
        if (m != null) {
            val units = mapOf("K" to 1000L, "M" to 1000_000L, "G" to 1000_000_000L, "" to 1)
            val n = (m.groupValues[1].toDouble() * units[m.groupValues[2]]!!).toLong()
            return "$n"
        }

        m = unitBytesRe.matchEntire(s)
        if (m != null) {
            val units = mapOf("KB" to 1024L, "MB" to 1024L * 1024L, "GB" to 1024L * 1024L * 1024L, "B" to 1, "" to 1)
            val n = (m.groupValues[1].toDouble() * units[m.groupValues[2]]!!) as Long
            return "$n"
        }
        return s
    }

    fun squeezeWhiteSpaces(s: String): String {
        return s.replace(Regex("[\n\r]"), " ").replace(Regex("\\s+"), " ").trim()
    }

    fun createPropertiesConfFile(path: String, props: List<Pair<String, String>>) {
        createFile(path) { o ->
            props.forEach { e ->
                o.println("${e.first}=${e.second}")
            }
        }
    }

    fun generateRandomBigInt(negRatio: Int): () -> BigInteger {
        val rand = Random()
        return {
            if (rand.nextInt(100) < negRatio) {
                BigInteger(128, rand).negate()
            } else {
                BigInteger(128, rand)
            }
        }
    }

    fun generateRandomDecimal128(precision: Int, scale: Int, negRatio: Int): () -> BigDecimal {
        val maxValue = BigInteger(Strings.repeat("9", precision))
        val randomBigInt = generateRandomBigInt(negRatio)
        return {
            val bigInt = randomBigInt()
            if (bigInt.signum() < 0) {
                BigDecimal(bigInt.mod(maxValue), scale).negate()
            } else {
                BigDecimal(bigInt.mod(maxValue), scale)
            }
        }
    }

    fun generateRandomLong(numBits: Int): () -> Long {
        val rand = Random()
        val mask = (1L shl numBits) - 1L

        return {
            rand.nextLong().and(mask)
        }
    }

    fun generateRandomDecimal64(precision: Int, scale: Int): () -> Long {
        val maxValue = Strings.repeat("9", precision).toLong()
        val randomLong = generateRandomLong(64)
        return {
            randomLong() % maxValue
        }
    }

    fun generateCounter(limit: Int): () -> Int {
        var n = -1
        return {
            n += 1
            n %= limit
            n
        }
    }

    fun generateCounter(): () -> Int = generateCounter(Int.MAX_VALUE)


    fun generateLongCounter(): () -> Long = generateLongCounter(Long.MAX_VALUE)


    fun generateCounterRange(from: Int, till: Int): () -> Int {
        val counter = generateCounter(till - from)
        return { counter() + from }
    }

    fun generateLongCounter(limit: Long): () -> Long {
        var n = -1L
        return {
            n += 1L
            n %= limit
            n
        }
    }

    fun generateCounterFrom(from: Int) = generateCounterRange(from, Int.MAX_VALUE)

    fun suffixCounter(prefix: String, counter: () -> Int): () -> String {
        return {
            "$prefix${counter()}"
        }
    }

    private fun <T> uniqueImpl(gen: () -> T, s: MutableSet<T>): T {
        val d = gen()
        return if (s.contains(d)) {
            uniqueImpl(gen, s)
        } else {
            s.add(d)
            d
        }
    }
    fun <T> unique(gen:()->T):()->T {
        val s = mutableSetOf<T>()
        return {
            uniqueImpl(gen,s)
        }
    }

    fun prefixCounter(suffix: String, counter: () -> Int): () -> String {
        return {
            "${counter()}${suffix}"
        }
    }
    fun padLeading(s: String, c: Char, n: Int) =
        (Strings.repeat("$c", n) + s).takeLast(n)

    fun createPropertiesConfFile(path: String, props: Map<String, String>) {
        createPropertiesConfFile(path, props.entries.map { e -> e.key to e.value })
    }

    private fun createFile(path: String, writeCb: (PrintWriter) -> Unit) {
        Preconditions.checkArgument(!path.isEmpty())
        val file = File(path)
        Preconditions.checkState(file.parentFile.exists())
        Preconditions.checkState(!file.exists())
        val writer = PrintWriter(
            OutputStreamWriter(
                FileOutputStream(file),
                Charsets.UTF_8
            )
        )
        writeCb(writer)
        writer.close()
    }

    fun <A, B> crossProduct(xs: List<A>, ys: List<B>) =
        xs.flatMap { x -> ys.map { y -> x to y } }

    abstract sealed class LispList<out T> {
        final fun toList(): List<T> {
            return when (this) {
                is Cons -> listOf(this.car) + this.cdr.toList()
                NIL -> listOf<T>()
            }
        }
    }

    object NIL : LispList<Nothing>()
    data class Cons<T>(val car: T, val cdr: LispList<T>) : LispList<T>()

    fun nils(sz: Int) = List<LispList<Nothing>>(sz) { NIL }
    fun <T> cons(xs: List<T>, ys: List<LispList<T>>): List<LispList<T>> {
        val sz = Math.min(xs.size, ys.size)
        return (0 until sz).map { i -> Cons(xs[i], ys[i]) }
    }

    fun <T> flat(xs: List<LispList<T>>): List<List<T>> = xs.map { it.toList() }

    fun <T> zip2(xs: List<T>, ys: List<T>): List<List<T>> = flat(cons(xs, cons(ys, nils(ys.size))))
    fun <T, U> zip(xs: List<T>, ys: List<U>): List<Pair<T, U>> {
        val sz = Math.min(xs.size, ys.size)
        return (0 until sz).map { i -> xs[i] to ys[i] }
    }

    fun <T1, T2, T3> zipThree(xs: List<T1>, ys: List<T2>, zs: List<T3>): List<Triple<T1, T2, T3>> {
        val sz = Math.min(Math.min(xs.size, ys.size), zs.size)
        return (0 until sz).map { i -> Triple(xs[i], ys[i], zs[i]) }
    }

    fun <T, U> zipToMax(xs: List<T>, ys: List<U>): List<Pair<T, U>> {
        val sz = Math.max(xs.size, ys.size)
        val xsGen = roundRobin(xs)
        val ysGen = roundRobin(ys)
        return (0 until sz).map { _ -> xsGen() to ysGen() }
    }


    private fun createDirIfMissing(dir: Path, perm: String) {
        if (Files.notExists(dir)) {
            Files.createDirectories(dir)
            Files.setPosixFilePermissions(dir, PosixFilePermissions.fromString(perm))
        }
    }

    fun classpath(vararg dirs: String): String {
        return dirs.map {
            val d = it.trimEnd('/')
            if (d.endsWith("conf") || d.endsWith("classes")) {
                d
            } else if (!File(d).isDirectory) {
                emptyArray<String>()
            } else {
                val df = File(d)
                df.listFiles { _, name ->
                    name.endsWith("jar")
                }.joinToString(":") { e ->
                    e.canonicalPath
                }
            }
        }.joinToString(":")
    }

    fun enclosedWriter(file: File, cb: (Writer) -> Unit) {
        file.outputStream().let {
            OutputStreamWriter(it, Charsets.UTF_8)
        }.let {
            cb(it)
            it.close()
        }
    }

    fun enclosedOutputStream(file: File, cb: (PrintStream) -> Unit) {
        file.outputStream().let {
            PrintStream(it)
        }.let {
            cb(it)
            it.flush()
            it.close()
        }
    }

    fun createFile(file: File, content: String) {
        Preconditions.checkState(!file.exists() || file.isFile)
        val f = file.outputStream()
        f.channel.truncate(0)
        f.write(content.toByteArray(Charsets.UTF_8))
        f.close()
    }

    fun <T> measureCost(tag: String, cb: () -> T): T {
        val begin = System.currentTimeMillis()
        try {
            return cb()
        } finally {
            val end = System.currentTimeMillis()
            println("[measureCost($tag)]: ${(end - begin) / 1000.0}s")
        }
    }

    fun <T> cost(cb: () -> T): Double {
        val begin = System.currentTimeMillis()
        try {
            cb()
        } finally {
            val end = System.currentTimeMillis()
            return (end - begin) / 1000.0;
        }
    }

    fun loadConfig(propFile: String): Properties {
        Preconditions.checkArgument(propFile.endsWith(".conf"))
        val file = File(propFile)
        Preconditions.checkArgument(file.exists() && file.isFile)
        val properties = Properties()
        properties.load(file.inputStream())
        return properties
    }

    fun streamCopy(ins: InputStream, outs: OutputStream) {
        val reader = BufferedReader(InputStreamReader(ins, Charsets.UTF_8))
        val printer = PrintWriter(OutputStreamWriter(outs, Charsets.UTF_8))
        while (true) {
            reader.readLine()?.let {
                printer.println(it)
                printer.flush()
            } ?: break
        }
    }

    fun loadFiles(dir: File, re: Regex, filterRe: Regex): Map<String, String> {
        return dir.listFiles()!!.filter { f ->
            f.name.matches(re) && f.isFile
        }.filter { f ->
            !filterRe.containsMatchIn(f.name)
        }.map { f ->
            f.name to f.readText(Charsets.UTF_8)
        }.toMap()
    }

    fun readFile(file: File): List<String> {
        Preconditions.checkState(file.isFile)
        val reader = BufferedReader(
            InputStreamReader(file.inputStream(), Charsets.UTF_8)
        )
        val lines = reader.lines().toList()
        reader.close()
        return lines
    }

    fun createLog4jPropertiesFile(file: File, logFile: String) {
        val log4jProperties = listOf(
            "log4j.rootLogger" to "INFO, console, FILE",
            "log4j.appender.console" to "org.apache.log4j.ConsoleAppender",
            "log4j.appender.console.layout" to "org.apache.log4j.PatternLayout",
            "log4j.appender.console.layout.ConversionPattern" to "%d [%-5p] %C{1}:%L %m%n",
            "log4j.appender.console.Threshold" to "WARN",
            "log4j.appender.FILE" to "org.apache.log4j.RollingFileAppender",
            "log4j.appender.FILE.Append" to "true",
            "log4j.appender.FILE.File" to logFile,
            "log4j.appender.FILE.Threshold" to "DEBUG",
            "log4j.appender.FILE.layout" to "org.apache.log4j.PatternLayout",
            "log4j.appender.FILE.layout.ConversionPattern" to "%d [%-5p] %C{1}:%L %m%n",
            "log4j.appender.FILE.MaxFileSize" to "10MB"
        )
        createPropertiesConfFile(file.canonicalPath, log4jProperties)
    }

    fun flattenArgs(args: Array<out String>): Array<String> {
        return args.flatMap { s ->
            s.trim().split(Regex("\\s+"))
        }.toTypedArray()
    }

    fun randLong(bound: Long): () -> Long {
        val r = Random()
        return {
            abs(r.nextLong() % bound)
        }
    }

    fun randInt(bound: Int): () -> Int {
        val r = Random()
        return {
            abs(r.nextInt(bound))
        }
    }

    fun isPortAlive(host: String, port: Int): Boolean {
        val boxed = Result.wrap {
            val sock = Socket()
            sock.connect(InetSocketAddress(host, port), 1000)
            sock.close()
        }
        return boxed.isOk(true)
    }

    fun isPortAlive(port: Int): Boolean {
        return isPortAlive("127.0.0.1", port)
    }

    fun isPortDead(host: String, port: Int) = !isPortAlive(host, port)
    fun isPortDead(port: Int) = isPortDead("127.0.0.1", port)

    fun ensure(times: Int, failMsg: String, cb: () -> Boolean) {
        ensure(cb, failMsg, times)
    }

    fun ensure(cb: () -> Boolean, failMsg: String, times: Int = 60) {
        val rand = Random()
        for (i in (0..times)) {
            Result.wrap { Thread.sleep(1500 + rand.nextLong() % 500) }
            val boxed = Result.wrap(cb)
            if (!boxed.isOk(true)) continue
            if (boxed.unwrap()) return
        }
        Preconditions.checkState(false, "$failMsg, after 60 times")
    }

    fun ensurePortAlive(host: String, port: Int, failMsg: String) {
        ensure({ isPortAlive(host, port) }, failMsg)
    }

    fun ensurePortDead(host: String, port: Int, failMsg: String) {
        ensure({ isPortDead(host, port) }, failMsg)
    }

    fun unwind(g: () -> Unit, f: () -> Unit = {}) = { g();f() }

    fun getClusterBaseDir(clazz: Class<*>): String {
        val cwd = System.getProperty("user.dir")
        return cwd + File.separator + clazz.simpleName + ".dir"
    }

    fun recreateDir(path: String) {
        removeDir(path)
        Preconditions.checkState(File(path).mkdirs())
    }

    fun removeDir(path: String) {
        val dir = File(path)
        if (dir.exists()) {
            dir.deleteRecursively()
        }
    }

    fun getRandSize(base: Int, delta: Int): Int {
        Preconditions.checkState(base > 0)
        Preconditions.checkState(delta in 0..base)
        return base + Random().nextInt() % delta
    }

    fun getRandRanges(n: Int, l: Int): Array<Pair<Int, Int>> {
        Preconditions.checkState(n > 0)
        Preconditions.checkState(l > 0)
        return Array(n) {
            val a = Math.abs(Random().nextInt()) % l
            val b = Math.abs(Random().nextInt()) % l
            if (a < b) a to b else b to a
        }
    }

    fun dump(e: Throwable) {
        var err = e
        while (true) {
            err.printStackTrace()
            if (err.cause == null) {
                break
            } else {
                println("caused by: ")
                err = err.cause!!
            }
        }
    }

    data class LazyList<T>(private val gen: () -> T) {
        fun next(): T = gen()
        fun materialize(f: (T) -> Boolean): List<T> {
            val xs = mutableListOf<T>()
            while (true) {
                val v = gen()
                if (f(v)) {
                    break
                } else {
                    xs.add(v)
                }
            }
            return xs
        }

        fun take(n: Int) = List<T>(n) { gen() }

        fun <U> map(f: (T) -> U) = LazyList { f(gen()) }
        fun <U> zip(l: LazyList<U>) = LazyList { gen() to l.gen() }

        fun <U> foldr(init: U, f: (U, T) -> U): LazyList<U> {
            var v = init
            return LazyList<U> {
                val v0 = v
                v = f(v, gen())
                v0
            }
        }

        fun concat(xs: List<T>): LazyList<T> {
            val it = xs.iterator()
            return LazyList<T> {
                if (it.hasNext()) {
                    it.next()
                } else {
                    gen()
                }
            }
        }

        companion object {
            fun natural() = LazyList<Int>(generateCounter())
            fun step(n: Int) = natural().map { i -> i * n }
            fun <T> constants(v: T) = LazyList { v }
        }
    }


    fun <T> splitEveryNElem(xs: List<T>, n: Int): List<List<T>> {
        Preconditions.checkState(n > 0)
        return LazyList.step(n).zip(LazyList.step(n).map { v -> v + n })
            .materialize { (a, _) -> a >= xs.size }.map { (a, b) ->
                xs.subList(a, Math.min(b, xs.size))
            }
    }

    fun <T> adjacentPairs(xs: List<T>): List<Pair<T, T>> {
        return zip(xs.dropLast(1), xs.drop(1))
    }

    fun factor(n: Long, m: Long): List<Long> {
        return if (n <= m * 2) listOf(n)
        else factor(n / m, m).plus(m)
    }

    fun <T> pickUpOneRandomly(xs: List<T>): T =
        xs[Random().nextInt(xs.size)]

    fun <T> pickUpRandomly(xs: List<T>, n: Int): List<T> {
        return xs.shuffled().take(n)
    }

    fun <T> splitNGroupRandomly(xs: List<T>, n: Int): List<List<T>> {
        if (xs.size <= n) {
            return xs.map { x -> listOf(x) }
        }
        var numRemainElms = xs.size
        var numRemainGroups = n
        var points = mutableListOf<Int>(0)
        val rand = Random()
        val twiceAvgGroupSize = 2 * (xs.size / n);
        while (numRemainGroups > 0) {
            numRemainGroups -= 1
            val maxGroupSize = numRemainElms - numRemainGroups
            val groupSize = if (numRemainGroups == 0) {
                maxGroupSize
            } else {
                rand.nextInt(Math.min(twiceAvgGroupSize, maxGroupSize)) + 1
            }
            points.add(groupSize)
            numRemainElms -= groupSize
        }
        Preconditions.checkArgument(numRemainElms == 0 && numRemainGroups == 0);
        val offsets = points.toTypedArray()
        Preconditions.checkArgument(offsets.size == n + 1)
        (1..n).forEach { i ->
            offsets[i] += offsets[i - 1]
        }
        return (1..n).map { i ->
            xs.subList(offsets[i - 1], offsets[i])
        }
    }

    fun <T> splitNGroup(xs: List<T>, n: Int): List<List<T>> {
        if (xs.isEmpty()) {
            return emptyList()
        }
        val m0 = xs.size / n
        val ms = Array(n) { m0 }
        (0 until xs.size % n).forEach { i ->
            ms[i] = ms[i] + 1
        }
        val ms0 = ms.filter { m -> m > 0 }
        var i = 0
        val xss = mutableListOf<List<T>>()
        (ms0.indices).forEach { j ->
            xss.add(xs.subList(i, i + ms0[j]))
            i += ms0[j]
        }
        return xss
    }


    fun <T> roundRobin(elms: List<T>): () -> T {
        Preconditions.checkState(elms.isNotEmpty())
        var i = AtomicInteger(0);
        return {
            elms[abs(i.getAndIncrement() % elms.size)]
        }
    }

    fun timed(timeout: Long, interval: Long, unit: TimeUnit, f: () -> Boolean): Boolean {
        val startMs = System.currentTimeMillis()
        val deadLine = startMs + unit.toMillis(timeout)
        while (true) {
            if (f()) {
                return true
            }
            val nowMs = System.currentTimeMillis()
            if (nowMs > deadLine) {
                return false
            }
            println("Timed elapse=${(nowMs - startMs) / 1000}s, remain=${(deadLine - nowMs) / 1000}s")
            LockSupport.parkNanos(unit.toNanos(interval))
        }
        return false
    }

    fun getClassPathOfJavaClass(clz: Class<*>) =
        clz.protectionDomain.codeSource.location.path!!


    fun times(atLeast: Int, atMost: Int): IntRange {
        return 1..atLeast + Random().nextInt() % (atMost + 1 - atLeast)
    }

    fun getRandSegments(l: Int, n: Int): IntArray {
        if (l < 2) {
            return intArrayOf(l)
        }

        Preconditions.checkState(n in 1 until l)
        val cuts = arrayOf(
            0,
            *Array(n) {
                getRandSize(l / 2, l / 2)
            },
            l
        )

        cuts.sort()
        val segments = mutableListOf<Int>()
        var init = cuts[0]
        cuts.slice(1..cuts.lastIndex).forEach { c ->
            segments.add(c - init)
            init = c
        }

        return segments.toIntArray()
    }

    fun getCallerName(n: Int): String {
        val byteOut = ByteArrayOutputStream()
        val ps = PrintStream(byteOut)
        Exception().printStackTrace(ps)
        val lines = byteOut.toByteArray().toString(Charsets.UTF_8).split("\n")
        val methodPattern = Regex("^\\s*at\\s+\\S*\\.(\\w+)\\(.*\\)\\s*$")
        return methodPattern.matchEntire(lines[n])!!.groupValues[1]
    }

    fun getTestName(): String {
        val byteOut = ByteArrayOutputStream()
        val ps = PrintStream(byteOut)
        Exception().printStackTrace(ps)
        val lines = byteOut.toByteArray().toString(Charsets.UTF_8).split("\n")
        val methodPattern = Regex("^\\s*at\\s+(\\S*)\\.(\\w+)\\(.*\\)\\s*$")
        val methods = lines.flatMap { l ->
            methodPattern.matchEntire(l)?.let { listOf(it.groupValues[1] to it.groupValues[2]) } ?: listOf()
        }
        return methods.first { (cls, method) ->
            Result.wrap {
                Class.forName(cls)!!
            } bind { cls ->
                cls.getMethod(method)!!
            } bind { method ->
                method.annotations.first { a ->
                    a.annotationClass.qualifiedName == "org.testng.annotations.Test"
                }
            } bind {
                true
            } unwrapOr false
        }.second
    }

    fun db(): String = toSnake(getTestName())

    fun generateCounterWithPrefix(s: String): () -> String {
        val count = generateLongCounter()
        return {
            "$s${count()}"
        }
    }

    fun toCamel(s: String): String {
        return s.split("_").filter { e -> e.isNotEmpty() }
            .joinToString("") { e -> "${e.first().uppercaseChar()}${e.drop(1)}" }
    }

    fun toSnake(s: String): String {
        return s.map { c ->
            if (c.isUpperCase()) {
                "_${c.lowercaseChar()}"
            } else {
                "$c"
            }
        }.joinToString("").trimStart('_')
    }

    /**
     * Read resource from relative path which all in `framework` module.
     */
    fun readContentFromResource(path: String): String {
        val realPath = "${getResourceDir()}/$path"
        println(realPath)
        return readContentFromPath(realPath)
    }

    fun readContentFromCurrentResource(res: String): String {
        return String(this.javaClass.classLoader.getResourceAsStream(res).readBytes()!!, StandardCharsets.UTF_8)
    }

    fun readContentFromPath(path: String): String {
        return File(path).readText(Charsets.UTF_8)
    }

    fun getResourceDir(): String {
        val currentDir = System.getProperty("user.dir")
        return "$currentDir/../xlab-framework/src/main/resources"
    }

    fun readPropertiesFromResource(path: String): Properties {
        val defaultPath = getResourceDir()
        val realPath = "$defaultPath/${path}"
        val p = Properties()
        val s = readContentFromPath(realPath)
        p.load(StringReader(s))
        return p
    }

    fun listResource(subdir: String, filter: (File) -> Boolean): List<File> {
        val p = this.javaClass.classLoader.getResource(subdir).path
        return File(p).listFiles()!!.filter(filter)
    }

    fun listResource(subdir: String, fileExt: String): List<File> {
        return listResource(subdir) { file ->
            file.isFile && file.name.endsWith(fileExt)
        }
    }

    fun toHexString(ba: ByteArray): String {
        val alphabet = (('0'..'9') + ('a'..'f')).toCharArray()
        val chars =
            ba.flatMap { b -> listOf(alphabet[b.toInt().shr(4).and(0xf)], alphabet[b.toInt().and(0xf)]) }.toCharArray()
        return String(chars)
    }

    fun renderTemplate(
        template: String,
        mainTemplateName: String,
        parameters: Map<String, Any?>
    ): String {
        val st = STGroupString(template).getInstanceOf(mainTemplateName)
        val requiredKeys = st.attributes.keys
        val actualKeys = parameters.keys
        if (!actualKeys.containsAll(requiredKeys)) {
            requiredKeys.removeAll(actualKeys)
            val missingKeys = requiredKeys.stream().map { k: String -> "'$k'" }.collect(Collectors.joining(", "))
            throw Exception("Missing keys: $missingKeys")
        }
        parameters.forEach { (k: String, v: Any?) -> st.add(k, v) }
        return st.render()
    }

    fun renderTemplate(templateName: String, vararg parameters: Pair<String, Any?>): String {
        val template =
            String(this.javaClass.classLoader.getResourceAsStream(templateName).readBytes()!!, StandardCharsets.UTF_8)
        return renderTemplate(template, "main", parameters.toMap())
    }

    fun renderTemplateFromResources(path: String, vararg parameters: Pair<String, Any?>): String {
        val templatePath = "${getResourceDir()}/$path"
        val templateContent = readContentFromPath(templatePath)
        return renderTemplate(templateContent, "main", parameters.toMap())
    }
}

