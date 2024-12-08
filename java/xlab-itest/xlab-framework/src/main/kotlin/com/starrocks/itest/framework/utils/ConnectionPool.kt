package com.starrocks.itest.framework.utils

import java.sql.Connection
import java.util.concurrent.ArrayBlockingQueue

class ConnectionPool<T : Connection>(private val initConnectionFunc: () -> Unit,
                                     private val newConnectionFunc: () -> T,
                                     private val capacity: Int) {
  init {
    initConnectionFunc()
  }

  private val connectionQueue = ArrayBlockingQueue<T>(
      if (capacity <= 0) {
        1
      } else {
        capacity
      }
  )

  fun getCxn(): T {
    var cxn = connectionQueue.poll()
    if (cxn == null || capacity <= 0) {
      return newConnectionFunc()
    }
    return cxn
  }
}
