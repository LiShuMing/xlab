package com.starrocks.itest.framework

import org.junit.jupiter.api.Test
import kotlin.test.assertTrue

class BasicTest {
   @Test
   fun testBasic() {
       assertTrue { 2 == 1 + 1 }
   }
}