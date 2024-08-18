package com.alipay.tools.cases

import scala.reflect.runtime.{universe => ru}
import ru._

case class TableInput(records: Long, bytes: Long, overwrite: Boolean = false)

object ReflectDemo {
  def main(args: Array[String]): Unit = {
    val runtimeMirror = ru.runtimeMirror(getClass.getClassLoader)

    val cls = Class.forName("com.alipay.tools.cases.TableInput")
    val clsSymbol = runtimeMirror.classSymbol(cls)
    val ctor = clsSymbol.primaryConstructor.asMethod
    val clsMirror = runtimeMirror.reflectClass(clsSymbol)
    val ctorMirror = clsMirror.reflectConstructor(ctor)
    val tableInput = ctorMirror.apply(1L, 1L)
    println(tableInput)
  }
}
