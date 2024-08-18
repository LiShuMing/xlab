package com.starrocks.itest.framework

import org.junit.jupiter.api.Test
import kotlin.test.assertTrue

class BasicTest {
   @Test
   fun testBasic() {
       assertTrue { 2 == 1 + 1 }
   }

    @Test
    fun testLinkedMap() {
        val a = LinkedHashMap<String, String>()
        a.put("b", "b")
        a.put("a", "a")
        a.put("c", "c")
        a.put("a", "a")
        a.put("b", "a")
        for (e in a.entries) {
            println(e.key + "-> " + e.value)
        }
    }
}