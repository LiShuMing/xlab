package com.starrocks.itest.framework.utils

import com.google.common.base.Strings
import java.math.BigDecimal
import java.math.BigInteger
import java.math.RoundingMode
import java.sql.Date
import java.sql.Timestamp
import java.util.*
import kotlin.math.abs

object RandUtil {
    fun generateRandomInteger(bits: Int, negRatio: Int): () -> BigInteger {
        val rand = Random()
        val max = DecimalUtil.max_bin_integer(bits)
        val min = DecimalUtil.min_bin_integer(bits)
        return {
            if (rand.nextInt(100) < negRatio) {
                when (val randBits = rand.nextInt(bits)) {
                    bits - 1 -> min
                    else -> {
                        BigInteger.ONE.shiftLeft(randBits).add(BigInteger(randBits, rand)).negate()
                    }
                }
            } else {
                when (val randBits = rand.nextInt(bits + 1)) {
                    0 -> {
                        BigInteger.ZERO
                    }

                    bits -> {
                        max
                    }

                    else -> {
                        BigInteger.ONE.shiftLeft(randBits - 1).add(BigInteger(randBits - 1, rand))
                    }
                }
            }
        }
    }

    fun generateRandomDecimalBinary(precision: Int, scale: Int): () -> ByteArray {
        val decimalGen = generateRandomDecimal(precision, scale, 50)
        return {
            decimalGen().toPlainString().toByteArray()
        }
    }

    fun generateRandomBoolean(falseRatio: Int): () -> Boolean {

        val r = generateRandomInt(falseRatio)
        return {
            r() < 0
        }
    }

    fun getFiniteSetGenerator(n: Int, generator: () -> Any): () -> Any {
        val finiteSet = mutableSetOf<Any>()
        val rand = Random()
        val setSize = if (n == 1) {
            1
        } else {
            n / 2 + rand.nextInt(n)
        }
        while (finiteSet.size < setSize) {
            finiteSet.add(generator())
        }
        val finiteSetArray = finiteSet.toTypedArray()
        return {
            finiteSetArray[rand.nextInt(setSize)]
        }
    }

    inline fun <reified T> generateDuplicateValue(values: List<T>): () -> T {
        val valueArray = values.toTypedArray()
        val rand = Random()
        var i = 0
        return {
            val v = valueArray[i]
            i += rand.nextInt(2)
            i %= valueArray.size
            v
        }
    }

    fun <T> generateRandomValue(vararg values: T): () -> T {
        val rand = Random()
        return {
            values[rand.nextInt(values.size)]
        }
    }

    fun generateRandomRangeInt(from: Int, to: Int): () -> Int {
        val rand = Random()
        return {
            from + rand.nextInt(to - from)
        }
    }

    fun generateRandomRangeLong(from: Long, to: Long): () -> Long {
        val rand = Random()
        return {
            from + abs(rand.nextLong() % (to - from))
        }
    }

    fun generateRandomRangeDecimal(scale: Int, from: BigDecimal, to: BigDecimal): () -> BigDecimal {
        val rand = SplittableRandom()
        return {
            (from + rand.nextDouble((to - from).toDouble()).toBigDecimal()).setScale(scale, RoundingMode.CEILING)
        }
    }


    fun generateRandomTinyInt(negRatio: Int): () -> Byte {
        val r = generateRandomInteger(8, negRatio)
        return { r().toByte() }
    }

    fun generateRandomSmallInt(negRatio: Int): () -> Short {
        val r = generateRandomInteger(16, negRatio)
        return { r().toShort() }
    }

    fun generateRandomInt(negRatio: Int): () -> Int {
        val r = generateRandomInteger(32, negRatio)
        return { r().toInt() }
    }

    fun generateRandomBigInt(negRatio: Int): () -> Long {
        val r = generateRandomInteger(64, negRatio)
        return { r().toLong() }
    }

    fun generateRandomLargeInt(negRatio: Int): () -> BigInteger =
        generateRandomInteger(128, negRatio)


    fun generateRandomDecimal(precision: Int, scale: Int, negRatio: Int): () -> BigDecimal {
        val maxValue = BigInteger(Strings.repeat("9", precision))
        val randomBigInt = generateRandomLargeInt(negRatio)
        return {
            val bigInt = randomBigInt()
            if (bigInt.signum() < 0) {
                BigDecimal(bigInt.mod(maxValue), scale).negate()
            } else {
                BigDecimal(bigInt.mod(maxValue), scale)
            }
        }
    }

    fun generateRandomVarChar(alphabeta: Array<Char>, minLength: Int, maxLength: Int): () -> ByteArray {
        val rand = Random()
        return {
            val delta = if (minLength == maxLength) {
                0
            } else {
                rand.nextInt(maxLength - minLength)
            }

            val clob = CharArray(minLength + delta) {
                alphabeta[rand.nextInt(alphabeta.size)]
            }
            String(clob).toByteArray(Charsets.UTF_8)
        }
    }

    fun generateRandomUtf8VarChar(alphabeta: Array<String>, minLength: Int, maxLength: Int): () -> ByteArray {
        val rand = Random()
        return {
            val delta = if (minLength == maxLength) {
                0
            } else {
                rand.nextInt(maxLength - minLength)
            }

            val clob = Array<String>(minLength + delta) {
                alphabeta[rand.nextInt(alphabeta.size)]
            }
            clob.joinToString("").toByteArray(Charsets.UTF_8)
        }
    }

    fun generateVarchar(minLength: Int, maxLength: Int): () -> ByteArray {
        return generateRandomVarChar(lc() + uc() + digit(), minLength, maxLength)
    }

    fun <T> generateDataSkew(value: T, percentile: Int, f: () -> T): () -> T {
        val r = generateRandomRangeInt(0, 100)
        return {
            if (r() < percentile) {
                value
            } else {
                f()
            }
        }
    }

    inline fun <reified T> generateNItems(n: Int, gen: () -> T): Array<T> = Array(n) { gen() }
    inline fun <reified T> generateFixedItems(items: Array<T>): () -> T {
        val rndIdx = generateRandomRangeInt(0, items.size)
        return {
            items[rndIdx()]
        }
    }

    fun generateUtf8Varchar(minLength: Int, maxLength: Int): () -> ByteArray {
        val ascii = (lc() + uc() + digit()).map { ch -> "$ch" }.toTypedArray()
        val utf8 = utf8();
        return generateRandomUtf8VarChar(ascii + utf8, minLength, maxLength)
    }

    fun lc() = (0..25).map { ('a'.toInt() + it).toChar() }.toTypedArray()
    fun uc() = (0..25).map { ('A'.toInt() + it).toChar() }.toTypedArray()
    fun digit() = (0..9).map { ('0'.toInt() + it).toChar() }.toTypedArray()
    fun utf8() = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥〇一二三四五六七八大九十百千万亿零壹贰叁肆伍陆柒捌玖拾佰仟"
        .split(Regex("")).toTypedArray()

    fun extraXdigit() =
        (0..5).map { ('A'.toInt() + it).toChar() }.toTypedArray() +
                (0..5).map { ('a'.toInt() + it).toChar() }.toTypedArray()

    fun xdigit() = digit() + extraXdigit()

    fun generateRandomFloat(): () -> Float {
        val rand = Random()
        val genInt = generateRandomInt(50)
        return {
            rand.nextFloat() * genInt()
        }
    }

    fun generateRandomDouble(): () -> Double {
        val rand = Random()
        val genLong = generateRandomBigInt(50)
        return {
            rand.nextDouble() * genLong()
        }
    }

    fun generateRandomDate(start: String, end: String): () -> Date {
        val rand = Random()
        val startDay = Date.valueOf(start).time / 86400000
        val endDay = Date.valueOf(end).time / 86400000 - 1
        val timeDiff = Date.valueOf(start).time % 86400000
        return {
            val date = Date((startDay + abs(rand.nextLong() % (endDay - startDay))) * 86400000 + timeDiff)
            date
        }
    }

    fun generateRandomTimestamp(start: String, end: String): () -> Timestamp {
        val rand = Random()
        val startMs = Timestamp.valueOf(start).time
        val endMs = Timestamp.valueOf(end).time
        return {
            Timestamp((startMs + abs(rand.nextLong() % (endMs - startMs))))
        }
    }

    fun generateMidTimestamp(start: String, end: String): String {
        val startMs = Timestamp.valueOf(start).time
        val endMs = Timestamp.valueOf(end).time
        val midMs = (startMs + endMs) / 2
        val midMs0 = midMs - midMs % 1000
        val trailMsRe = Regex("\\.\\d+$")
        return trailMsRe.replace(Timestamp(midMs0).toString(), "")
    }

}
