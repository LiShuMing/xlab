package com.alipay.tools.demo

/**
 * @author shuming.lsm
 * @version 2018/10/24
 **/
class If1Impl extends If1 {
  override def method1(a: Int, b: Boolean = false): Unit = {
    println(s"a: ${a}, b: ${b}")
  }
}
