package com.starrocks.itest.framework.utils

import org.slf4j.LoggerFactory

sealed class Result<out T> {
    fun isOk(slientOnErr: Boolean = false): Boolean {
        return when (this) {
            is Ok -> true
            is Err -> {
                if (!slientOnErr) {
                    LOG.warn("${e.javaClass.simpleName}: ${e.message}", e)
                }
                false
            }
        }
    }

    infix fun onOk(f: () -> Unit): Result<T> {
        if (this is Ok) {
            f()
        }
        return this
    }

    infix fun onErr(f: (Throwable) -> Unit): Result<T> {
        if (this is Err) {
            f(e)
        }
        return this
    }

    infix fun onAny(f: () -> Unit): Result<T> {
        f()
        return this
    }

    infix fun ifOkThen(f: () -> Unit) = onOk(f)
    infix fun ifErrThen(f: (Throwable) -> Unit) = onErr(f)

    companion object {
        val LOG = LoggerFactory.getLogger(Result::class.java)!!

        object Begin {
            // wrap函数将函数f的执行结果转换为Result<T>.
            // 如果f无异常抛出, 则结果为Ok<T>; 否则为Err
            // 如果f无返回值, 则结果为Result<Unit>, Unit即为Java中void类型.
            inline infix fun <T> wrap(f: () -> T): Result<T> {
                return try {
                    Ok(f())
                } catch (e: Throwable) {
                    Err(e)
                }
            }
        }

        object End

        val b = Begin
        val e = End

        inline infix fun <T> wrap(f: () -> T) = Begin.wrap(f)
    }

    fun unwrap(): T {
        when (this) {
            is Ok -> return v
            is Err -> throw e
        }
    }

    fun unwrap_or_null(): T? {
        return when (this) {
            is Ok -> v
            else -> null
        }
    }

    inline infix fun unwrap(e: End): T = unwrap()
    inline infix fun <S> unwrapOr(v: S): T = when (this) {
        is Err -> v as T
        is Ok -> this.v
    }

    // 如果Result<T>为Err, 则直接返回原来的e;
    // 如果Result<T>为Ok, 则执行下一步操作f
    inline infix fun <S> bind(f: (T) -> S): Result<S> {
        return when (this) {
            is Err -> Err(e)
            is Ok -> Begin.wrap { f(v) }
        }
    }

}

data class Ok<T>(val v: T) : Result<T>()
data class Err(val e: Throwable) : Result<Nothing>()
