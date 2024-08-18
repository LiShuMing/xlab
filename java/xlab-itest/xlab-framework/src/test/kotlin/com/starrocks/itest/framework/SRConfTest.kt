package com.starrocks.itest.framework

import com.starrocks.itest.framework.conf.SRConf
import org.junit.jupiter.api.Disabled
import java.nio.file.Paths
import kotlin.io.path.exists
import kotlin.test.Test
import kotlin.test.assertTrue

class SRConfTest {
    @Test
    @Disabled
    fun testBasic() {
        val path = Paths.get("./conf", "sr.yaml")
        assertTrue { path.exists() }

        val srConf = SRConf.parse(path)
        assertTrue { srConf != null }
        println(srConf)
    }
}