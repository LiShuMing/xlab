package com.alipay.tools.demo

/**
 * @author shuming.lsm
 * @version 2019/06/13
 **/
class PanguFileAlreadyExistsException(msg: String) extends Exception(msg) {
}

object ExceptionDemo {

  def exception(): Unit = {
    throw new PanguFileAlreadyExistsException("abc")
  }

  def main(args: Array[String]): Unit = {
    try {
      exception()
    } catch {
      case e: Exception =>
        println(e.getClass)
        val exceptionName = e.getClass.getName
        println(exceptionName)
        if (exceptionName.contains("PanguFileAlreadyExistsException")) {
          println("ignore exception")
        } else {
          throw e
        }
    }
  }
}
