package com.alipay.tools.demo

/**
 * @author shuming.lsm
 * @version 2018/10/24
 **/

case class Case1(a: Int, b: Boolean = false) {
  def p(): Unit = {
    println(s"a: ${a}, b: ${b}")
  }
}
