package com.starrocks.itest.framework.utils

import com.google.common.base.Strings
import java.math.BigDecimal
import java.math.BigInteger

object DecimalUtil {
    enum class OverflowPolicy {
        BINARY_BOUND_QUIET,
        DECIMAL_BOUND_QUIET,
        BINARY_BOUND_EXCLAIM,
        DECIMAL_BOUND_EXCLAIM,
    }

    fun intPart(d: BigDecimal): BigDecimal = BigDecimal(d.toBigInteger(), 0)
    fun decimalIsInteger(d: BigDecimal): Boolean = d.rem(BigDecimal.ONE).unscaledValue() == BigInteger.ZERO
    fun decimalToString(d: BigDecimal): String = if (decimalIsInteger(d)) {
        d.toBigInteger().toString()
    } else {
        d.toPlainString()
    }

    data class RawDouble(val sign: Boolean, val exponent: Int, val mantissa: Long);
    fun doubleToRawDouble(d: Double): RawDouble {
        val signShift = 63
        val signMask = 1L.shl(signShift)
        val exponentShift = 52
        val exponentMask = 2047L.shl(exponentShift)
        val mantissaShift = 0
        val mantissaMask = 1L.shl(exponentShift) - 1L
        val rawBits = d.toRawBits()
        val sign = rawBits.and(signMask).ushr(signShift)
        val exponent = rawBits.and(exponentMask).ushr(exponentShift)
        val mantissa = rawBits.and(mantissaMask)
        return RawDouble(sign == 0L, exponent.toInt() - 1023, mantissa)
    }

    fun scaleUpDecimal(d: BigDecimal, s: Int): BigDecimal {
        val newScale = d.scale() + s
        val tens = BigDecimal.valueOf(10).pow(s).unscaledValue()
        return BigDecimal(d.unscaledValue().multiply(tens), newScale)
    }

    fun max_bin_integer(bits: Int) =
            BigInteger.ONE.shiftLeft(bits - 1).subtract(BigInteger.ONE)!!

    fun min_bin_integer(bits: Int) =
            max_bin_integer(bits).negate().subtract(BigInteger.ONE)!!

    fun max_bin_decimal(bits: Int, scale: Int) =
            BigDecimal(max_bin_integer(bits), scale)

    fun min_bin_decimal(bits: Int, scale: Int) =
            BigDecimal(min_bin_integer(bits), scale)

    fun max_dec_integer(precision: Int) = BigInteger(Strings.repeat("9", precision))

    fun min_dec_integer(precision: Int) = max_dec_integer(precision).negate()!!

    fun max_dec_decimal(precision: Int, scale: Int) =
            BigDecimal(max_dec_integer(precision), scale)

    fun min_dec_decimal(precision: Int, scale: Int) =
            max_dec_decimal(precision, scale).negate()

    fun two_complement(v: BigInteger, bits: Int): BigInteger {
        val power2 = BigInteger.ONE.shiftLeft(bits)!!
        val mask32bits = power2 - BigInteger.ONE
        val v0 = v.and(mask32bits)!!
        return if (v0.testBit(bits - 1)) {
            power2.subtract(v0).negate()
        } else {
            v0
        }
    }

    fun integer_overflow_policy(nbits: Int): (BigInteger) -> BigInteger? {
        val binMax = max_bin_integer(nbits)
        val binMin = min_bin_integer(nbits)
        return { intValue ->
            if (intValue > binMax || intValue < binMin) {
                null
            } else {
                intValue
            }
        }
    }

    fun overflow_policy(nbits: Int, precision: Int, policy: OverflowPolicy): (BigDecimal) -> BigDecimal? {
        val binMax = max_bin_integer(nbits)
        val binMin = min_bin_integer(nbits)
        val decMax = max_dec_integer(precision)
        val decMin = min_dec_integer(precision)
        when (policy) {
            OverflowPolicy.BINARY_BOUND_QUIET -> {
                return { v ->
                    val dec = v.unscaledValue()!!
                    if (dec > binMax || dec < binMin) {
                        BigDecimal(two_complement(dec, nbits), v.scale())
                    } else {
                        v
                    }
                }
            }
            OverflowPolicy.DECIMAL_BOUND_QUIET -> {
                return { v ->
                    val dec = v.unscaledValue()!!
                    if (dec > decMax || dec < decMin) {
                        BigDecimal(two_complement(dec, nbits), v.scale())
                    } else {
                        v
                    }
                }
            }
            OverflowPolicy.BINARY_BOUND_EXCLAIM -> {
                return { v ->
                    val dec = v.unscaledValue()!!
                    if (dec > binMax || dec < binMin) {
                        null
                    } else {
                        v
                    }
                }
            }
            OverflowPolicy.DECIMAL_BOUND_EXCLAIM -> {
                return { v ->
                    val dec = v.unscaledValue()!!
                    if (dec > decMax || dec < decMin) {
                        null
                    } else {
                        v
                    }
                }
            }
        }
    }
}
