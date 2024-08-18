package org.xlab.scala.demo

/**
 * @author shuming.lsm
 * @version 2019/08/05
 **/
object PrecisionDemo {
  def main(args: Array[String]): Unit = {
    val bg = BigDecimal("20190801002382000052000000017638")
    if (bg.isValidLong) {

    } else {

    }
    println(bg.toLong)
  }
}
