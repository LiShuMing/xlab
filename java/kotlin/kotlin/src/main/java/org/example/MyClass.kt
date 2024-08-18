package org.example
class MyClass(val a: Double, val b: Double) {
    val c = a + b
}
fun main(args: Array<String>) {
    println("abc")
    val a = MyClass(1.0, 1.0)
    println(a.c)
}