package com.cclab

import org.example.MyClass
import org.junit.Assert
import org.junit.Test

class BasicUse {
    @Test
    fun testBase() {
        val a = MyClass(1.0, 1.0)
        Assert.assertTrue(a.c == 2.0)
    }
}